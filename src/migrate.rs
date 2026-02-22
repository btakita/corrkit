//! Migrate from accounts.toml + collaborators.toml to .corky.toml.

use anyhow::{bail, Result};

use crate::config::collaborator;
use crate::resolve;

/// corky migrate
pub fn run() -> Result<()> {
    let corky_toml = resolve::corky_toml();
    if corky_toml.exists() {
        bail!(
            ".corky.toml already exists at {}.\nMigration is only needed when using the old accounts.toml format.",
            corky_toml.display()
        );
    }

    let accounts_path = resolve::accounts_toml();
    if !accounts_path.exists() {
        bail!(
            "No accounts.toml found at {}.\nNothing to migrate. Run 'corky init' to create a new project.",
            accounts_path.display()
        );
    }

    // Warn if working tree is dirty
    let git_status = std::process::Command::new("git")
        .args(["status", "--porcelain"])
        .output();
    if let Ok(output) = git_status {
        let status = String::from_utf8_lossy(&output.stdout);
        if !status.trim().is_empty() {
            eprintln!("Warning: working tree has uncommitted changes. Consider committing first.");
        }
    }

    // 1. Read accounts.toml
    println!("Reading accounts.toml...");
    let accounts_content = std::fs::read_to_string(&accounts_path)?;

    // 2. Read collaborators.toml
    let collabs_path = resolve::collaborators_toml();
    let collabs = collaborator::load_collaborators(Some(&collabs_path)).unwrap_or_default();

    // 3. Build .corky.toml content
    // Start with the accounts.toml content as a base (preserves owner, accounts, watch)
    let mut doc = accounts_content.parse::<toml_edit::DocumentMut>()?;

    // Add [routing] section from collaborators
    if !collabs.is_empty() {
        let mut routing = toml_edit::Table::new();
        for (gh_user, collab) in &collabs {
            let mb_path = format!("mailboxes/{}", gh_user.to_lowercase());
            for label in &collab.labels {
                let mut arr = toml_edit::Array::new();
                arr.push(&mb_path);
                routing.insert(label, toml_edit::value(arr));
            }
        }
        doc.insert("routing", toml_edit::Item::Table(routing));
    }

    // Add [mailboxes.*] sections
    if !collabs.is_empty() {
        let mut mailboxes = toml_edit::Table::new();
        for gh_user in collabs.keys() {
            let mb_config = toml_edit::Table::new();
            mailboxes.insert(
                &gh_user.to_lowercase(),
                toml_edit::Item::Table(mb_config),
            );
        }
        doc.insert("mailboxes", toml_edit::Item::Table(mailboxes));
    }

    // 4. Write .corky.toml
    let config_dir = resolve::config_dir();
    let new_config_path = config_dir.join(".corky.toml");
    std::fs::write(&new_config_path, doc.to_string())?;
    println!("Created {}", new_config_path.display());

    // 5. Move directories: collabs/{name}/to → mailboxes/{name}
    let data_dir = resolve::data_dir();
    let collabs_dir = data_dir.join("collabs");
    let mailboxes_dir = data_dir.join("mailboxes");

    if collabs_dir.exists() && !collabs.is_empty() {
        std::fs::create_dir_all(&mailboxes_dir)?;

        for gh_user in collabs.keys() {
            let old_path = collabs_dir
                .join(gh_user.to_lowercase())
                .join("to");
            let new_path = mailboxes_dir.join(gh_user.to_lowercase());

            if old_path.exists() {
                println!(
                    "Moving {} \u{2192} {}",
                    old_path.display(),
                    new_path.display()
                );

                // Try git mv first, fall back to regular move
                let result = std::process::Command::new("git")
                    .args([
                        "mv",
                        &old_path.to_string_lossy(),
                        &new_path.to_string_lossy(),
                    ])
                    .output();

                match result {
                    Ok(output) if output.status.success() => {}
                    _ => {
                        // Fall back to regular move
                        std::fs::rename(&old_path, &new_path)?;
                    }
                }
            }
        }

        // Clean up empty collabs directories
        for gh_user in collabs.keys() {
            let user_dir = collabs_dir.join(gh_user.to_lowercase());
            if user_dir.exists() && is_dir_empty(&user_dir) {
                let _ = std::fs::remove_dir(&user_dir);
            }
        }
        if collabs_dir.exists() && is_dir_empty(&collabs_dir) {
            let _ = std::fs::remove_dir(&collabs_dir);
        }
    }

    // 6. Print summary
    println!();
    println!("Migration complete!");
    println!("  - Created .corky.toml from accounts.toml");
    if !collabs.is_empty() {
        println!(
            "  - Converted {} collaborator(s) to mailbox config",
            collabs.len()
        );
        println!("  - Moved collabs/*/to/ directories to mailboxes/");
    }
    println!();
    println!("You can now remove the old config files:");
    println!("  rm accounts.toml collaborators.toml");

    Ok(())
}

fn is_dir_empty(path: &std::path::Path) -> bool {
    std::fs::read_dir(path)
        .map(|mut d| d.next().is_none())
        .unwrap_or(true)
}
