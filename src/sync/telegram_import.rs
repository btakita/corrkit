//! Telegram Desktop JSON export → corky conversations.
//!
//! Parses Telegram Desktop's `result.json` export format and converts
//! each chat into a corky thread using `merge_message_to_file()`.

use anyhow::{Context, Result};
use chrono::NaiveDateTime;
use serde::Deserialize;
use std::path::Path;

use super::imap_sync::merge_message_to_file;
use super::types::Message;

// ---------------------------------------------------------------------------
// Telegram Desktop JSON types
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
pub struct TelegramExport {
    #[serde(default)]
    pub chats: Option<ChatList>,

    // Single-chat export (no wrapping `chats` key)
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default, rename = "type")]
    pub chat_type: Option<String>,
    #[serde(default)]
    pub id: Option<i64>,
    #[serde(default)]
    pub messages: Option<Vec<TelegramMessage>>,
}

#[derive(Debug, Deserialize)]
pub struct ChatList {
    #[serde(default)]
    pub list: Vec<Chat>,
}

#[derive(Debug, Deserialize)]
pub struct Chat {
    pub name: String,
    #[serde(rename = "type")]
    pub chat_type: String,
    pub id: i64,
    #[serde(default)]
    pub messages: Vec<TelegramMessage>,
}

#[derive(Debug, Deserialize)]
pub struct TelegramMessage {
    pub id: i64,
    #[serde(rename = "type")]
    pub msg_type: String,
    pub date: String,
    #[serde(default)]
    pub from: Option<String>,
    #[serde(default)]
    pub from_id: Option<String>,
    #[serde(default)]
    pub text: Option<TextContent>,
}

/// Telegram's `text` field can be a plain string or an array of text entities
/// (rich text with formatting, links, etc.).
#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum TextContent {
    Plain(String),
    Parts(Vec<TextPart>),
}

#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum TextPart {
    Plain(String),
    Entity(TextEntity),
}

#[derive(Debug, Deserialize)]
pub struct TextEntity {
    #[serde(rename = "type")]
    pub entity_type: String,
    pub text: String,
}

impl TextContent {
    /// Flatten text content to a plain string.
    pub fn to_plain(&self) -> String {
        match self {
            TextContent::Plain(s) => s.clone(),
            TextContent::Parts(parts) => {
                let mut buf = String::new();
                for part in parts {
                    match part {
                        TextPart::Plain(s) => buf.push_str(s),
                        TextPart::Entity(e) => buf.push_str(&e.text),
                    }
                }
                buf
            }
        }
    }
}

// ---------------------------------------------------------------------------
// ISO 8601 (Telegram) → RFC 2822 (corky) date conversion
// ---------------------------------------------------------------------------

fn telegram_date_to_rfc2822(iso: &str) -> String {
    // Telegram exports dates as "2024-10-09T19:32:23"
    NaiveDateTime::parse_from_str(iso, "%Y-%m-%dT%H:%M:%S")
        .map(|dt| {
            use chrono::TimeZone;
            chrono::Utc
                .from_utc_datetime(&dt)
                .format("%a, %d %b %Y %H:%M:%S +0000")
                .to_string()
        })
        .unwrap_or_else(|_| iso.to_string())
}

// ---------------------------------------------------------------------------
// Import logic
// ---------------------------------------------------------------------------

/// Import a single chat into the output directory.
fn import_chat(
    chat_name: &str,
    chat_id: i64,
    messages: &[TelegramMessage],
    label: &str,
    out_dir: &Path,
    account_name: &str,
) -> Result<u32> {
    let thread_id = format!("tg:{}", chat_id);
    let subject = chat_name.to_string();
    let mut count = 0u32;

    for msg in messages {
        // Only import regular messages
        if msg.msg_type != "message" {
            continue;
        }

        let body = msg
            .text
            .as_ref()
            .map(|t| t.to_plain())
            .unwrap_or_default();

        // Skip empty messages (e.g. media-only)
        if body.trim().is_empty() {
            continue;
        }

        let from = msg.from.clone().unwrap_or_else(|| "Unknown".to_string());
        let date = telegram_date_to_rfc2822(&msg.date);

        let message = Message {
            id: msg.id.to_string(),
            thread_id: thread_id.clone(),
            from,
            to: String::new(),
            cc: String::new(),
            date,
            subject: subject.clone(),
            body,
        };

        merge_message_to_file(out_dir, label, account_name, &message, &thread_id)?;
        count += 1;
    }

    Ok(count)
}

/// Parse a single Telegram Desktop JSON export file.
fn import_file(
    path: &Path,
    label: &str,
    out_dir: &Path,
    account_name: &str,
) -> Result<()> {
    let data = std::fs::read_to_string(path)
        .with_context(|| format!("Failed to read {}", path.display()))?;
    let export: TelegramExport = serde_json::from_str(&data)
        .with_context(|| format!("Failed to parse {}", path.display()))?;

    // Multi-chat export (has `chats.list`)
    if let Some(chats) = export.chats {
        println!("Found {} chat(s) in {}", chats.list.len(), path.display());
        for chat in &chats.list {
            let count = import_chat(
                &chat.name,
                chat.id,
                &chat.messages,
                label,
                out_dir,
                account_name,
            )?;
            if count > 0 {
                println!("  {} — {} message(s)", chat.name, count);
            }
        }
        return Ok(());
    }

    // Single-chat export (top-level name/id/messages)
    if let (Some(name), Some(id), Some(messages)) =
        (export.name, export.id, export.messages)
    {
        let count = import_chat(&name, id, &messages, label, out_dir, account_name)?;
        println!("{} — {} message(s)", name, count);
        return Ok(());
    }

    anyhow::bail!(
        "Unrecognized Telegram export format in {}. \
         Expected either a multi-chat export with `chats.list` \
         or a single-chat export with `name`, `id`, and `messages`.",
        path.display()
    );
}

/// Entry point: import Telegram Desktop JSON export(s).
///
/// `path` can be a single `result.json` file or a directory containing
/// multiple JSON export files.
pub fn run(path: &Path, label: &str, out_dir: &Path, account_name: &str) -> Result<()> {
    println!("Telegram import: {}", path.display());

    if path.is_dir() {
        let mut found = false;
        for entry in std::fs::read_dir(path)
            .with_context(|| format!("Cannot read directory {}", path.display()))?
        {
            let entry = entry?;
            let p = entry.path();
            if p.extension().and_then(|e| e.to_str()) == Some("json") {
                import_file(&p, label, out_dir, account_name)?;
                found = true;
            }
        }
        if !found {
            anyhow::bail!("No JSON files found in {}", path.display());
        }
    } else {
        import_file(path, label, out_dir, account_name)?;
    }

    println!("Telegram import complete.");
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_telegram_date_to_rfc2822() {
        let rfc = telegram_date_to_rfc2822("2024-10-09T19:32:23");
        assert_eq!(rfc, "Wed, 09 Oct 2024 19:32:23 +0000");
    }

    #[test]
    fn test_telegram_date_invalid_passthrough() {
        let bad = "not-a-date";
        assert_eq!(telegram_date_to_rfc2822(bad), bad);
    }

    #[test]
    fn test_text_content_plain() {
        let tc = TextContent::Plain("hello".to_string());
        assert_eq!(tc.to_plain(), "hello");
    }

    #[test]
    fn test_text_content_parts() {
        let tc = TextContent::Parts(vec![
            TextPart::Plain("Hello ".to_string()),
            TextPart::Entity(TextEntity {
                entity_type: "bold".to_string(),
                text: "world".to_string(),
            }),
            TextPart::Plain("!".to_string()),
        ]);
        assert_eq!(tc.to_plain(), "Hello world!");
    }

    #[test]
    fn test_parse_single_chat_export() {
        let json = r#"{
            "name": "Alice",
            "type": "personal_chat",
            "id": 12345,
            "messages": [
                {
                    "id": 1,
                    "type": "message",
                    "date": "2024-10-09T19:32:23",
                    "from": "Alice",
                    "from_id": "user123",
                    "text": "Hello!"
                },
                {
                    "id": 2,
                    "type": "message",
                    "date": "2024-10-09T19:33:00",
                    "from": "Bob",
                    "from_id": "user456",
                    "text": [
                        "Check this ",
                        {"type": "link", "text": "link"}
                    ]
                }
            ]
        }"#;
        let export: TelegramExport = serde_json::from_str(json).unwrap();
        assert_eq!(export.name.as_deref(), Some("Alice"));
        assert_eq!(export.id, Some(12345));
        let messages = export.messages.unwrap();
        assert_eq!(messages.len(), 2);
        assert_eq!(messages[0].text.as_ref().unwrap().to_plain(), "Hello!");
        assert_eq!(
            messages[1].text.as_ref().unwrap().to_plain(),
            "Check this link"
        );
    }

    #[test]
    fn test_parse_multi_chat_export() {
        let json = r#"{
            "chats": {
                "list": [
                    {
                        "name": "Alice",
                        "type": "personal_chat",
                        "id": 111,
                        "messages": []
                    },
                    {
                        "name": "Dev Group",
                        "type": "private_group",
                        "id": 222,
                        "messages": [
                            {
                                "id": 1,
                                "type": "message",
                                "date": "2024-01-01T00:00:00",
                                "from": "Charlie",
                                "text": "Hi all"
                            }
                        ]
                    }
                ]
            }
        }"#;
        let export: TelegramExport = serde_json::from_str(json).unwrap();
        let chats = export.chats.unwrap();
        assert_eq!(chats.list.len(), 2);
        assert_eq!(chats.list[0].name, "Alice");
        assert_eq!(chats.list[1].messages.len(), 1);
    }

    #[test]
    fn test_import_to_disk() {
        let dir = tempfile::tempdir().unwrap();
        let out_dir = dir.path().join("conversations");
        std::fs::create_dir_all(&out_dir).unwrap();

        let json = r#"{
            "name": "Test Chat",
            "type": "personal_chat",
            "id": 99999,
            "messages": [
                {
                    "id": 1,
                    "type": "message",
                    "date": "2024-06-15T10:00:00",
                    "from": "Alice",
                    "text": "First message"
                },
                {
                    "id": 2,
                    "type": "message",
                    "date": "2024-06-15T10:01:00",
                    "from": "Bob",
                    "text": "Second message"
                },
                {
                    "id": 3,
                    "type": "service",
                    "date": "2024-06-15T10:02:00",
                    "from": "Alice",
                    "text": "service message ignored"
                }
            ]
        }"#;

        let json_path = dir.path().join("result.json");
        std::fs::write(&json_path, json).unwrap();

        run(&json_path, "telegram", &out_dir, "tg-personal").unwrap();

        // Should have created one thread file
        let files: Vec<_> = std::fs::read_dir(&out_dir)
            .unwrap()
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.path()
                    .extension()
                    .and_then(|ext| ext.to_str())
                    == Some("md")
            })
            .collect();
        assert_eq!(files.len(), 1);

        let content = std::fs::read_to_string(files[0].path()).unwrap();
        assert!(content.contains("# Test Chat"));
        assert!(content.contains("**Thread ID**: tg:99999"));
        assert!(content.contains("First message"));
        assert!(content.contains("Second message"));
        // Service messages should be excluded
        assert!(!content.contains("service message ignored"));
    }
}
