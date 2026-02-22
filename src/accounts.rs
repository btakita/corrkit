//! Account configuration — parse accounts.toml with provider presets.

use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};

use crate::resolve;

/// Provider presets for common IMAP/SMTP configurations.
pub fn provider_presets() -> HashMap<&'static str, AccountDefaults> {
    let mut m = HashMap::new();
    m.insert(
        "gmail",
        AccountDefaults {
            imap_host: "imap.gmail.com",
            imap_port: 993,
            imap_starttls: false,
            smtp_host: "smtp.gmail.com",
            smtp_port: 465,
            drafts_folder: "[Gmail]/Drafts",
        },
    );
    m.insert(
        "protonmail-bridge",
        AccountDefaults {
            imap_host: "127.0.0.1",
            imap_port: 1143,
            imap_starttls: true,
            smtp_host: "127.0.0.1",
            smtp_port: 1025,
            drafts_folder: "Drafts",
        },
    );
    m
}

pub struct AccountDefaults {
    pub imap_host: &'static str,
    pub imap_port: u16,
    pub imap_starttls: bool,
    pub smtp_host: &'static str,
    pub smtp_port: u16,
    pub drafts_folder: &'static str,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OwnerConfig {
    pub github_user: String,
    #[serde(default)]
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WatchConfig {
    #[serde(default = "default_poll_interval")]
    pub poll_interval: u64,
    #[serde(default)]
    pub notify: bool,
}

fn default_poll_interval() -> u64 {
    300
}

impl Default for WatchConfig {
    fn default() -> Self {
        Self {
            poll_interval: 300,
            notify: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Account {
    #[serde(default = "default_provider")]
    pub provider: String,
    #[serde(default)]
    pub user: String,
    #[serde(default)]
    pub password: String,
    #[serde(default)]
    pub password_cmd: String,
    #[serde(default)]
    pub labels: Vec<String>,
    #[serde(default)]
    pub imap_host: String,
    #[serde(default = "default_imap_port")]
    pub imap_port: u16,
    #[serde(default)]
    pub imap_starttls: bool,
    #[serde(default)]
    pub smtp_host: String,
    #[serde(default = "default_smtp_port")]
    pub smtp_port: u16,
    #[serde(default = "default_drafts_folder")]
    pub drafts_folder: String,
    #[serde(default = "default_sync_days")]
    pub sync_days: u32,
    #[serde(default)]
    pub default: bool,
}

fn default_provider() -> String {
    "imap".to_string()
}
fn default_imap_port() -> u16 {
    993
}
fn default_smtp_port() -> u16 {
    465
}
fn default_drafts_folder() -> String {
    "Drafts".to_string()
}
fn default_sync_days() -> u32 {
    3650
}

impl Default for Account {
    fn default() -> Self {
        Self {
            provider: "imap".to_string(),
            user: String::new(),
            password: String::new(),
            password_cmd: String::new(),
            labels: vec![],
            imap_host: String::new(),
            imap_port: 993,
            imap_starttls: false,
            smtp_host: String::new(),
            smtp_port: 465,
            drafts_folder: "Drafts".to_string(),
            sync_days: 3650,
            default: false,
        }
    }
}

/// Apply provider preset defaults. Account values win over preset.
fn apply_preset(account: &mut Account) {
    let presets = provider_presets();
    let Some(preset) = presets.get(account.provider.as_str()) else {
        return;
    };
    let defaults = Account::default();
    if account.imap_host == defaults.imap_host {
        account.imap_host = preset.imap_host.to_string();
    }
    if account.imap_port == defaults.imap_port {
        account.imap_port = preset.imap_port;
    }
    if account.imap_starttls == defaults.imap_starttls && preset.imap_starttls {
        account.imap_starttls = preset.imap_starttls;
    }
    if account.smtp_host == defaults.smtp_host {
        account.smtp_host = preset.smtp_host.to_string();
    }
    if account.smtp_port == defaults.smtp_port {
        account.smtp_port = preset.smtp_port;
    }
    if account.drafts_folder == defaults.drafts_folder {
        account.drafts_folder = preset.drafts_folder.to_string();
    }
}

/// Resolve password: inline value if set, else run password_cmd.
pub fn resolve_password(account: &Account) -> Result<String> {
    if !account.password.is_empty() {
        return Ok(account.password.clone());
    }
    if !account.password_cmd.is_empty() {
        let output = std::process::Command::new("sh")
            .arg("-c")
            .arg(&account.password_cmd)
            .output()?;
        if !output.status.success() {
            bail!(
                "password_cmd failed: {}",
                String::from_utf8_lossy(&output.stderr).trim()
            );
        }
        return Ok(String::from_utf8_lossy(&output.stdout).trim().to_string());
    }
    bail!("Account {:?} has no password or password_cmd", account.user)
}

const NON_ACCOUNT_KEYS: &[&str] = &["watch", "owner", "routing", "mailboxes"];

/// Parse accounts from .corky.toml or accounts.toml → {name: Account} mapping.
///
/// Resolution order (when path is None):
/// 1. .corky.toml / corky.toml (new unified config)
/// 2. accounts.toml (legacy)
pub fn load_accounts(path: Option<&Path>) -> Result<HashMap<String, Account>> {
    let path = match path {
        Some(p) => PathBuf::from(p),
        None => {
            let ck = resolve::corky_toml();
            if ck.exists() {
                ck
            } else {
                resolve::accounts_toml()
            }
        }
    };
    if !path.exists() {
        return Ok(HashMap::new());
    }
    let content = std::fs::read_to_string(&path)?;
    let raw: toml::Value = toml::from_str(&content)?;
    let table = raw.as_table().unwrap();

    // Try [accounts.*] format first, fall back to flat format
    let accounts_section = if let Some(toml::Value::Table(accts)) = table.get("accounts") {
        accts.clone()
    } else {
        table.clone()
    };

    let mut result = HashMap::new();
    for (name, data) in &accounts_section {
        if NON_ACCOUNT_KEYS.contains(&name.as_str()) {
            continue;
        }
        if !data.is_table() {
            continue;
        }
        let mut account: Account = data.clone().try_into()?;
        apply_preset(&mut account);
        result.insert(name.clone(), account);
    }
    Ok(result)
}

/// Build a synthetic Account from legacy .env GMAIL_* vars.
fn legacy_account_from_env() -> Result<Account> {
    dotenvy::dotenv().ok();
    let user = std::env::var("GMAIL_USER_EMAIL")
        .map_err(|_| anyhow::anyhow!("No accounts.toml found and GMAIL_USER_EMAIL not set in .env"))?;
    let password = std::env::var("GMAIL_APP_PASSWORD")
        .unwrap_or_default()
        .replace(' ', "");
    let labels_str = std::env::var("GMAIL_SYNC_LABELS").unwrap_or_default();
    let sync_days: u32 = std::env::var("GMAIL_SYNC_DAYS")
        .unwrap_or_else(|_| "3650".to_string())
        .parse()
        .unwrap_or(3650);

    Ok(Account {
        provider: "gmail".to_string(),
        user,
        password,
        labels: labels_str
            .split(',')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect(),
        imap_host: "imap.gmail.com".to_string(),
        imap_port: 993,
        smtp_host: "smtp.gmail.com".to_string(),
        smtp_port: 465,
        drafts_folder: "[Gmail]/Drafts".to_string(),
        sync_days,
        default: true,
        ..Default::default()
    })
}

/// Load accounts.toml, falling back to .env GMAIL_* vars.
pub fn load_accounts_or_env(path: Option<&Path>) -> Result<HashMap<String, Account>> {
    let accounts = load_accounts(path)?;
    if !accounts.is_empty() {
        return Ok(accounts);
    }
    let legacy = legacy_account_from_env()?;
    let mut m = HashMap::new();
    m.insert("_legacy".to_string(), legacy);
    Ok(m)
}

/// Load [owner] section from .corky.toml or accounts.toml.
pub fn load_owner(path: Option<&Path>) -> Result<OwnerConfig> {
    let path = match path {
        Some(p) => PathBuf::from(p),
        None => {
            let ck = resolve::corky_toml();
            if ck.exists() {
                ck
            } else {
                resolve::accounts_toml()
            }
        }
    };
    if !path.exists() {
        bail!(
            "Config not found at {}.\nRun 'corky init' or add an [owner] section with github_user.",
            path.display()
        );
    }
    let content = std::fs::read_to_string(&path)?;
    let raw: toml::Value = toml::from_str(&content)?;
    let owner_data = raw
        .get("owner")
        .ok_or_else(|| {
            anyhow::anyhow!(
                "Missing [owner] section in config.\nAdd: [owner]\ngithub_user = \"your-github-username\""
            )
        })?;
    let owner: OwnerConfig = owner_data.clone().try_into()?;
    Ok(owner)
}

/// Return (name, account) for the default account.
pub fn get_default_account(accounts: &HashMap<String, Account>) -> Result<(String, Account)> {
    for (name, acct) in accounts {
        if acct.default {
            return Ok((name.clone(), acct.clone()));
        }
    }
    // Fall back to first account
    let (name, acct) = accounts.iter().next().ok_or_else(|| anyhow::anyhow!("No accounts configured"))?;
    Ok((name.clone(), acct.clone()))
}

/// Lookup account by email address.
pub fn get_account_for_email(
    accounts: &HashMap<String, Account>,
    email_addr: &str,
) -> Option<(String, Account)> {
    let email_lower = email_addr.to_lowercase();
    for (name, acct) in accounts {
        if acct.user.to_lowercase() == email_lower {
            return Some((name.clone(), acct.clone()));
        }
    }
    None
}

/// Add a label to an account's labels list in .corky.toml or accounts.toml.
///
/// Uses toml_edit for format-preserving edits.
/// Returns Ok(true) if added, Ok(false) if already present.
pub fn add_label_to_account(account_name: &str, label: &str, path: Option<&Path>) -> Result<bool> {
    let path = match path {
        Some(p) => PathBuf::from(p),
        None => {
            let ck = resolve::corky_toml();
            if ck.exists() {
                ck
            } else {
                resolve::accounts_toml()
            }
        }
    };
    if !path.exists() {
        bail!("Config not found at {}", path.display());
    }

    // Verify account exists and label isn't already there
    let accounts = load_accounts(Some(&path))?;
    let Some(acct) = accounts.get(account_name) else {
        bail!(
            "Unknown account: {}\nAvailable: {}",
            account_name,
            accounts.keys().cloned().collect::<Vec<_>>().join(", ")
        );
    };
    if acct.labels.contains(&label.to_string()) {
        return Ok(false);
    }

    // Format-preserving edit with toml_edit
    let content = std::fs::read_to_string(&path)?;
    let mut doc = content.parse::<toml_edit::DocumentMut>()?;

    // Try [accounts.{name}] first, then [{name}]
    let labels_array = if let Some(accounts_table) = doc.get_mut("accounts") {
        accounts_table
            .get_mut(account_name)
            .and_then(|t| t.get_mut("labels"))
    } else {
        doc.get_mut(account_name)
            .and_then(|t| t.get_mut("labels"))
    };

    if let Some(labels) = labels_array {
        if let Some(arr) = labels.as_array_mut() {
            arr.push(label);
        }
    }

    std::fs::write(&path, doc.to_string())?;
    Ok(true)
}

/// CLI: corky add-label LABEL --account ACCOUNT
pub fn add_label_cmd(label: &str, account: &str) -> Result<()> {
    let added = add_label_to_account(account, label, None)?;
    if added {
        println!("Added '{}' to account '{}'", label, account);
    } else {
        println!("Label '{}' already in account '{}'", label, account);
    }
    Ok(())
}

/// Load [watch] section from .corky.toml or accounts.toml. Returns defaults if missing.
pub fn load_watch_config(path: Option<&Path>) -> Result<WatchConfig> {
    let path = match path {
        Some(p) => PathBuf::from(p),
        None => {
            let ck = resolve::corky_toml();
            if ck.exists() {
                ck
            } else {
                resolve::accounts_toml()
            }
        }
    };
    if !path.exists() {
        return Ok(WatchConfig::default());
    }
    let content = std::fs::read_to_string(&path)?;
    let raw: toml::Value = toml::from_str(&content)?;
    match raw.get("watch") {
        Some(watch_data) => {
            let config: WatchConfig = watch_data.clone().try_into()?;
            Ok(config)
        }
        None => Ok(WatchConfig::default()),
    }
}
