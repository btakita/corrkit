//! Path resolution for corrkit data and config directories.
//!
//! Resolution order for data directory:
//!   1. correspondence/ in cwd (developer workflow)
//!   2. CORRKIT_DATA environment variable
//!   3. App config space (via app_config::resolve_space)
//!   4. ~/Documents/correspondence (general user default)

use std::path::PathBuf;

/// Return the data directory path.
pub fn data_dir() -> PathBuf {
    let local = PathBuf::from("correspondence");
    if local.is_dir() {
        return local;
    }
    if let Ok(env) = std::env::var("CORRKIT_DATA") {
        if !env.is_empty() {
            return PathBuf::from(env);
        }
    }
    // Try app config space
    if let Ok(Some(space_path)) = crate::app_config::resolve_space(None) {
        return space_path;
    }
    home_dir().join("Documents").join("correspondence")
}

/// Return the config directory path.
///
/// Config always lives inside the data directory (correspondence/).
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

pub fn collab_to_dir(gh_user: &str) -> PathBuf {
    data_dir()
        .join("collabs")
        .join(gh_user.to_lowercase())
        .join("to")
}

pub fn collab_from_dir(gh_user: &str) -> PathBuf {
    data_dir()
        .join("collabs")
        .join(gh_user.to_lowercase())
        .join("from")
}

pub fn sync_state_file() -> PathBuf {
    data_dir().join(".sync-state.json")
}

pub fn manifest_file() -> PathBuf {
    data_dir().join("manifest.toml")
}

// --- Derived helpers: config paths ---

/// Resolve .corrkit.toml path: check .corrkit.toml then corrkit.toml in config_dir().
pub fn corrkit_toml() -> PathBuf {
    let dir = config_dir();
    let dotfile = dir.join(".corrkit.toml");
    if dotfile.exists() {
        return dotfile;
    }
    let plain = dir.join("corrkit.toml");
    if plain.exists() {
        return plain;
    }
    // Default to .corrkit.toml (for creation)
    dotfile
}

pub fn accounts_toml() -> PathBuf {
    config_dir().join("accounts.toml")
}

pub fn collaborators_toml() -> PathBuf {
    config_dir().join("collaborators.toml")
}

pub fn contacts_toml() -> PathBuf {
    config_dir().join("contacts.toml")
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
