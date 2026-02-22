//! Find threads where the last message is not from the owner.

use anyhow::Result;
use once_cell::sync::Lazy;
use regex::Regex;
use std::path::PathBuf;

static SENDER_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?m)^## (.+?) \u{2014}").unwrap());
static DATE_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"\*\*Last updated\*\*:\s*(\S+)").unwrap());
static LABELS_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"\*\*Labels?\*\*:\s*(.+)").unwrap());

fn last_sender(text: &str) -> String {
    SENDER_RE
        .captures_iter(text)
        .last()
        .map(|cap| cap[1].trim().to_string())
        .unwrap_or_default()
}

fn thread_date(text: &str) -> String {
    DATE_RE
        .captures(text)
        .map(|cap| cap[1].to_string())
        .unwrap_or_default()
}

fn thread_labels(text: &str) -> String {
    LABELS_RE
        .captures(text)
        .map(|cap| cap[1].trim().to_string())
        .unwrap_or_default()
}

/// corky find-unanswered [--from NAME]
pub fn run(from_name: &str) -> Result<()> {
    let conversations = PathBuf::from("conversations");
    if !conversations.exists() {
        eprintln!(
            "No conversations/ directory found. \
             Make sure you're in the shared repo root."
        );
        std::process::exit(1);
    }

    let from_lower = from_name.to_lowercase();

    let mut unanswered: Vec<(String, String, String, String)> = Vec::new(); // (date, labels, file, sender)

    let mut md_files = Vec::new();
    collect_md_files(&conversations, &mut md_files)?;
    md_files.sort();

    for thread_file in &md_files {
        let text = std::fs::read_to_string(thread_file)?;
        let sender = last_sender(&text);
        if !sender.is_empty() && !sender.to_lowercase().contains(&from_lower) {
            let labels = {
                let l = thread_labels(&text);
                if l.is_empty() {
                    thread_file
                        .parent()
                        .and_then(|p| p.file_name())
                        .map(|n| n.to_string_lossy().to_string())
                        .unwrap_or_default()
                } else {
                    l
                }
            };
            let date = {
                let d = thread_date(&text);
                if d.is_empty() {
                    "unknown".to_string()
                } else {
                    d
                }
            };
            let filename = thread_file
                .file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_default();
            unanswered.push((date, labels, filename, sender));
        }
    }

    if unanswered.is_empty() {
        println!("No unanswered threads found.");
        std::process::exit(0);
    }

    // Sort by date descending (newest first)
    unanswered.sort_by(|a, b| b.0.cmp(&a.0));

    println!("Unanswered threads ({}):\n", unanswered.len());
    for (date, labels, filename, sender) in &unanswered {
        println!("  [{}] {}", labels, filename);
        println!("           Last from: {} ({})", sender, date);
        println!();
    }

    Ok(())
}

fn collect_md_files(dir: &std::path::Path, out: &mut Vec<PathBuf>) -> Result<()> {
    if !dir.is_dir() {
        return Ok(());
    }
    for entry in std::fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            collect_md_files(&path, out)?;
        } else if path.extension().and_then(|e| e.to_str()) == Some("md") {
            out.push(path);
        }
    }
    Ok(())
}
