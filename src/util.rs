use once_cell::sync::Lazy;
use regex::Regex;
use std::process::Command;

static SLUG_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"[^a-z0-9]+").unwrap());
static THREAD_KEY_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?i)^(re|fwd?):\s*").unwrap());

/// Generate a URL-safe slug from text.
///
/// Lowercases, replaces non-alphanumeric runs with hyphens,
/// trims hyphens, truncates to 60 chars. Returns "untitled" if empty.
pub fn slugify(text: &str) -> String {
    let lower = text.to_lowercase();
    let slugged = SLUG_RE.replace_all(&lower, "-");
    let trimmed = slugged.trim_matches('-');
    let truncated = if trimmed.len() > 60 {
        // Don't split in the middle of a multi-byte char
        let mut end = 60;
        while !trimmed.is_char_boundary(end) && end > 0 {
            end -= 1;
        }
        &trimmed[..end]
    } else {
        trimmed
    };
    if truncated.is_empty() {
        "untitled".to_string()
    } else {
        truncated.to_string()
    }
}

/// Derive a thread key from a subject line.
///
/// Strips one `Re:` or `Fwd:` prefix (case-insensitive), then lowercases.
pub fn thread_key_from_subject(subject: &str) -> String {
    let trimmed = subject.trim().to_lowercase();
    THREAD_KEY_RE.replace(&trimmed, "").to_string()
}

/// Run a shell command, returning (stdout, stderr, exit_code).
pub fn run_cmd(args: &[&str]) -> anyhow::Result<(String, String, i32)> {
    let output = Command::new(args[0]).args(&args[1..]).output()?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let code = output.status.code().unwrap_or(-1);
    Ok((stdout, stderr, code))
}

/// Run a shell command, printing it first. Returns Ok on success, Err on failure.
pub fn run_cmd_checked(args: &[&str]) -> anyhow::Result<String> {
    let cmd_str = args.join(" ");
    println!("  $ {}", cmd_str);
    let (stdout, stderr, code) = run_cmd(args)?;
    if code != 0 {
        anyhow::bail!("Command failed (exit {}): {}\n{}", code, cmd_str, stderr.trim());
    }
    Ok(stdout)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_slugify_basic() {
        assert_eq!(slugify("Hello World"), "hello-world");
    }

    #[test]
    fn test_slugify_special_chars() {
        assert_eq!(slugify("Re: My Important Email!"), "re-my-important-email");
    }

    #[test]
    fn test_slugify_truncation() {
        let long = "a".repeat(100);
        assert_eq!(slugify(&long).len(), 60);
    }

    #[test]
    fn test_slugify_empty() {
        assert_eq!(slugify(""), "untitled");
        assert_eq!(slugify("!!!"), "untitled");
    }

    #[test]
    fn test_thread_key_strips_re() {
        assert_eq!(
            thread_key_from_subject("Re: Hello World"),
            "hello world"
        );
    }

    #[test]
    fn test_thread_key_strips_fwd() {
        assert_eq!(
            thread_key_from_subject("Fwd: Hello World"),
            "hello world"
        );
    }

    #[test]
    fn test_thread_key_strips_fw() {
        assert_eq!(
            thread_key_from_subject("Fw: Hello World"),
            "hello world"
        );
    }

    #[test]
    fn test_thread_key_case_insensitive() {
        assert_eq!(
            thread_key_from_subject("RE: Hello World"),
            "hello world"
        );
    }

    #[test]
    fn test_thread_key_no_prefix() {
        assert_eq!(
            thread_key_from_subject("Hello World"),
            "hello world"
        );
    }
}
