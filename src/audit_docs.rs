//! Audit instruction files against the codebase.

use anyhow::Result;
use once_cell::sync::Lazy;
use regex::Regex;
use std::path::{Path, PathBuf};

const LINE_BUDGET: usize = 1000;
static SKIP_PATHS: Lazy<std::collections::HashSet<&str>> =
    Lazy::new(|| [".env"].iter().copied().collect());

static IMPERATIVE_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(?i)\b(use|add|create|run|do|don't|never|must|should|avoid|prefer|ensure|keep|set)\b").unwrap()
});

static TABLE_SEP_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\|[\s:]*-+[\s:]*(\|[\s:]*-+[\s:]*)*\|?\s*$").unwrap()
});

const INFORMATIONAL_HEADINGS: &[&str] = &[
    "project structure",
    "directory layout",
    "architecture",
    "overview",
    "tech stack",
    "sources",
    "bibliography",
    "references",
    "available tools",
    "resources",
];

struct Issue {
    file: String,
    line: usize,
    end_line: usize,
    message: String,
    warning: bool,
}

/// Find the project root by walking up from CWD looking for Cargo.toml.
fn find_root() -> PathBuf {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let mut dir = cwd.as_path();
    loop {
        if dir.join("Cargo.toml").exists() {
            return dir.to_path_buf();
        }
        match dir.parent() {
            Some(p) => dir = p,
            None => {
                eprintln!("Error: could not find Cargo.toml");
                std::process::exit(2);
            }
        }
    }
}

fn find_instruction_files(root: &Path) -> Vec<PathBuf> {
    let patterns = ["AGENTS.md", "README.md"];
    let mut found = std::collections::HashSet::new();

    for pattern in &patterns {
        let path = root.join(pattern);
        if path.exists() {
            found.insert(path);
        }
    }

    // .claude/**/SKILL.md
    if let Ok(entries) = glob::glob(&root.join(".claude/**/SKILL.md").to_string_lossy()) {
        for entry in entries.flatten() {
            found.insert(entry);
        }
    }

    // .agents/**/SKILL.md
    if let Ok(entries) = glob::glob(&root.join(".agents/**/SKILL.md").to_string_lossy()) {
        for entry in entries.flatten() {
            found.insert(entry);
        }
    }

    // .agents/**/AGENTS.md
    if let Ok(entries) = glob::glob(&root.join(".agents/**/AGENTS.md").to_string_lossy()) {
        for entry in entries.flatten() {
            found.insert(entry);
        }
    }

    // src/**/AGENTS.md
    if let Ok(entries) = glob::glob(&root.join("src/**/AGENTS.md").to_string_lossy()) {
        for entry in entries.flatten() {
            found.insert(entry);
        }
    }

    let mut result: Vec<PathBuf> = found.into_iter().collect();
    result.sort();
    result
}

/// Parse file paths from the Project Structure tree block.
fn extract_tree_paths(content: &str) -> Vec<(usize, String)> {
    let mut results = Vec::new();
    let lines: Vec<&str> = content.lines().collect();
    let mut in_section = false;
    let mut in_block = false;
    let mut stack: Vec<(usize, String)> = Vec::new(); // (indent, dirname_with_slash)

    for (i, line) in lines.iter().enumerate() {
        let line_no = i + 1;
        if line.starts_with("## Project Structure") {
            in_section = true;
            continue;
        }
        if in_section && !in_block {
            if line.trim().starts_with("```") {
                in_block = true;
                continue;
            }
            if line.starts_with("## ") {
                break;
            }
            continue;
        }
        if !in_block {
            continue;
        }
        if line.trim().starts_with("```") {
            break;
        }

        let stripped = line.trim_end();
        let trimmed = stripped.trim();
        if trimmed.is_empty() {
            continue;
        }
        let indent = stripped.len() - stripped.trim_start().len();
        let mut name = trimmed.split('#').next().unwrap_or("").trim().to_string();
        if name.is_empty() {
            continue;
        }

        // Strip symlink arrow notation
        if name.contains(" -> ") {
            name = format!("{}/", name.split(" -> ").next().unwrap_or("").trim());
        }

        // Pop deeper/equal entries from stack
        while stack.last().map(|(ind, _)| *ind >= indent).unwrap_or(false) {
            stack.pop();
        }

        if name.ends_with('/') {
            stack.push((indent, name));
        } else {
            let mut parts: Vec<String> = stack.iter().map(|(_, d)| d.clone()).collect();
            parts.push(name);
            let full = parts.join("");
            results.push((line_no, full));
        }
    }

    results
}

fn check_tree_paths(rel: &str, content: &str, root: &Path) -> Vec<Issue> {
    let mut issues = Vec::new();
    let bracket_re = Regex::new(r"\[.*?]").unwrap();
    for (line_no, path) in extract_tree_paths(content) {
        if bracket_re.is_match(&path) {
            continue;
        }
        if SKIP_PATHS.contains(path.as_str()) {
            continue;
        }
        if !root.join(&path).exists() {
            issues.push(Issue {
                file: rel.to_string(),
                line: line_no,
                end_line: 0,
                message: format!("Referenced path does not exist: {}", path),
                warning: false,
            });
        }
    }
    issues
}

fn check_line_budget(files: &[PathBuf], root: &Path) -> (Vec<Issue>, Vec<(String, usize)>, usize) {
    let mut counts = Vec::new();
    let mut total = 0;
    for f in files {
        if let Ok(content) = std::fs::read_to_string(f) {
            let n = content.lines().count();
            let rel = f.strip_prefix(root).unwrap_or(f).to_string_lossy().to_string();
            counts.push((rel, n));
            total += n;
        }
    }
    let mut issues = Vec::new();
    if total > LINE_BUDGET {
        issues.push(Issue {
            file: "(all)".to_string(),
            line: 0,
            end_line: 0,
            message: format!("Over line budget: {} lines (max {})", total, LINE_BUDGET),
            warning: false,
        });
    }
    (issues, counts, total)
}

fn check_staleness(files: &[PathBuf], root: &Path) -> Vec<Issue> {
    let src_dir = root.join("src");
    if !src_dir.exists() {
        return vec![];
    }

    let mut newest_mtime = std::time::SystemTime::UNIX_EPOCH;
    let mut newest_src = PathBuf::new();

    fn scan_rs(dir: &Path, newest: &mut std::time::SystemTime, newest_path: &mut PathBuf) {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    scan_rs(&path, newest, newest_path);
                } else if path.extension().and_then(|e| e.to_str()) == Some("rs") {
                    if let Ok(meta) = path.metadata() {
                        if let Ok(mtime) = meta.modified() {
                            if mtime > *newest {
                                *newest = mtime;
                                *newest_path = path;
                            }
                        }
                    }
                }
            }
        }
    }

    scan_rs(&src_dir, &mut newest_mtime, &mut newest_src);

    let mut issues = Vec::new();
    for doc in files {
        if let Ok(meta) = doc.metadata() {
            if let Ok(doc_mtime) = meta.modified() {
                if doc_mtime < newest_mtime {
                    let rel = doc.strip_prefix(root).unwrap_or(doc).to_string_lossy().to_string();
                    let src_rel = newest_src
                        .strip_prefix(root)
                        .unwrap_or(&newest_src)
                        .to_string_lossy()
                        .to_string();
                    issues.push(Issue {
                        file: rel,
                        line: 0,
                        end_line: 0,
                        message: format!("Older than {} \u{2014} may be stale", src_rel),
                        warning: false,
                    });
                }
            }
        }
    }
    issues
}

fn is_agent_file(rel: &str) -> bool {
    let name = Path::new(rel)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("");
    name == "AGENTS.md" || name == "SKILL.md"
}

/// Return the heading level (1–6) and title text for a markdown heading line.
fn heading_level(line: &str) -> Option<(usize, &str)> {
    let hashes = line.bytes().take_while(|&b| b == b'#').count();
    if hashes == 0 || hashes > 6 {
        return None;
    }
    let rest = &line[hashes..];
    if rest.starts_with(' ') {
        Some((hashes, rest.trim()))
    } else {
        None
    }
}

/// A bullet line that is primarily a link or backtick-enclosed identifier.
fn is_link_bullet(line: &str) -> bool {
    let stripped = line.strip_prefix("- ").or_else(|| line.strip_prefix("* "));
    match stripped {
        Some(rest) => rest.starts_with('[') || rest.starts_with('`'),
        None => false,
    }
}

/// A line that can appear within a link-heavy list block (link bullets, blanks,
/// or sub-section headings).
fn is_list_context(line: &str) -> bool {
    line.trim().is_empty()
        || line.starts_with("### ")
        || line.starts_with("#### ")
        || is_link_bullet(line)
}

fn check_actionable(rel: &str, content: &str) -> Vec<Issue> {
    if !is_agent_file(rel) {
        return vec![];
    }

    let lines: Vec<&str> = content.lines().collect();
    let mut issues = Vec::new();

    // 1. Informational section headings
    for (i, line) in lines.iter().enumerate() {
        if let Some((level, title)) = heading_level(line) {
            let title_lower = title.to_lowercase();
            if INFORMATIONAL_HEADINGS.iter().any(|h| title_lower == *h) {
                let mut end = lines.len();
                for j in (i + 1)..lines.len() {
                    if let Some((next_level, _)) = heading_level(lines[j]) {
                        if next_level <= level {
                            end = j;
                            break;
                        }
                    }
                }
                while end > i + 1 && lines[end - 1].trim().is_empty() {
                    end -= 1;
                }
                issues.push(Issue {
                    file: rel.to_string(),
                    line: i + 1,
                    end_line: end,
                    message: format!(
                        "Informational section \"{}\" \u{2014} consider moving to README.md",
                        title
                    ),
                    warning: true,
                });
            }
        }
    }

    // 2. Large fenced code blocks (> 8 lines) without imperative verb in 2 preceding lines
    {
        let mut i = 0;
        while i < lines.len() {
            if lines[i].trim().starts_with("```") {
                let start = i;
                i += 1;
                while i < lines.len() && !lines[i].trim().starts_with("```") {
                    i += 1;
                }
                let close = i;
                let block_lines = close - start - 1;
                if block_lines > 8 {
                    let check_start = start.saturating_sub(2);
                    let preceding = &lines[check_start..start];
                    let has_imperative = preceding.iter().any(|l| IMPERATIVE_RE.is_match(l));
                    if !has_imperative {
                        issues.push(Issue {
                            file: rel.to_string(),
                            line: start + 1,
                            end_line: if close < lines.len() {
                                close + 1
                            } else {
                                close
                            },
                            message: format!(
                                "Large code block ({} lines) without imperative context \u{2014} consider moving to README.md",
                                block_lines
                            ),
                            warning: true,
                        });
                    }
                }
            }
            i += 1;
        }
    }

    // 3. Large tables (> 5 non-separator rows)
    {
        let mut i = 0;
        while i < lines.len() {
            if lines[i].trim_start().starts_with('|') {
                let start = i;
                let mut rows = 0;
                while i < lines.len() && lines[i].trim_start().starts_with('|') {
                    if !TABLE_SEP_RE.is_match(lines[i].trim()) {
                        rows += 1;
                    }
                    i += 1;
                }
                if rows > 5 {
                    issues.push(Issue {
                        file: rel.to_string(),
                        line: start + 1,
                        end_line: i,
                        message: format!(
                            "Large table ({} rows) \u{2014} consider moving to README.md",
                            rows
                        ),
                        warning: true,
                    });
                }
                continue;
            }
            i += 1;
        }
    }

    // 4. Link-heavy bullet lists (> 10 consecutive link/backtick bullets)
    {
        let mut i = 0;
        while i < lines.len() {
            if is_link_bullet(lines[i]) {
                let start = i;
                let mut count = 0;
                while i < lines.len() && is_list_context(lines[i]) {
                    if is_link_bullet(lines[i]) {
                        count += 1;
                    }
                    i += 1;
                }
                let mut end = i;
                while end > start && lines[end - 1].trim().is_empty() {
                    end -= 1;
                }
                if count > 10 {
                    issues.push(Issue {
                        file: rel.to_string(),
                        line: start + 1,
                        end_line: end,
                        message: format!(
                            "Link-heavy list ({} items) \u{2014} consider moving to README.md",
                            count
                        ),
                        warning: true,
                    });
                }
                continue;
            }
            i += 1;
        }
    }

    issues
}

pub fn run() -> Result<()> {
    println!("Auditing docs...\n");

    let root = find_root();
    let files = find_instruction_files(&root);
    let mut issues: Vec<Issue> = Vec::new();

    for doc in &files {
        let rel = doc
            .strip_prefix(&root)
            .unwrap_or(doc)
            .to_string_lossy()
            .to_string();
        if let Ok(content) = std::fs::read_to_string(doc) {
            issues.extend(check_tree_paths(&rel, &content, &root));
            issues.extend(check_actionable(&rel, &content));
        }
    }

    let (budget_issues, counts, total) = check_line_budget(&files, &root);
    issues.extend(budget_issues);
    issues.extend(check_staleness(&files, &root));

    for issue in &issues {
        let mut loc = format!("  {}", issue.file);
        if issue.line > 0 {
            if issue.end_line > issue.line {
                loc.push_str(&format!(":{}-{}", issue.line, issue.end_line));
            } else {
                loc.push_str(&format!(":{}", issue.line));
            }
        }
        let marker = if issue.warning { "\u{26a0}" } else { "\u{2717}" };
        println!("{:<50} {} {}", loc, marker, issue.message);
    }

    let mark = if total <= LINE_BUDGET {
        "\u{2713}"
    } else {
        "\u{2717}"
    };
    println!(
        "\nCombined instruction files: {} lines (budget: {}) {}",
        total, LINE_BUDGET, mark
    );
    for (name, n) in &counts {
        println!("  {}: {}", name, n);
    }

    let n = issues.len();
    if n > 0 {
        println!("\nFound {} issue(s)", n);
        std::process::exit(1);
    } else {
        println!("\nNo issues found \u{2713}");
    }

    Ok(())
}
