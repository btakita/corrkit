//! Integration tests for mailbox config and path resolution.

mod common;

use tempfile::TempDir;

use corky::config::corky_config;
use corky::resolve;

#[test]
fn test_load_config_basic() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(
        &path,
        r#"
[owner]
github_user = "testuser"
name = "Test User"

[accounts.default]
provider = "gmail"
user = "test@gmail.com"
password = "secret"
labels = ["correspondence"]
default = true

[routing]
for-alex = ["mailboxes/alex"]

[mailboxes.alex]
"#,
    )
    .unwrap();

    let config = corky_config::load_config(Some(&path)).unwrap();
    assert!(config.owner.is_some());
    assert_eq!(config.owner.unwrap().github_user, "testuser");
    assert!(config.accounts.contains_key("default"));
    assert_eq!(config.routing.len(), 1);
    assert_eq!(
        config.routing.get("for-alex").unwrap(),
        &vec!["mailboxes/alex".to_string()]
    );
    assert!(config.mailboxes.contains_key("alex"));
}

#[test]
fn test_load_config_missing_file() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");

    let result = corky_config::load_config(Some(&path));
    assert!(result.is_err());
}

#[test]
fn test_try_load_config_missing_file() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");

    let config = corky_config::try_load_config(Some(&path));
    assert!(config.is_none());
}

#[test]
fn test_load_config_empty_sections() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(
        &path,
        r#"
[owner]
github_user = "testuser"
"#,
    )
    .unwrap();

    let config = corky_config::load_config(Some(&path)).unwrap();
    assert!(config.accounts.is_empty());
    assert!(config.routing.is_empty());
    assert!(config.mailboxes.is_empty());
}

#[test]
fn test_load_config_multiple_mailboxes() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(
        &path,
        r#"
[owner]
github_user = "testuser"

[routing]
for-alice = ["mailboxes/alice"]
for-bob = ["mailboxes/bob"]
shared = ["mailboxes/alice", "mailboxes/bob"]

[mailboxes.alice]

[mailboxes.bob]
auto_send = true
"#,
    )
    .unwrap();

    let config = corky_config::load_config(Some(&path)).unwrap();
    assert_eq!(config.mailboxes.len(), 2);
    assert!(!config.mailboxes["alice"].auto_send);
    assert!(config.mailboxes["bob"].auto_send);

    // shared label routes to two mailboxes
    assert_eq!(config.routing["shared"].len(), 2);
}

#[test]
fn test_load_config_with_watch() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(
        &path,
        r#"
[owner]
github_user = "testuser"

[watch]
poll_interval = 60
notify = true
"#,
    )
    .unwrap();

    let config = corky_config::load_config(Some(&path)).unwrap();
    let watch = config.watch.unwrap();
    assert_eq!(watch.poll_interval, 60);
    assert!(watch.notify);
}

#[test]
fn test_mailbox_dir() {
    let tmp = TempDir::new().unwrap();
    let data = tmp.path().to_path_buf();
    std::env::set_var("CORKY_DATA", data.to_string_lossy().as_ref());

    let dir = resolve::mailbox_dir("AlexUser");
    // Should lowercase the name
    assert!(dir.to_string_lossy().ends_with("mailboxes/alexuser"));

    std::env::remove_var("CORKY_DATA");
}

#[test]
fn test_corky_toml_resolution() {
    let tmp = TempDir::new().unwrap();
    std::env::set_var("CORKY_DATA", tmp.path().to_string_lossy().as_ref());

    // No file exists — should default to .corky.toml path
    let path = resolve::corky_toml();
    assert!(path.to_string_lossy().ends_with(".corky.toml"));

    // Create .corky.toml — should find it
    std::fs::write(tmp.path().join(".corky.toml"), "").unwrap();
    let path = resolve::corky_toml();
    assert!(path.to_string_lossy().ends_with(".corky.toml"));
    // data_dir() gives precedence to local mail/ when present,
    // so the env var path may not be used in the dev checkout.
    if resolve::data_dir() == tmp.path().to_path_buf() {
        assert!(path.exists());
    }

    std::env::remove_var("CORKY_DATA");
}

#[test]
fn test_accounts_loaded_from_corky_toml() {
    let tmp = TempDir::new().unwrap();
    common::write_corky_toml(tmp.path(), "test@example.com");
    let config_path = tmp.path().join(".corky.toml");

    let accounts = corky::accounts::load_accounts(Some(&config_path)).unwrap();
    assert!(accounts.contains_key("default"));
    let acct = accounts.get("default").unwrap();
    assert_eq!(acct.user, "test@example.com");
}

#[test]
fn test_owner_loaded_from_corky_toml() {
    let tmp = TempDir::new().unwrap();
    common::write_corky_toml(tmp.path(), "test@example.com");
    let config_path = tmp.path().join(".corky.toml");

    let owner = corky::accounts::load_owner(Some(&config_path)).unwrap();
    assert_eq!(owner.github_user, "testuser");
}

#[test]
fn test_load_config_routing_with_account_scope() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(
        &path,
        r#"
[owner]
github_user = "testuser"

[routing]
"personal:for-alex" = ["mailboxes/alex"]

[mailboxes.alex]
"#,
    )
    .unwrap();

    let config = corky_config::load_config(Some(&path)).unwrap();
    assert!(config.routing.contains_key("personal:for-alex"));
}
