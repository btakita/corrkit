//! Initialize a new corrkit project directory with config and folder structure.

use anyhow::Result;
use std::path::{Path, PathBuf};

use crate::accounts::provider_presets;
use crate::app_config;

const VOICE_MD: &str = include_str!("../voice.md");

/// Create the data directory structure with .gitkeep files.
fn create_dirs(data_dir: &Path) -> Result<()> {
    for sub in &["conversations", "drafts", "contacts"] {
        let d = data_dir.join(sub);
        std::fs::create_dir_all(&d)?;
        let gitkeep = d.join(".gitkeep");
        if !gitkeep.exists() {
            std::fs::write(&gitkeep, "")?;
        }
    }
    Ok(())
}

/// Generate accounts.toml content.
fn generate_accounts_toml(
    user: &str,
    provider: &str,
    password_cmd: &str,
    labels: &[String],
    github_user: &str,
    name: &str,
) -> String {
    let mut doc = toml_edit::DocumentMut::new();

    // Owner section
    if !github_user.is_empty() || !name.is_empty() {
        let mut owner = toml_edit::Table::new();
        if !github_user.is_empty() {
            owner.insert("github_user", toml_edit::value(github_user));
        }
        if !name.is_empty() {
            owner.insert("name", toml_edit::value(name));
        }
        doc.insert("owner", toml_edit::Item::Table(owner));
    }

    // Account section
    let mut accounts = toml_edit::Table::new();
    let mut default_acct = toml_edit::Table::new();
    default_acct.insert("provider", toml_edit::value(provider));
    default_acct.insert("user", toml_edit::value(user));
    let mut labels_arr = toml_edit::Array::new();
    for label in labels {
        labels_arr.push(label.as_str());
    }
    default_acct.insert("labels", toml_edit::value(labels_arr));
    default_acct.insert("default", toml_edit::value(true));
    if !password_cmd.is_empty() {
        default_acct.insert("password_cmd", toml_edit::value(password_cmd));
    }
    accounts.insert("default", toml_edit::Item::Table(default_acct));
    doc.insert("accounts", toml_edit::Item::Table(accounts));

    doc.to_string()
}

/// Find the git repo root containing `start`.
fn find_git_root(start: &Path) -> Option<PathBuf> {
    let mut dir = start.to_path_buf();
    loop {
        if dir.join(".git").exists() {
            return Some(dir);
        }
        if !dir.pop() {
            return None;
        }
    }
}

/// Ensure an entry exists in .gitignore at the repo root.
fn ensure_gitignore_entry(repo_root: &Path, entry: &str) -> Result<()> {
    let gitignore = repo_root.join(".gitignore");
    if gitignore.exists() {
        let content = std::fs::read_to_string(&gitignore)?;
        for line in content.lines() {
            if line.trim() == entry {
                return Ok(());
            }
        }
        // Append entry, ensuring a newline before it
        let suffix = if content.ends_with('\n') || content.is_empty() {
            format!("{}\n", entry)
        } else {
            format!("\n{}\n", entry)
        };
        std::fs::write(&gitignore, format!("{}{}", content, suffix))?;
    } else {
        std::fs::write(&gitignore, format!("{}\n", entry))?;
    }
    println!("Added '{}' to {}", entry, gitignore.display());
    Ok(())
}

/// Install voice.md into the project directory if not present.
fn install_voice_md(project_dir: &Path) -> Result<()> {
    let path = project_dir.join("voice.md");
    if path.exists() {
        return Ok(());
    }
    std::fs::write(&path, VOICE_MD)?;
    println!("Created {}", path.display());
    Ok(())
}

#[allow(clippy::too_many_arguments)]
pub fn run(
    user: &str,
    path: &Path,
    provider: &str,
    password_cmd: &str,
    labels_str: &str,
    github_user: &str,
    name: &str,
    sync: bool,
    space: &str,
    force: bool,
    with_skill: bool,
) -> Result<()> {
    // 1. Resolve project path
    let path = if path.starts_with("~") {
        crate::resolve::expand_tilde(&path.to_string_lossy())
    } else {
        path.to_path_buf()
    };
    std::fs::create_dir_all(&path)?;
    let path = path.canonicalize()?;

    let data_dir = path.join("correspondence");

    let labels: Vec<String> = labels_str
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    let accounts_path = path.join("accounts.toml");
    if accounts_path.exists() && !force {
        eprintln!("accounts.toml already exists at {}", accounts_path.display());
        eprintln!("Use --force to overwrite.");
        std::process::exit(1);
    }

    // 2. Create correspondence/{conversations,drafts,contacts}/
    create_dirs(&data_dir)?;
    println!(
        "Created {}/{{conversations,drafts,contacts}}/",
        data_dir.display()
    );

    // 3. Generate config files at project root
    let content =
        generate_accounts_toml(user, provider, password_cmd, &labels, github_user, name);
    std::fs::write(&accounts_path, &content)?;
    println!("Created {}", accounts_path.display());

    for filename in &["collaborators.toml", "contacts.toml"] {
        let p = path.join(filename);
        if !p.exists() {
            std::fs::write(&p, "")?;
            println!("Created {}", p.display());
        }
    }

    // 4. Install voice.md
    install_voice_md(&path)?;

    // 5. Add correspondence to .gitignore if in a git repo
    if let Some(repo_root) = find_git_root(&path) {
        ensure_gitignore_entry(&repo_root, "correspondence")?;
    }

    // 6. Install email skill if requested
    if with_skill {
        crate::skill::install("email", &path)?;
    }

    // 7. Register space in app config
    app_config::add_space(space, &path.to_string_lossy())?;
    println!(
        "Registered space '{}' \u{2192} {}",
        space,
        path.display()
    );

    // 8. Provider-specific guidance
    let presets = provider_presets();
    if provider == "gmail" && password_cmd.is_empty() {
        println!();
        println!("Gmail setup:");
        println!("  Option A: App password \u{2014} https://myaccount.google.com/apppasswords");
        println!("    Add password_cmd = \"pass email/personal\" to accounts.toml");
        println!("  Option B: OAuth \u{2014} run 'corrkit sync-auth' after placing credentials.json");
    }

    // 9. Optional first sync
    if sync {
        std::env::set_var("CORRKIT_DATA", data_dir.to_string_lossy().as_ref());
        println!();
        crate::sync::run(false, None)?;
    }

    if !sync {
        println!();
        println!("Done! Next steps:");
        println!("  - Edit {} with your credentials", accounts_path.display());
        if provider == "gmail" && password_cmd.is_empty() {
            println!("  - Set up app password or OAuth (see above)");
        }
        if !presets.contains_key(provider) && provider == "imap" {
            println!("  - Add imap_host, smtp_host to accounts.toml");
        }
        println!("  - Run: corrkit sync");
        if !with_skill {
            println!("  - Run: corrkit install-skill email  (to add the email agent skill)");
        }
    }

    Ok(())
}
