//! Path resolution for corky data and config directories.
//!
//! Resolution order for data directory:
//!   1. mail/ in cwd (developer workflow)
//!   2. CORKY_DATA environment variable
//!   3. App config mailbox (via app_config::resolve_mailbox)
//!   4. ~/Documents/mail (general user default)

use std::path::PathBuf;

/// Return the data directory path.
pub fn data_dir() -> PathBuf {
    let local = PathBuf::from("mail");
    if local.is_dir() {
        return local;
    }
    if let Ok(env) = std::env::var("CORKY_DATA") {
        if !env.is_empty() {
            return PathBuf::from(env);
        }
    }
    // Try app config mailbox
    if let Ok(Some(mailbox_path)) = crate::app_config::resolve_mailbox(None) {
        return mailbox_path;
    }
    home_dir().join("Documents").join("mail")
}

/// Return the config directory path.
///
/// Config always lives inside the data directory (mail/).
pub fn config_dir() -> PathBuf {
    data_dir()
}

// --- Derived helpers: data paths ---

pub fn conversations_dir() -> PathBuf {
    data_dir().join("conversations")
}

pub fn drafts_dir() -> PathBuf {
    data_dir().join("drafts")
}

pub fn contacts_dir() -> PathBuf {
    data_dir().join("contacts")
}

pub fn mailbox_dir(name: &str) -> PathBuf {
    data_dir().join("mailboxes").join(name.to_lowercase())
}

pub fn sync_state_file() -> PathBuf {
    data_dir().join(".sync-state.json")
}

pub fn manifest_file() -> PathBuf {
    data_dir().join("manifest.toml")
}

// --- Derived helpers: config paths ---

/// Resolve .corky.toml path: check .corky.toml then corky.toml in config_dir().
pub fn corky_toml() -> PathBuf {
    let dir = config_dir();
    let dotfile = dir.join(".corky.toml");
    if dotfile.exists() {
        return dotfile;
    }
    let plain = dir.join("corky.toml");
    if plain.exists() {
        return plain;
    }
    // Default to .corky.toml (for creation)
    dotfile
}

pub fn voice_md() -> PathBuf {
    config_dir().join("voice.md")
}

pub fn credentials_json() -> PathBuf {
    config_dir().join("credentials.json")
}

/// Get the user's home directory.
pub fn home_dir() -> PathBuf {
    std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

/// Expand ~ to home directory.
pub fn expand_tilde(path: &str) -> PathBuf {
    if let Some(rest) = path.strip_prefix("~/") {
        home_dir().join(rest)
    } else if path == "~" {
        home_dir()
    } else {
        PathBuf::from(path)
    }
}
