//! Sync shared mailboxes: pull changes, push updates.

use anyhow::Result;
use std::path::Path;
use std::process::Command;

use crate::config::corky_config;
use crate::resolve;

fn run_git(args: &[&str]) -> (String, String, i32) {
    let output = Command::new(args[0])
        .args(&args[1..])
        .output()
        .unwrap_or_else(|_| {
            panic!("Failed to run: {}", args.join(" "));
        });
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let code = output.status.code().unwrap_or(-1);
    (stdout, stderr, code)
}

fn mailbox_status(name: &str, mb_path: &Path) {
    let sp = mb_path.to_string_lossy().to_string();
    run_git(&["git", "-C", &sp, "fetch"]);

    let (incoming, _, inc_code) =
        run_git(&["git", "-C", &sp, "rev-list", "--count", "HEAD..@{u}"]);
    let (outgoing, _, out_code) =
        run_git(&["git", "-C", &sp, "rev-list", "--count", "@{u}..HEAD"]);

    let inc = if inc_code == 0 {
        incoming.trim().to_string()
    } else {
        "?".to_string()
    };
    let out = if out_code == 0 {
        outgoing.trim().to_string()
    } else {
        "?".to_string()
    };

    if inc == "0" && out == "0" {
        println!("  {}: up to date", name);
    } else {
        let mut parts = Vec::new();
        if inc != "0" {
            parts.push(format!("{} incoming", inc));
        }
        if out != "0" {
            parts.push(format!("{} outgoing", out));
        }
        println!("  {}: {}", name, parts.join(", "));
    }
}

/// Check if a directory is a git repo (submodule or standalone).
fn is_git_repo(path: &Path) -> bool {
    // .git file (submodule) or .git directory (standalone repo)
    path.join(".git").exists()
}

/// Full sync for one mailbox.
pub fn sync_one(name: &str) -> Result<()> {
    let mb_path = resolve::mailbox_dir(name);
    if !mb_path.exists() {
        println!(
            "  {}: mailbox not found at {} -- skipping",
            name,
            mb_path.display()
        );
        return Ok(());
    }

    if !is_git_repo(&mb_path) {
        println!("  {}: plain directory -- skipping git sync", name);
        return Ok(());
    }

    println!("Syncing {}...", name);
    let sp = mb_path.to_string_lossy().to_string();

    // Pull changes
    let (stdout, _stderr, code) = run_git(&["git", "-C", &sp, "pull", "--rebase"]);
    if code == 0 {
        if !stdout.contains("Already up to date") {
            println!("  Pulled changes");
        }
    } else {
        println!("  Pull failed -- continuing with push");
    }

    // Copy voice.md if root copy is newer
    let voice_file = resolve::voice_md();
    let mb_voice = mb_path.join("voice.md");
    if voice_file.exists() {
        let should_copy = if mb_voice.exists() {
            let root_mtime = voice_file.metadata().ok().and_then(|m| m.modified().ok());
            let mb_mtime = mb_voice.metadata().ok().and_then(|m| m.modified().ok());
            match (root_mtime, mb_mtime) {
                (Some(r), Some(s)) => r > s,
                _ => true,
            }
        } else {
            true
        };
        if should_copy {
            std::fs::copy(&voice_file, &mb_voice)?;
            println!("  Updated voice.md");
        }
    }

    // Stage, commit, push any local changes
    run_git(&["git", "-C", &sp, "add", "-A"]);

    let (status_out, _, _) = run_git(&["git", "-C", &sp, "status", "--porcelain"]);
    if !status_out.trim().is_empty() {
        run_git(&[
            "git",
            "-C",
            &sp,
            "commit",
            "-m",
            "Sync shared conversations",
        ]);
        let (_, stderr, code) = run_git(&["git", "-C", &sp, "push"]);
        if code == 0 {
            println!("  Pushed changes");
        } else {
            println!("  Push failed: {}", stderr.trim());
        }
    } else {
        println!("  No local changes to push");
    }

    // Update submodule ref in parent
    run_git(&["git", "add", &sp]);

    Ok(())
}

/// corky mailbox sync [NAME]
pub fn run(name: Option<&str>) -> Result<()> {
    let config = corky_config::try_load_config(None);
    let mailbox_names: Vec<String> = config
        .as_ref()
        .map(|c| c.mailboxes.keys().cloned().collect())
        .unwrap_or_default();

    if mailbox_names.is_empty() {
        println!("No mailboxes configured in .corky.toml");
        return Ok(());
    }

    let names: Vec<String> = if let Some(n) = name {
        if !mailbox_names.contains(&n.to_string()) {
            anyhow::bail!("Unknown mailbox: {}", n);
        }
        vec![n.to_string()]
    } else {
        mailbox_names
    };

    for n in &names {
        sync_one(n)?;
    }

    Ok(())
}

/// corky mailbox status
pub fn status() -> Result<()> {
    let config = corky_config::try_load_config(None);
    let mailbox_names: Vec<String> = config
        .as_ref()
        .map(|c| c.mailboxes.keys().cloned().collect())
        .unwrap_or_default();

    if mailbox_names.is_empty() {
        println!("No mailboxes configured in .corky.toml");
        return Ok(());
    }

    println!("Mailbox status:");
    for name in &mailbox_names {
        let mb_path = resolve::mailbox_dir(name);
        if mb_path.exists() {
            if is_git_repo(&mb_path) {
                mailbox_status(name, &mb_path);
            } else {
                println!("  {}: plain directory", name);
            }
        } else {
            println!("  {}: not found", name);
        }
    }

    Ok(())
}
