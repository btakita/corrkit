//! Version upgrade check and self-update for corky.

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const CRATE_NAME: &str = env!("CARGO_PKG_NAME");
const CURRENT_VERSION: &str = env!("CARGO_PKG_VERSION");
const CACHE_MAX_AGE_SECS: u64 = 24 * 60 * 60; // 24 hours

#[derive(Serialize, Deserialize)]
struct VersionCache {
    latest: String,
    checked_at: u64,
}

/// Called on startup — prints a warning to stderr if a newer version is available.
/// Silently returns on any error.
pub fn warn_if_outdated() {
    if let Some(latest) = check_for_update() {
        eprintln!(
            "\x1b[33mA newer version of corky is available: v{latest} (current: v{CURRENT_VERSION})\n\
             Run `corky upgrade` to update.\x1b[0m"
        );
    }
}

/// The `upgrade` subcommand handler.
pub fn run() -> Result<()> {
    eprintln!("Checking for updates...");

    let latest = match fetch_latest_version(CRATE_NAME) {
        Some(v) => v,
        None => {
            eprintln!("Could not determine the latest version from crates.io.");
            return Ok(());
        }
    };

    if !version_is_newer(&latest, CURRENT_VERSION) {
        eprintln!("You are already on the latest version (v{CURRENT_VERSION}).");
        return Ok(());
    }

    eprintln!("New version available: v{latest} (current: v{CURRENT_VERSION})");

    // Try cargo install first
    eprintln!("Attempting: cargo install {CRATE_NAME}");
    let cargo_status = std::process::Command::new("cargo")
        .args(["install", CRATE_NAME])
        .status();

    if let Ok(status) = cargo_status {
        if status.success() {
            eprintln!("Successfully upgraded to v{latest} via cargo.");
            return Ok(());
        }
    }

    // Fall back to pip
    eprintln!("cargo install failed, trying: pip install --upgrade {CRATE_NAME}");
    let pip_status = std::process::Command::new("pip")
        .args(["install", "--upgrade", CRATE_NAME])
        .status();

    if let Ok(status) = pip_status {
        if status.success() {
            eprintln!("Successfully upgraded to v{latest} via pip.");
            return Ok(());
        }
    }

    // Manual instructions
    eprintln!(
        "\nAutomatic upgrade failed. You can upgrade manually:\n\
         \n  cargo install {CRATE_NAME}\n\
         \nor:\n\
         \n  pip install --upgrade {CRATE_NAME}\n\
         \nor build from source:\n\
         \n  git pull && make install\n"
    );

    Ok(())
}

/// Check for an update using a 24h cache. Returns the latest version string
/// if it is newer than the current version.
fn check_for_update() -> Option<String> {
    // Try to read from cache first
    if let Some(cache) = read_cache() {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .ok()?
            .as_secs();
        if now.saturating_sub(cache.checked_at) < CACHE_MAX_AGE_SECS {
            return if version_is_newer(&cache.latest, CURRENT_VERSION) {
                Some(cache.latest)
            } else {
                None
            };
        }
    }

    // Cache miss or stale — fetch from crates.io
    let latest = fetch_latest_version(CRATE_NAME)?;
    write_cache(&latest);

    if version_is_newer(&latest, CURRENT_VERSION) {
        Some(latest)
    } else {
        None
    }
}

/// Query crates.io for the latest version of the given crate.
fn fetch_latest_version(crate_name: &str) -> Option<String> {
    let url = format!("https://crates.io/api/v1/crates/{crate_name}");
    let agent = ureq::AgentBuilder::new()
        .timeout_read(Duration::from_secs(5))
        .timeout_write(Duration::from_secs(5))
        .build();
    let resp = agent.get(&url).call().ok()?;
    let body: serde_json::Value = resp.into_json().ok()?;
    body.get("crate")?
        .get("max_version")?
        .as_str()
        .map(|s: &str| s.to_string())
}

/// Simple X.Y.Z version comparison. Returns true if `latest` is strictly
/// newer than `current`.
fn version_is_newer(latest: &str, current: &str) -> bool {
    let parse = |v: &str| -> Option<(u64, u64, u64)> {
        let mut parts = v.split('.');
        let major = parts.next()?.parse().ok()?;
        let minor = parts.next()?.parse().ok()?;
        let patch = parts.next()?.parse().ok()?;
        Some((major, minor, patch))
    };

    match (parse(latest), parse(current)) {
        (Some(l), Some(c)) => l > c,
        _ => false,
    }
}

fn cache_path() -> Option<PathBuf> {
    let home = std::env::var("HOME").ok()?;
    Some(PathBuf::from(home).join(".cache/corky/version-cache.json"))
}

fn read_cache() -> Option<VersionCache> {
    let path = cache_path()?;
    let data = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&data).ok()
}

fn write_cache(latest: &str) {
    let Some(path) = cache_path() else { return };
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let cache = VersionCache {
        latest: latest.to_string(),
        checked_at: now,
    };
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let _ = std::fs::write(&path, serde_json::to_string(&cache).unwrap_or_default());
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn test_version_newer() {
        assert!(version_is_newer("1.0.1", "1.0.0"));
        assert!(version_is_newer("1.1.0", "1.0.9"));
        assert!(version_is_newer("2.0.0", "1.9.9"));
    }

    #[test]
    fn test_version_same() {
        assert!(!version_is_newer("1.0.0", "1.0.0"));
        assert!(!version_is_newer("0.9.2", "0.9.2"));
    }

    #[test]
    fn test_version_older() {
        assert!(!version_is_newer("1.0.0", "1.0.1"));
        assert!(!version_is_newer("0.8.0", "0.9.0"));
        assert!(!version_is_newer("1.0.0", "2.0.0"));
    }

    #[test]
    fn test_version_major_minor_patch() {
        // Major bump
        assert!(version_is_newer("2.0.0", "1.99.99"));
        // Minor bump
        assert!(version_is_newer("1.1.0", "1.0.99"));
        // Patch bump
        assert!(version_is_newer("1.0.2", "1.0.1"));
    }

    #[test]
    fn test_version_invalid() {
        assert!(!version_is_newer("abc", "1.0.0"));
        assert!(!version_is_newer("1.0.0", "abc"));
        assert!(!version_is_newer("1.0", "1.0.0"));
    }

    #[test]
    fn test_cache_freshness() {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Fresh cache (just now)
        let fresh = VersionCache {
            latest: "9.9.9".to_string(),
            checked_at: now,
        };
        assert!(now.saturating_sub(fresh.checked_at) < CACHE_MAX_AGE_SECS);

        // Stale cache (25 hours ago)
        let stale = VersionCache {
            latest: "9.9.9".to_string(),
            checked_at: now - 25 * 60 * 60,
        };
        assert!(now.saturating_sub(stale.checked_at) >= CACHE_MAX_AGE_SECS);
    }

    #[test]
    fn test_cache_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let cache_file = dir.path().join("version-cache.json");

        let cache = VersionCache {
            latest: "1.2.3".to_string(),
            checked_at: 1700000000,
        };

        // Write
        let json = serde_json::to_string(&cache).unwrap();
        let mut f = std::fs::File::create(&cache_file).unwrap();
        f.write_all(json.as_bytes()).unwrap();

        // Read back
        let data = std::fs::read_to_string(&cache_file).unwrap();
        let loaded: VersionCache = serde_json::from_str(&data).unwrap();

        assert_eq!(loaded.latest, "1.2.3");
        assert_eq!(loaded.checked_at, 1700000000);
    }
}
