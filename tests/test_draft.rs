//! Integration tests for draft parsing (src/draft/mod.rs).

mod common;

use tempfile::TempDir;

use corky::draft::parse_draft;

fn write_draft(dir: &std::path::Path, filename: &str, content: &str) -> std::path::PathBuf {
    let path = dir.join(filename);
    std::fs::write(&path, content).unwrap();
    path
}

#[test]
fn test_parse_draft_basic() {
    let tmp = TempDir::new().unwrap();
    let path = write_draft(
        tmp.path(),
        "2025-02-10-test.md",
        r#"# Test Subject

**To**: alice@example.com
**CC**: bob@example.com
**Status**: draft
**Author**: brian

---

Hello Alice,

This is a test draft.
"#,
    );

    let (meta, subject, body) = parse_draft(&path).unwrap();

    assert_eq!(subject, "Test Subject");
    assert_eq!(meta["To"], "alice@example.com");
    assert_eq!(meta["CC"], "bob@example.com");
    assert_eq!(meta["Status"], "draft");
    assert_eq!(meta["Author"], "brian");
    assert!(body.contains("Hello Alice"));
    assert!(body.contains("This is a test draft."));
}

#[test]
fn test_parse_draft_with_account_and_from() {
    let tmp = TempDir::new().unwrap();
    let path = write_draft(
        tmp.path(),
        "2025-02-10-with-account.md",
        r#"# Follow Up

**To**: recipient@example.com
**Status**: review
**Account**: personal
**From**: me@gmail.com
**In-Reply-To**: <abc123@mail.example.com>

---

Following up on our conversation.
"#,
    );

    let (meta, subject, body) = parse_draft(&path).unwrap();

    assert_eq!(subject, "Follow Up");
    assert_eq!(meta["To"], "recipient@example.com");
    assert_eq!(meta["Status"], "review");
    assert_eq!(meta["Account"], "personal");
    assert_eq!(meta["From"], "me@gmail.com");
    assert_eq!(meta["In-Reply-To"], "<abc123@mail.example.com>");
    assert!(body.contains("Following up"));
}

#[test]
fn test_parse_draft_missing_to_field() {
    let tmp = TempDir::new().unwrap();
    let path = write_draft(
        tmp.path(),
        "2025-02-10-no-to.md",
        r#"# No Recipient

**Status**: draft
**Author**: brian

---

This draft has no To field.
"#,
    );

    let result = parse_draft(&path);
    assert!(result.is_err());
    let err_msg = result.unwrap_err().to_string();
    assert!(err_msg.contains("To"));
}

#[test]
fn test_parse_draft_missing_separator() {
    let tmp = TempDir::new().unwrap();
    let path = write_draft(
        tmp.path(),
        "2025-02-10-no-sep.md",
        r#"# Missing Separator

**To**: alice@example.com
**Status**: draft

No separator before body.
"#,
    );

    let result = parse_draft(&path);
    assert!(result.is_err());
    let err_msg = result.unwrap_err().to_string();
    assert!(err_msg.contains("---"));
}

#[test]
fn test_parse_draft_minimal() {
    let tmp = TempDir::new().unwrap();
    let path = write_draft(
        tmp.path(),
        "2025-02-10-minimal.md",
        r#"# Minimal

**To**: someone@example.com

---

Body here.
"#,
    );

    let (meta, subject, body) = parse_draft(&path).unwrap();
    assert_eq!(subject, "Minimal");
    assert_eq!(meta["To"], "someone@example.com");
    assert!(body.contains("Body here."));
}

#[test]
fn test_parse_draft_multiline_body() {
    let tmp = TempDir::new().unwrap();
    let path = write_draft(
        tmp.path(),
        "2025-02-10-multiline.md",
        r#"# Multiline Body

**To**: someone@example.com
**Status**: draft

---

First paragraph.

Second paragraph with more detail.

Best regards,
Test User
"#,
    );

    let (_, _, body) = parse_draft(&path).unwrap();
    assert!(body.contains("First paragraph."));
    assert!(body.contains("Second paragraph"));
    assert!(body.contains("Best regards,"));
    assert!(body.contains("Test User"));
}

#[test]
fn test_parse_draft_status_values() {
    let statuses = ["draft", "review", "approved", "sent"];
    let tmp = TempDir::new().unwrap();

    for status in &statuses {
        let path = write_draft(
            tmp.path(),
            &format!("status-{}.md", status),
            &format!(
                r#"# Status Test

**To**: someone@example.com
**Status**: {}

---

Body.
"#,
                status
            ),
        );

        let (meta, _, _) = parse_draft(&path).unwrap();
        assert_eq!(meta["Status"], *status);
    }
}

#[test]
fn test_parse_draft_file_not_found() {
    let result = parse_draft(std::path::Path::new("/nonexistent/path/draft.md"));
    assert!(result.is_err());
}

#[test]
fn test_parse_draft_empty_body() {
    let tmp = TempDir::new().unwrap();
    let path = write_draft(
        tmp.path(),
        "2025-02-10-empty-body.md",
        r#"# Empty Body

**To**: someone@example.com

---
"#,
    );

    let (_, subject, body) = parse_draft(&path).unwrap();
    assert_eq!(subject, "Empty Body");
    assert!(body.is_empty());
}

#[test]
fn test_parse_draft_optional_fields_absent() {
    let tmp = TempDir::new().unwrap();
    let path = write_draft(
        tmp.path(),
        "2025-02-10-optional.md",
        r#"# Minimal Fields

**To**: someone@example.com

---

Just the essentials.
"#,
    );

    let (meta, _, _) = parse_draft(&path).unwrap();

    // Optional fields should not be present
    assert!(!meta.contains_key("CC"));
    assert!(!meta.contains_key("Status"));
    assert!(!meta.contains_key("Author"));
    assert!(!meta.contains_key("Account"));
    assert!(!meta.contains_key("From"));
    assert!(!meta.contains_key("In-Reply-To"));
}

#[test]
fn test_parse_draft_preserves_formatting() {
    let tmp = TempDir::new().unwrap();
    let path = write_draft(
        tmp.path(),
        "2025-02-10-formatting.md",
        r#"# Formatted Draft

**To**: someone@example.com

---

Dear Alice,

Here are the items:

- Item 1
- Item 2
- Item 3

Thanks!
"#,
    );

    let (_, _, body) = parse_draft(&path).unwrap();
    assert!(body.contains("- Item 1"));
    assert!(body.contains("- Item 2"));
    assert!(body.contains("- Item 3"));
}
