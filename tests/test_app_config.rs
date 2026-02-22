//! Integration tests for app config / mailbox registry (src/app_config.rs).

mod common;

use corky::app_config;

#[test]
fn test_app_config_dir_returns_path() {
    let dir = app_config::app_config_dir();
    // Should contain "corky" somewhere in the path
    assert!(dir.to_string_lossy().contains("corky"));
}

#[test]
fn test_app_config_path_returns_toml() {
    let path = app_config::app_config_path();
    assert!(path.to_string_lossy().ends_with("config.toml"));
}

#[test]
fn test_resolve_mailbox_no_config() {
    // When asked for a nonexistent mailbox, should error or return None
    // Either way, it shouldn't panic
    let result = app_config::resolve_mailbox(Some("nonexistent-mailbox-xyz"));
    let _ = result;
}

#[test]
fn test_list_mailboxes_no_panic() {
    // Should not panic even if config doesn't exist or is corrupted
    let _ = app_config::list_mailboxes();
}

#[test]
fn test_load_no_panic() {
    // Should not panic even if config doesn't exist or is corrupted
    let _ = app_config::load();
}
