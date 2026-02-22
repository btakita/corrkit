//! Integration tests for contact config parsing (src/config/contact.rs).

mod common;

use tempfile::TempDir;

use corky::config::contact::{self, Contact};

#[test]
fn test_load_contacts_empty_file() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(&path, "").unwrap();

    let contacts = contact::load_contacts(Some(&path)).unwrap();
    assert!(contacts.is_empty());
}

#[test]
fn test_load_contacts_missing_file() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join("nonexistent.toml");

    let contacts = contact::load_contacts(Some(&path)).unwrap();
    assert!(contacts.is_empty());
}

#[test]
fn test_load_contacts_basic() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(
        &path,
        r#"
[contacts.alice]
emails = ["alice@example.com", "alice@work.com"]
labels = ["correspondence"]
account = "personal"
"#,
    )
    .unwrap();

    let contacts = contact::load_contacts(Some(&path)).unwrap();
    assert_eq!(contacts.len(), 1);

    let alice = contacts.get("alice").unwrap();
    assert_eq!(alice.emails, vec!["alice@example.com", "alice@work.com"]);
    assert_eq!(alice.labels, vec!["correspondence"]);
    assert_eq!(alice.account, "personal");
}

#[test]
fn test_load_contacts_multiple() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(
        &path,
        r#"
[contacts.alice]
emails = ["alice@example.com"]

[contacts.bob]
emails = ["bob@example.com"]
labels = ["work"]

[contacts.charlie]
emails = ["charlie@example.com"]
account = "work"
"#,
    )
    .unwrap();

    let contacts = contact::load_contacts(Some(&path)).unwrap();
    assert_eq!(contacts.len(), 3);
    assert!(contacts.contains_key("alice"));
    assert!(contacts.contains_key("bob"));
    assert!(contacts.contains_key("charlie"));
}

#[test]
fn test_load_contacts_default_fields() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(
        &path,
        r#"
[contacts.minimal]
emails = ["min@example.com"]
"#,
    )
    .unwrap();

    let contacts = contact::load_contacts(Some(&path)).unwrap();
    let minimal = contacts.get("minimal").unwrap();
    assert_eq!(minimal.emails, vec!["min@example.com"]);
    assert!(minimal.labels.is_empty());
    assert!(minimal.account.is_empty());
}

#[test]
fn test_save_contact() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(&path, "").unwrap();

    let alice = Contact {
        emails: vec!["alice@example.com".to_string()],
        labels: vec!["correspondence".to_string()],
        account: "personal".to_string(),
    };

    contact::save_contact("alice", &alice, Some(&path)).unwrap();

    let content = std::fs::read_to_string(&path).unwrap();
    assert!(content.contains("[contacts.alice]"));
    assert!(content.contains("\"alice@example.com\""));
    assert!(content.contains("\"correspondence\""));
    assert!(content.contains("account = \"personal\""));
}

#[test]
fn test_save_contact_multiple_emails() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(&path, "").unwrap();

    let bob = Contact {
        emails: vec![
            "bob@work.com".to_string(),
            "bob@personal.com".to_string(),
        ],
        labels: vec![],
        account: String::new(),
    };

    contact::save_contact("bob", &bob, Some(&path)).unwrap();

    let content = std::fs::read_to_string(&path).unwrap();
    assert!(content.contains("\"bob@work.com\""));
    assert!(content.contains("\"bob@personal.com\""));
}

#[test]
fn test_save_and_reload_contacts() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(&path, "").unwrap();

    let alice = Contact {
        emails: vec!["alice@example.com".to_string()],
        labels: vec!["inbox".to_string(), "vip".to_string()],
        account: "personal".to_string(),
    };
    let bob = Contact {
        emails: vec!["bob@work.com".to_string()],
        labels: vec![],
        account: String::new(),
    };

    contact::save_contact("alice", &alice, Some(&path)).unwrap();
    contact::save_contact("bob", &bob, Some(&path)).unwrap();
    let reloaded = contact::load_contacts(Some(&path)).unwrap();

    assert_eq!(reloaded.len(), 2);

    let alice = reloaded.get("alice").unwrap();
    assert_eq!(alice.emails, vec!["alice@example.com"]);
    assert_eq!(alice.labels, vec!["inbox", "vip"]);
    assert_eq!(alice.account, "personal");

    let bob = reloaded.get("bob").unwrap();
    assert_eq!(bob.emails, vec!["bob@work.com"]);
    assert!(bob.labels.is_empty());
    assert!(bob.account.is_empty());
}

#[test]
fn test_load_contacts_no_contacts_section() {
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

    let contacts = contact::load_contacts(Some(&path)).unwrap();
    assert!(contacts.is_empty());
}

#[test]
fn test_contact_no_emails() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(
        &path,
        r#"
[contacts.no-email]
labels = ["test"]
"#,
    )
    .unwrap();

    let contacts = contact::load_contacts(Some(&path)).unwrap();
    let no_email = contacts.get("no-email").unwrap();
    assert!(no_email.emails.is_empty());
    assert_eq!(no_email.labels, vec!["test"]);
}

#[test]
fn test_save_contact_preserves_existing_config() {
    let tmp = TempDir::new().unwrap();
    let path = tmp.path().join(".corky.toml");
    std::fs::write(
        &path,
        r#"[owner]
github_user = "testuser"

[accounts.personal]
provider = "gmail"
user = "test@gmail.com"
"#,
    )
    .unwrap();

    let alice = Contact {
        emails: vec!["alice@example.com".to_string()],
        labels: vec![],
        account: String::new(),
    };
    contact::save_contact("alice", &alice, Some(&path)).unwrap();

    let content = std::fs::read_to_string(&path).unwrap();
    // Existing config preserved
    assert!(content.contains("[owner]"));
    assert!(content.contains("github_user = \"testuser\""));
    assert!(content.contains("[accounts.personal]"));
    // New contact added
    assert!(content.contains("[contacts.alice]"));
    assert!(content.contains("\"alice@example.com\""));
}
