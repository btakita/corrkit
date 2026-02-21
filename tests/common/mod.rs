//! Shared test fixtures and helpers.

#![allow(dead_code)]

use std::path::{Path, PathBuf};
use tempfile::TempDir;

/// Create a temporary data directory with the standard corrkit structure.
pub fn temp_data_dir() -> (TempDir, PathBuf) {
    let tmp = TempDir::new().expect("failed to create temp dir");
    let data_dir = tmp.path().to_path_buf();

    for sub in &["conversations", "drafts", "contacts"] {
        std::fs::create_dir_all(data_dir.join(sub)).unwrap();
    }

    (tmp, data_dir)
}

/// Create a minimal accounts.toml for testing.
pub fn write_accounts_toml(dir: &Path, user: &str) {
    let content = format!(
        r#"[owner]
github_user = "testuser"
name = "Test User"

[accounts.default]
provider = "gmail"
user = "{user}"
password = "testpassword"
labels = ["correspondence"]
default = true
"#,
        user = user,
    );
    std::fs::write(dir.join("accounts.toml"), content).unwrap();
}

/// Create an empty collaborators.toml.
pub fn write_empty_collaborators(dir: &Path) {
    std::fs::write(dir.join("collaborators.toml"), "").unwrap();
}

/// Create an empty contacts.toml.
pub fn write_empty_contacts(dir: &Path) {
    std::fs::write(dir.join("contacts.toml"), "").unwrap();
}
