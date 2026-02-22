//! Validate draft markdown files.

use anyhow::Result;
use once_cell::sync::Lazy;
use regex::Regex;
use std::collections::HashMap;
use std::path::{Path, PathBuf};

static META_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"(?m)^\*\*(.+?)\*\*:\s*(.+)$").unwrap());

const REQUIRED_FIELDS: &[&str] = &["To"];
const RECOMMENDED_FIELDS: &[&str] = &["Status", "Author"];
const VALID_STATUSES: &[&str] = &["draft", "review", "approved", "sent"];

/// Validate a draft file. Returns list of issues (empty = valid).
pub fn validate_draft(path: &Path) -> Vec<String> {
    let mut issues = Vec::new();

    if !path.exists() {
        return vec![format!("File not found: {}", path.display())];
    }

    let text = match std::fs::read_to_string(path) {
        Ok(t) => t,
        Err(e) => return vec![format!("Cannot read {}: {}", path.display(), e)],
    };
    let lines: Vec<&str> = text.split('\n').collect();

    // Check for subject heading
    let has_subject = lines.iter().any(|line| line.starts_with("# "));
    if !has_subject {
        issues.push("Missing subject: no '# Subject' heading found".to_string());
    }

    // Parse metadata fields
    let mut meta: HashMap<String, String> = HashMap::new();
    for cap in META_RE.captures_iter(&text) {
        meta.insert(cap[1].to_string(), cap[2].trim().to_string());
    }

    // Required fields
    for field in REQUIRED_FIELDS {
        if !meta.contains_key(*field) {
            issues.push(format!("Missing required field: **{}**", field));
        }
    }

    // Recommended fields (warn, don't error)
    for field in RECOMMENDED_FIELDS {
        if !meta.contains_key(*field) {
            issues.push(format!(
                "Warning: missing recommended field: **{}**",
                field
            ));
        }
    }

    // Status validation
    let status = meta
        .get("Status")
        .map(|s| s.to_lowercase())
        .unwrap_or_default();
    if !status.is_empty() && !VALID_STATUSES.contains(&status.as_str()) {
        issues.push(format!(
            "Invalid status '{}'. Valid: {}",
            meta.get("Status").unwrap(),
            VALID_STATUSES.to_vec().join(", ")
        ));
    }

    if status == "draft" {
        issues.push(
            "Warning: Status is 'draft'. Set to 'review' when ready for review".to_string(),
        );
    }

    // Check for --- separator
    let has_separator = lines.iter().any(|line| line.trim() == "---");
    if !has_separator {
        issues.push("Missing '---' separator between metadata and body".to_string());
    }

    // Check body exists after separator
    if has_separator {
        if let Some(sep_idx) = lines.iter().position(|line| line.trim() == "---") {
            let body: String = lines[sep_idx + 1..].join("\n");
            if body.trim().is_empty() {
                issues.push("Warning: empty body after --- separator".to_string());
            }
        }
    }

    issues
}

/// corky validate-draft FILE [FILE...]
pub fn run(files: &[PathBuf]) -> Result<()> {
    let mut all_ok = true;

    for path in files {
        let issues = validate_draft(path);
        if !issues.is_empty() {
            all_ok = false;
            let errors: Vec<_> = issues
                .iter()
                .filter(|i| !i.starts_with("Warning:"))
                .collect();
            let warnings: Vec<_> = issues.iter().filter(|i| i.starts_with("Warning:")).collect();
            println!("{}:", path.display());
            for issue in errors {
                println!("  ERROR: {}", issue);
            }
            for issue in warnings {
                println!("  {}", issue);
            }
            println!();
        } else {
            println!("{}: OK", path.display());
        }
    }

    if !all_ok {
        std::process::exit(1);
    }
    Ok(())
}
