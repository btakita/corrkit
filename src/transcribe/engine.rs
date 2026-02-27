//! Whisper-rs transcription engine.

use anyhow::{bail, Result};
use std::path::Path;
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

use super::audio;
use super::model;

/// Run transcription on an audio file.
///
/// Outputs timestamped text to stdout or a file.
/// If `speakers` is non-empty, uses whisper's speaker turn detection to label segments.
/// If `diarize` is true, uses pyannote-rs for speaker diarization (requires `diarize` feature).
pub fn run(
    file: &Path,
    model_name: Option<&str>,
    language: Option<&str>,
    output: Option<&str>,
    speakers: &[String],
    diarize: bool,
) -> Result<()> {
    if !file.exists() {
        bail!("Audio file not found: {}", file.display());
    }

    // Load config for defaults
    let config = crate::config::corky_config::try_load_config(None);
    let tc = config.as_ref().and_then(|c| c.transcription.as_ref());

    let model_name = model_name
        .or(tc.map(|t| t.model.as_str()))
        .unwrap_or("large-v3-turbo");
    let language = language.or(tc.and_then(|t| {
        if t.language.is_empty() { None } else { Some(t.language.as_str()) }
    }));
    let cache_dir = tc.and_then(|t| {
        if t.model_path.is_empty() { None } else { Some(t.model_path.as_str()) }
    });

    // Resolve model
    let model_path = model::resolve_model_path(model_name, cache_dir)?;

    // Decode audio
    eprintln!("Decoding audio: {}", file.display());
    let samples = audio::decode_audio(file)?;
    let duration_secs = samples.len() as f64 / 16000.0;
    eprintln!(
        "Audio: {:.1}s ({} samples at 16kHz mono)",
        duration_secs,
        samples.len()
    );

    // Load whisper model
    eprintln!("Loading model: {}", model_path.display());
    let ctx = WhisperContext::new_with_params(
        model_path.to_str().unwrap_or(""),
        WhisperContextParameters::default(),
    )
    .map_err(|e| anyhow::anyhow!("Failed to load whisper model: {:?}", e))?;

    // Configure transcription
    let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
    if let Some(lang) = language {
        params.set_language(Some(lang));
    }
    params.set_print_progress(true);
    params.set_print_realtime(false);
    params.set_print_timestamps(false);
    // Enable tdrz speaker turn detection when speakers are provided
    if !speakers.is_empty() {
        params.set_tdrz_enable(true);
    }

    // Run inference
    eprintln!("Transcribing...");
    let start = std::time::Instant::now();

    let mut state = ctx
        .create_state()
        .map_err(|e| anyhow::anyhow!("Failed to create whisper state: {:?}", e))?;
    state
        .full(params, &samples)
        .map_err(|e| anyhow::anyhow!("Transcription failed: {:?}", e))?;

    let elapsed = start.elapsed();
    let n_segments = state.full_n_segments();

    eprintln!(
        "Done. {} segments in {:.1}s (speed: {:.1}x realtime)",
        n_segments,
        elapsed.as_secs_f64(),
        duration_secs / elapsed.as_secs_f64()
    );

    // Format output
    let text = if diarize {
        #[cfg(feature = "diarize")]
        {
            format_diarized(&state, n_segments, &samples, speakers, duration_secs, cache_dir)?
        }
        #[cfg(not(feature = "diarize"))]
        {
            bail!(
                "Diarization support not compiled.\n\
                 Rebuild with: cargo install corky --features diarize"
            );
        }
    } else if speakers.is_empty() {
        format_plain(&state, n_segments)?
    } else {
        format_speakers(&state, n_segments, speakers, duration_secs)?
    };

    // Output
    if let Some(out_path) = output {
        std::fs::write(out_path, &text)?;
        eprintln!("Written to: {}", out_path);
    } else {
        print!("{}", text);
    }

    Ok(())
}

/// Plain timestamped output (no speaker labels).
fn format_plain(state: &whisper_rs::WhisperState, n_segments: i32) -> Result<String> {
    let mut text = String::new();
    for i in 0..n_segments {
        let segment = state
            .get_segment(i)
            .ok_or_else(|| anyhow::anyhow!("Failed to get segment {}", i))?;

        let t0 = segment.start_timestamp();
        let t1 = segment.end_timestamp();
        let segment_text = segment
            .to_str()
            .map_err(|e| anyhow::anyhow!("Failed to get segment text: {:?}", e))?;

        text.push_str(&format!(
            "[{} --> {}] {}\n",
            format_timestamp(t0),
            format_timestamp(t1),
            segment_text.trim()
        ));
    }
    Ok(text)
}

/// Speaker-labeled markdown output using whisper's tdrz speaker turn detection.
fn format_speakers(
    state: &whisper_rs::WhisperState,
    n_segments: i32,
    speakers: &[String],
    duration_secs: f64,
) -> Result<String> {
    let mut text = String::new();

    // YAML frontmatter
    text.push_str("---\n");
    text.push_str(&format!("date: {}\n", chrono::Local::now().format("%Y-%m-%d")));
    text.push_str("type: phone-call\n");
    text.push_str("participants:\n");
    for s in speakers {
        text.push_str(&format!("  - {}\n", s));
    }
    let mins = (duration_secs / 60.0).floor() as u32;
    let secs = (duration_secs % 60.0).floor() as u32;
    text.push_str(&format!("duration: \"{}:{:02}\"\n", mins, secs));
    text.push_str("---\n\n");

    let mut current_speaker_idx: usize = 0;
    let mut block_start: i64 = 0;
    #[allow(unused_assignments)]
    let mut block_end: i64 = 0;
    let mut block_text = String::new();
    let mut block_active = false;

    for i in 0..n_segments {
        let segment = state
            .get_segment(i)
            .ok_or_else(|| anyhow::anyhow!("Failed to get segment {}", i))?;

        let t0 = segment.start_timestamp();
        let t1 = segment.end_timestamp();
        let segment_text = segment
            .to_str()
            .map_err(|e| anyhow::anyhow!("Failed to get segment text: {:?}", e))?;
        let is_turn = segment.next_segment_speaker_turn();

        if !block_active {
            block_start = t0;
            block_active = true;
        }
        block_end = t1;

        let trimmed = segment_text.trim();
        if !trimmed.is_empty() {
            if !block_text.is_empty() {
                block_text.push(' ');
            }
            block_text.push_str(trimmed);
        }

        // Flush block on speaker turn or last segment
        if is_turn || i == n_segments - 1 {
            if !block_text.is_empty() {
                let speaker = &speakers[current_speaker_idx % speakers.len()];
                text.push_str(&format!(
                    "**{}** [{} → {}]\n{}\n\n",
                    speaker,
                    format_timestamp(block_start),
                    format_timestamp(block_end),
                    block_text
                ));
            }

            if is_turn {
                current_speaker_idx += 1;
            }
            block_active = false;
            block_text.clear();
        }
    }

    Ok(text)
}

/// Collect whisper segments as structured data (centisecond timestamps + text).
fn collect_whisper_segments(
    state: &whisper_rs::WhisperState,
    n_segments: i32,
) -> Result<Vec<(i64, i64, String)>> {
    let mut result = Vec::new();
    for i in 0..n_segments {
        let segment = state
            .get_segment(i)
            .ok_or_else(|| anyhow::anyhow!("Failed to get segment {}", i))?;
        let t0 = segment.start_timestamp();
        let t1 = segment.end_timestamp();
        let text = segment
            .to_str()
            .map_err(|e| anyhow::anyhow!("Failed to get segment text: {:?}", e))?
            .to_string();
        result.push((t0, t1, text));
    }
    Ok(result)
}

/// Diarized speaker-labeled output using pyannote-rs.
#[cfg(feature = "diarize")]
fn format_diarized(
    state: &whisper_rs::WhisperState,
    n_segments: i32,
    samples: &[f32],
    speakers: &[String],
    duration_secs: f64,
    cache_dir: Option<&str>,
) -> Result<String> {
    use super::diarize;

    // Collect whisper transcript segments
    let whisper_segs = collect_whisper_segments(state, n_segments)?;

    // Run pyannote diarization
    let max_speakers = if speakers.is_empty() { 6 } else { speakers.len() };
    let diarized = diarize::diarize(samples, 16000, max_speakers, cache_dir)?;

    // Merge whisper text with diarization speaker labels
    let merged = diarize::merge_speakers(&whisper_segs, &diarized, 16000);

    // Determine speaker names
    let speaker_labels = if speakers.is_empty() {
        // Interactive: show excerpts and prompt for names
        let excerpts = diarize::get_speaker_excerpts(&merged);
        if excerpts.is_empty() {
            std::collections::HashMap::new()
        } else {
            diarize::interactive_label(&excerpts)?
        }
    } else {
        // Map speaker IDs to provided names in order of first appearance
        let mut seen_order: Vec<usize> = Vec::new();
        for seg in &merged {
            if seg.speaker_id != 0 && !seen_order.contains(&seg.speaker_id) {
                seen_order.push(seg.speaker_id);
            }
        }
        let mut labels = std::collections::HashMap::new();
        for (i, &id) in seen_order.iter().enumerate() {
            let name = speakers.get(i).cloned().unwrap_or_else(|| format!("Speaker {}", id));
            labels.insert(id, name);
        }
        labels
    };

    // Build output
    let mut text = String::new();

    // YAML frontmatter
    text.push_str("---\n");
    text.push_str(&format!("date: {}\n", chrono::Local::now().format("%Y-%m-%d")));
    text.push_str("type: phone-call\n");
    text.push_str("participants:\n");
    let mut participant_names: Vec<&String> = speaker_labels.values().collect();
    participant_names.sort();
    for name in &participant_names {
        text.push_str(&format!("  - {}\n", name));
    }
    let mins = (duration_secs / 60.0).floor() as u32;
    let secs = (duration_secs % 60.0).floor() as u32;
    text.push_str(&format!("duration: \"{}:{:02}\"\n", mins, secs));
    text.push_str("---\n\n");

    // Group consecutive segments by speaker into blocks
    let mut current_speaker: Option<usize> = None;
    let mut block_start: i64 = 0;
    let mut block_end: i64 = 0;
    let mut block_text = String::new();
    let mut block_confidence_sum: f64 = 0.0;
    let mut block_confidence_count: usize = 0;

    for (i, seg) in merged.iter().enumerate() {
        let speaker_changed = current_speaker != Some(seg.speaker_id);
        let is_last = i == merged.len() - 1;

        if speaker_changed && !block_text.is_empty() {
            // Flush previous block
            let speaker_name = current_speaker
                .and_then(|id| speaker_labels.get(&id))
                .map(|s| s.as_str())
                .unwrap_or("Unknown");
            let avg_conf = if block_confidence_count > 0 {
                block_confidence_sum / block_confidence_count as f64
            } else {
                0.0
            };
            text.push_str(&format!(
                "**{}** ({:.2}) [{} → {}]\n{}\n\n",
                speaker_name,
                avg_conf,
                format_timestamp(block_start),
                format_timestamp(block_end),
                block_text.trim()
            ));
            block_text.clear();
            block_confidence_sum = 0.0;
            block_confidence_count = 0;
        }

        if speaker_changed {
            current_speaker = Some(seg.speaker_id);
            block_start = seg.t0;
        }
        block_end = seg.t1;
        block_confidence_sum += seg.confidence as f64;
        block_confidence_count += 1;

        let trimmed = seg.text.trim();
        if !trimmed.is_empty() {
            if !block_text.is_empty() {
                block_text.push(' ');
            }
            block_text.push_str(trimmed);
        }

        if is_last && !block_text.is_empty() {
            let speaker_name = current_speaker
                .and_then(|id| speaker_labels.get(&id))
                .map(|s| s.as_str())
                .unwrap_or("Unknown");
            let avg_conf = if block_confidence_count > 0 {
                block_confidence_sum / block_confidence_count as f64
            } else {
                0.0
            };
            text.push_str(&format!(
                "**{}** ({:.2}) [{} → {}]\n{}\n\n",
                speaker_name,
                avg_conf,
                format_timestamp(block_start),
                format_timestamp(block_end),
                block_text.trim()
            ));
        }
    }

    Ok(text)
}

/// Format centisecond timestamp as HH:MM:SS.mmm
fn format_timestamp(cs: i64) -> String {
    let total_ms = cs * 10;
    let hours = total_ms / 3_600_000;
    let minutes = (total_ms % 3_600_000) / 60_000;
    let seconds = (total_ms % 60_000) / 1_000;
    let ms = total_ms % 1_000;
    format!("{:02}:{:02}:{:02}.{:03}", hours, minutes, seconds, ms)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn timestamp_formatting() {
        assert_eq!(format_timestamp(0), "00:00:00.000");
        assert_eq!(format_timestamp(100), "00:00:01.000");
        assert_eq!(format_timestamp(6000), "00:01:00.000");
        assert_eq!(format_timestamp(360000), "01:00:00.000");
        assert_eq!(format_timestamp(365432), "01:00:54.320");
    }
}
