//! Integration tests for corky migrate.

mod common;

use std::sync::Mutex;
use tempfile::TempDir;

use corky::config::corky_config;

static ENV_MUTEX: Mutex<()> = Mutex::new(());

/// Run migrate in an isolated environment.
/// Must hold ENV_MUTEX to avoid cwd races with parallel tests.
fn run_migrate_isolated(data_dir: &std::path::Path) -> anyhow::Result<()> {
    let old_corky = std::env::var("CORKY_DATA").ok();
    let old_cwd = std::env::current_dir().ok();

    std::env::set_var("CORKY_DATA", data_dir.to_string_lossy().as_ref());
    // Change to a dir without correspondence/ to avoid config_dir() returning "."
    let _ = std::env::set_current_dir(data_dir);

    let result = corky::migrate::run();

    // Restore
    if let Some(c) = old_cwd {
        let _ = std::env::set_current_dir(c);
    }
    match old_corky {
        Some(v) => std::env::set_var("CORKY_DATA", v),
        None => std::env::remove_var("CORKY_DATA"),
    }

    result
}

#[test]
fn test_migrate_creates_corky_toml() {
    let _lock = ENV_MUTEX.lock().unwrap();
    let tmp = TempDir::new().unwrap();
    let data_dir = tmp.path().to_path_buf();

    // Create correspondence-like structure
    std::fs::create_dir_all(data_dir.join("conversations")).unwrap();
    std::fs::create_dir_all(
        data_dir.join("collabs").join("alex").join("to").join("conversations"),
    )
    .unwrap();

    // Set up old-style config in data_dir
    common::write_accounts_toml(&data_dir, "test@example.com");
    std::fs::write(
        data_dir.join("collaborators.toml"),
        r#"
[alex]
labels = ["for-alex"]
name = "Alex"
"#,
    )
    .unwrap();

    run_migrate_isolated(&data_dir).unwrap();

    // Verify .corky.toml was created
    let config_path = data_dir.join(".corky.toml");
    assert!(config_path.exists());

    // Verify it can be loaded
    let config = corky_config::load_config(Some(&config_path)).unwrap();
    assert!(config.routing.contains_key("for-alex"));
    assert!(config.mailboxes.contains_key("alex"));

    // Verify directory was moved
    assert!(data_dir.join("mailboxes").join("alex").exists());
}

#[test]
fn test_migrate_fails_if_corky_toml_exists() {
    let _lock = ENV_MUTEX.lock().unwrap();
    let tmp = TempDir::new().unwrap();
    let data_dir = tmp.path().to_path_buf();

    common::write_accounts_toml(&data_dir, "test@example.com");
    std::fs::write(data_dir.join(".corky.toml"), "").unwrap();

    let result = run_migrate_isolated(&data_dir);
    assert!(result.is_err());
}

#[test]
fn test_migrate_fails_if_no_accounts_toml() {
    let _lock = ENV_MUTEX.lock().unwrap();
    let tmp = TempDir::new().unwrap();
    let data_dir = tmp.path().to_path_buf();

    let result = run_migrate_isolated(&data_dir);
    assert!(result.is_err());
}

#[test]
fn test_migrate_without_collaborators() {
    let _lock = ENV_MUTEX.lock().unwrap();
    let tmp = TempDir::new().unwrap();
    let data_dir = tmp.path().to_path_buf();

    common::write_accounts_toml(&data_dir, "test@example.com");
    // Explicitly create empty collaborators.toml
    std::fs::write(data_dir.join("collaborators.toml"), "").unwrap();

    run_migrate_isolated(&data_dir).unwrap();

    let config_path = data_dir.join(".corky.toml");
    assert!(config_path.exists());

    let config = corky_config::load_config(Some(&config_path)).unwrap();
    assert!(config.routing.is_empty());
    assert!(config.mailboxes.is_empty());
}
