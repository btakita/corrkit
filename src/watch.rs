//! IMAP polling daemon — syncs email and pushes to shared repos on an interval.

use anyhow::Result;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use crate::accounts::{load_accounts, load_watch_config, resolve_password};
use crate::config::corky_config;
use crate::resolve;
use crate::sync::imap_sync::sync_account;
use crate::sync::types::SyncState;

/// Desktop notification (best-effort).
fn notify(title: &str, body: &str) {
    #[cfg(target_os = "macos")]
    {
        let _ = std::process::Command::new("osascript")
            .arg("-e")
            .arg(format!(
                "display notification \"{}\" with title \"{}\"",
                body, title
            ))
            .output();
    }
    #[cfg(target_os = "linux")]
    {
        let _ = std::process::Command::new("notify-send")
            .arg(title)
            .arg(body)
            .output();
    }
}

/// Snapshot {account: {label: last_uid}} from current sync state.
fn snapshot_uids(state: &SyncState) -> HashMap<String, HashMap<String, u32>> {
    let mut snap = HashMap::new();
    for (acct_name, acct_state) in &state.accounts {
        let mut labels = HashMap::new();
        for (label, ls) in &acct_state.labels {
            labels.insert(label.clone(), ls.last_uid);
        }
        snap.insert(acct_name.clone(), labels);
    }
    snap
}

/// Count labels where last_uid increased.
fn count_new_messages(
    before: &HashMap<String, HashMap<String, u32>>,
    after: &HashMap<String, HashMap<String, u32>>,
) -> usize {
    let mut count = 0;
    for (acct_name, labels) in after {
        let before_acct = before.get(acct_name);
        for (label, uid) in labels {
            let before_uid = before_acct
                .and_then(|a| a.get(label))
                .copied()
                .unwrap_or(0);
            if *uid > before_uid {
                count += 1;
            }
        }
    }
    count
}

fn load_state() -> SyncState {
    let sf = resolve::sync_state_file();
    if sf.exists() {
        if let Ok(data) = std::fs::read(&sf) {
            if let Ok(state) = crate::sync::types::load_state(&data) {
                return state;
            }
        }
    }
    SyncState::default()
}

fn save_state(state: &SyncState) {
    if let Ok(data) = serde_json::to_vec(state) {
        let _ = std::fs::write(resolve::sync_state_file(), data);
    }
}

fn sync_mailboxes() {
    let config = match corky_config::try_load_config(None) {
        Some(c) => c,
        None => return,
    };
    for name in config.mailboxes.keys() {
        let mb_path = resolve::mailbox_dir(name);
        if !mb_path.exists() || !mb_path.join(".git").exists() {
            continue;
        }
        let output = std::process::Command::new("git")
            .arg("-C")
            .arg(mb_path.to_string_lossy().as_ref())
            .arg("status")
            .arg("--porcelain")
            .output();
        if let Ok(out) = output {
            if !String::from_utf8_lossy(&out.stdout).trim().is_empty() {
                let _ = crate::mailbox::sync::sync_one(name);
            }
        }
    }
}

/// One sync + mailbox sync cycle. Returns count of labels with new messages.
fn poll_once(notify_enabled: bool) -> usize {
    let accounts = match load_accounts(None) {
        Ok(a) => a,
        Err(e) => {
            eprintln!("Failed to load accounts: {}", e);
            return 0;
        }
    };

    let mut state = load_state();
    let before = snapshot_uids(&state);

    for (acct_name, acct) in &accounts {
        println!("\n=== Account: {} ({}) ===", acct_name, acct.user);
        let password = match resolve_password(acct) {
            Ok(p) => p,
            Err(e) => {
                eprintln!("  Error resolving password for {}: {}", acct_name, e);
                continue;
            }
        };
        if let Err(e) = sync_account(
            acct_name,
            &acct.imap_host,
            acct.imap_port,
            acct.imap_starttls,
            &acct.user,
            &password,
            &acct.labels,
            acct.sync_days,
            &mut state,
            false,
            None,
            None,
        ) {
            eprintln!("  Error syncing {}: {}", acct_name, e);
            continue;
        }
    }

    save_state(&state);

    let after = snapshot_uids(&state);
    let new_count = count_new_messages(&before, &after);

    if new_count > 0 {
        println!("\n{} label(s) with new messages", new_count);
        sync_mailboxes();
        if notify_enabled {
            notify(
                "corky",
                &format!("{} label(s) with new messages", new_count),
            );
        }
    } else {
        println!("\nNo new messages");
    }

    new_count
}

/// corky watch [--interval N]
#[tokio::main]
pub async fn run(interval_override: Option<u64>) -> Result<()> {
    let config = load_watch_config(None)?;
    let interval = interval_override.unwrap_or(config.poll_interval);

    let shutdown = Arc::new(AtomicBool::new(false));
    let shutdown_clone = shutdown.clone();

    // Handle Ctrl-C
    tokio::spawn(async move {
        tokio::signal::ctrl_c().await.ok();
        println!("\nReceived signal, shutting down...");
        shutdown_clone.store(true, Ordering::Relaxed);
    });

    println!("corky watch: polling every {}s (Ctrl-C to stop)", interval);

    loop {
        if shutdown.load(Ordering::Relaxed) {
            break;
        }

        // Run sync in a blocking context
        let notify_enabled = config.notify;
        tokio::task::spawn_blocking(move || {
            poll_once(notify_enabled);
        })
        .await?;

        if shutdown.load(Ordering::Relaxed) {
            break;
        }

        tokio::time::sleep(tokio::time::Duration::from_secs(interval)).await;
    }

    println!("corky watch: stopped");
    Ok(())
}
