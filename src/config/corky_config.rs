//! Unified config type — parse .corky.toml (accounts + routing + mailboxes).

use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};

use crate::accounts::{Account, OwnerConfig, WatchConfig};
use crate::resolve;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CorkyConfig {
    #[serde(default)]
    pub owner: Option<OwnerConfig>,
    #[serde(default)]
    pub accounts: HashMap<String, Account>,
    #[serde(default)]
    pub routing: HashMap<String, Vec<String>>,
    #[serde(default)]
    pub mailboxes: HashMap<String, MailboxConfig>,
    #[serde(default)]
    pub watch: Option<WatchConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MailboxConfig {
    #[serde(default)]
    pub auto_send: bool,
    #[serde(default)]
    pub permissions: HashMap<String, MailboxPermissions>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MailboxPermissions {
    #[serde(default)]
    pub write: Vec<String>,
    #[serde(default)]
    pub read: Vec<String>,
    #[serde(default)]
    pub sync: bool,
    #[serde(default)]
    pub send: bool,
}

/// Load .corky.toml (or corky.toml) from a given path or resolved location.
pub fn load_config(path: Option<&Path>) -> Result<CorkyConfig> {
    let path = path
        .map(PathBuf::from)
        .unwrap_or_else(resolve::corky_toml);
    if !path.exists() {
        bail!(
            ".corky.toml not found at {}.\nRun 'corky init' or 'corky migrate' to create it.",
            path.display()
        );
    }
    let content = std::fs::read_to_string(&path)?;
    let config: CorkyConfig = toml::from_str(&content)?;
    Ok(config)
}

/// Try loading config, returning None if the file doesn't exist.
pub fn try_load_config(path: Option<&Path>) -> Option<CorkyConfig> {
    let path = path
        .map(PathBuf::from)
        .unwrap_or_else(resolve::corky_toml);
    if !path.exists() {
        return None;
    }
    let content = std::fs::read_to_string(&path).ok()?;
    toml::from_str(&content).ok()
}
