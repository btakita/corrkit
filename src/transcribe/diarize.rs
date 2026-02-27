//! Speaker diarization using pyannote-rs (ONNX Runtime).
//!
//! Requires the `diarize` feature flag.

use anyhow::Result;
use pyannote_rs::{EmbeddingExtractor, EmbeddingManager};
use std::collections::HashMap;

use super::model;

/// A labeled speaker segment from diarization.
#[derive(Debug, Clone)]
pub struct DiarizedSegment {
    pub start: f64,
    pub end: f64,
    pub speaker_id: usize,
    /// Cosine similarity confidence (0.0–1.0). 0.0 for segments assigned by proximity.
    pub confidence: f32,
}

/// ONNX model filenames (from pyannote-rs releases).
const SEGMENTATION_MODEL: &str = "segmentation-3.0.onnx";
const EMBEDDING_MODEL: &str = "wespeaker_en_voxceleb_CAM++.onnx";

/// Convert f32 audio samples ([-1.0, 1.0]) to i16 (pyannote-rs expects i16).
fn f32_to_i16(samples: &[f32]) -> Vec<i16> {
    samples
        .iter()
        .map(|&s| (s.clamp(-1.0, 1.0) * 32767.0) as i16)
        .collect()
}

/// Cosine similarity between two embedding vectors.
fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm_a == 0.0 || norm_b == 0.0 {
        return 0.0;
    }
    dot / (norm_a * norm_b)
}

/// Compute confidence (best cosine similarity) of an embedding against known speakers.
fn compute_confidence(embedding: &[f32], manager: &EmbeddingManager) -> (usize, f32) {
    let speakers = manager.get_all_speakers();
    let mut best_id = 0usize;
    let mut best_sim = 0.0f32;
    for (&id, stored) in speakers {
        let sim = cosine_similarity(embedding, stored.as_slice().unwrap_or(&[]));
        if sim > best_sim {
            best_sim = sim;
            best_id = id;
        }
    }
    (best_id, best_sim)
}

/// Run speaker diarization on audio samples.
///
/// Returns segments labeled with speaker IDs (1-based).
pub fn diarize(
    samples_f32: &[f32],
    sample_rate: u32,
    max_speakers: usize,
    cache_dir: Option<&str>,
) -> Result<Vec<DiarizedSegment>> {
    let samples_i16 = f32_to_i16(samples_f32);

    // Resolve ONNX model paths (download if needed)
    let seg_model = model::resolve_onnx_model(SEGMENTATION_MODEL, cache_dir)?;
    let emb_model = model::resolve_onnx_model(EMBEDDING_MODEL, cache_dir)?;

    eprintln!("Running speaker segmentation...");
    let segments = pyannote_rs::get_segments(&samples_i16, sample_rate, &seg_model)
        .map_err(|e| anyhow::anyhow!("Segmentation failed: {:?}", e))?;

    eprintln!("Extracting speaker embeddings...");
    let mut extractor = EmbeddingExtractor::new(&emb_model)
        .map_err(|e| anyhow::anyhow!("Failed to load embedding model: {:?}", e))?;
    let mut manager = EmbeddingManager::new(max_speakers);
    let threshold = 0.5;

    let mut result = Vec::new();

    for segment in segments {
        let segment = segment.map_err(|e| anyhow::anyhow!("Segment error: {:?}", e))?;
        match extractor.compute(&segment.samples) {
            Ok(embedding) => {
                let embedding_vec: Vec<f32> = embedding.collect();
                let speaker_id =
                    if manager.get_all_speakers().len() == max_speakers {
                        manager
                            .get_best_speaker_match(embedding_vec.clone())
                            .map_err(|e| anyhow::anyhow!("Speaker match error: {:?}", e))
                            .unwrap_or(0)
                    } else {
                        manager
                            .search_speaker(embedding_vec.clone(), threshold)
                            .unwrap_or(0)
                    };

                // Compute confidence score against stored speaker embeddings
                let (_, confidence) = compute_confidence(&embedding_vec, &manager);

                result.push(DiarizedSegment {
                    start: segment.start,
                    end: segment.end,
                    speaker_id,
                    confidence,
                });
            }
            Err(_) => {
                // Segment too short for embedding — mark for post-processing
                result.push(DiarizedSegment {
                    start: segment.start,
                    end: segment.end,
                    speaker_id: 0,
                    confidence: 0.0,
                });
            }
        }
    }

    // Post-process: reassign Unknown (speaker_id 0) segments to nearest speaker
    // by temporal proximity. There is no valid "Unknown" when speaker count is known.
    reassign_unknown_segments(&mut result);

    let unique_speakers: std::collections::HashSet<usize> =
        result.iter().map(|s| s.speaker_id).filter(|&id| id != 0).collect();
    eprintln!(
        "Diarization complete: {} segments, {} speakers detected",
        result.len(),
        unique_speakers.len()
    );

    Ok(result)
}

/// Reassign Unknown (speaker_id 0) segments to the nearest known speaker by time.
fn reassign_unknown_segments(segments: &mut [DiarizedSegment]) {
    let len = segments.len();
    for i in 0..len {
        if segments[i].speaker_id != 0 {
            continue;
        }
        let mid = (segments[i].start + segments[i].end) / 2.0;

        // Search backward for nearest known speaker
        let mut prev_id = 0usize;
        let mut prev_dist = f64::MAX;
        for j in (0..i).rev() {
            if segments[j].speaker_id != 0 {
                prev_id = segments[j].speaker_id;
                prev_dist = (mid - segments[j].end).abs();
                break;
            }
        }

        // Search forward for nearest known speaker
        let mut next_id = 0usize;
        let mut next_dist = f64::MAX;
        for seg in &segments[(i + 1)..] {
            if seg.speaker_id != 0 {
                next_id = seg.speaker_id;
                next_dist = (seg.start - mid).abs();
                break;
            }
        }

        // Assign to nearest neighbor (prefer previous on tie)
        let assigned = if prev_id != 0 && (prev_dist <= next_dist || next_id == 0) {
            prev_id
        } else if next_id != 0 {
            next_id
        } else {
            continue; // No known speakers at all — leave as 0
        };

        segments[i].speaker_id = assigned;
        // confidence stays 0.0 to indicate proximity-assigned
    }
}

/// A merged segment: whisper text + speaker ID + confidence.
#[derive(Debug, Clone)]
pub struct MergedSegment {
    pub t0: i64,
    pub t1: i64,
    pub text: String,
    pub speaker_id: usize,
    pub confidence: f32,
}

/// Merge whisper transcript segments with diarization speaker labels.
///
/// For each whisper segment, find the diarized speaker whose segment overlaps most.
pub fn merge_speakers(
    whisper_segments: &[(i64, i64, String)],
    diarized: &[DiarizedSegment],
    sample_rate: u32,
) -> Vec<MergedSegment> {
    whisper_segments
        .iter()
        .map(|(t0, t1, text)| {
            // Convert whisper centisecond timestamps to seconds
            let w_start = *t0 as f64 * 0.01;
            let w_end = *t1 as f64 * 0.01;

            // Find diarized segment with most overlap + its confidence
            let (speaker, confidence) =
                best_overlapping_speaker(w_start, w_end, diarized, sample_rate);
            MergedSegment {
                t0: *t0,
                t1: *t1,
                text: text.clone(),
                speaker_id: speaker,
                confidence,
            }
        })
        .collect()
}

/// Find the speaker ID with the most temporal overlap for a given time range.
/// Returns (speaker_id, weighted_confidence).
/// Falls back to nearest segment by temporal proximity when no overlap exists.
fn best_overlapping_speaker(
    start: f64,
    end: f64,
    diarized: &[DiarizedSegment],
    _sample_rate: u32,
) -> (usize, f32) {
    let mut speaker_overlap: HashMap<usize, f64> = HashMap::new();
    let mut speaker_conf_sum: HashMap<usize, f64> = HashMap::new();

    for seg in diarized {
        let overlap_start = start.max(seg.start);
        let overlap_end = end.min(seg.end);
        let overlap = (overlap_end - overlap_start).max(0.0);
        if overlap > 0.0 {
            *speaker_overlap.entry(seg.speaker_id).or_default() += overlap;
            *speaker_conf_sum.entry(seg.speaker_id).or_default() +=
                overlap * seg.confidence as f64;
        }
    }

    if let Some((&id, &total_overlap)) = speaker_overlap
        .iter()
        .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
    {
        let weighted_conf = if total_overlap > 0.0 {
            (speaker_conf_sum.get(&id).copied().unwrap_or(0.0) / total_overlap) as f32
        } else {
            0.0
        };
        return (id, weighted_conf);
    }

    // No overlap — fall back to nearest diarized segment by temporal proximity
    let mid = (start + end) / 2.0;
    diarized
        .iter()
        .filter(|seg| seg.speaker_id != 0)
        .min_by(|a, b| {
            let dist_a = (mid - (a.start + a.end) / 2.0).abs();
            let dist_b = (mid - (b.start + b.end) / 2.0).abs();
            dist_a.partial_cmp(&dist_b).unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|seg| (seg.speaker_id, 0.0)) // 0.0 confidence for proximity fallback
        .unwrap_or((0, 0.0))
}

/// Get representative text excerpts for each speaker (for interactive labeling).
pub fn get_speaker_excerpts(
    merged: &[MergedSegment],
) -> HashMap<usize, Vec<String>> {
    let mut excerpts: HashMap<usize, Vec<String>> = HashMap::new();

    for seg in merged {
        let trimmed = seg.text.trim();
        if trimmed.is_empty() || seg.speaker_id == 0 {
            continue;
        }
        let entry = excerpts.entry(seg.speaker_id).or_default();
        if entry.len() < 3 {
            entry.push(trimmed.to_string());
        }
    }

    excerpts
}

/// Prompt the user to assign names to speaker IDs via stdin.
pub fn interactive_label(
    excerpts: &HashMap<usize, Vec<String>>,
) -> Result<HashMap<usize, String>> {
    use std::io::{self, BufRead, Write};

    let mut labels = HashMap::new();
    let mut speaker_ids: Vec<usize> = excerpts.keys().copied().collect();
    speaker_ids.sort();

    eprintln!("\n--- Speaker Identification ---");
    for &id in &speaker_ids {
        eprintln!("\nSpeaker {} excerpts:", id);
        if let Some(texts) = excerpts.get(&id) {
            for (i, text) in texts.iter().enumerate() {
                let preview = if text.len() > 120 { &text[..120] } else { text };
                eprintln!("  {}. \"{}\"", i + 1, preview);
            }
        }
        eprint!("Who is Speaker {}? (name or enter to skip): ", id);
        io::stderr().flush()?;

        let mut line = String::new();
        io::stdin().lock().read_line(&mut line)?;
        let name = line.trim().to_string();
        if !name.is_empty() {
            labels.insert(id, name);
        } else {
            labels.insert(id, format!("Speaker {}", id));
        }
    }
    eprintln!("---\n");

    Ok(labels)
}
