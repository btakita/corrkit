//! Social media posting module.

pub mod auth;
pub mod draft;
pub mod linkedin;
pub mod platform;
pub mod profiles;
pub mod publish;
pub mod token_store;

use anyhow::{bail, Result};
use std::path::Path;

use crate::resolve;
use crate::util;
use draft::{DraftStatus, SocialDraft, SocialDraftMeta};
use platform::Platform;
use profiles::ProfilesFile;

/// Run the `social auth` command.
pub fn run_auth(platform_str: &str, profile: Option<&str>) -> Result<()> {
    let platform: Platform = platform_str.parse()?;
    auth::run(platform, profile)
}

/// Run the `social draft` command: create a new social draft file.
pub fn run_draft(
    platform_str: &str,
    body: Option<&str>,
    author: Option<&str>,
    visibility: &str,
    tags: &[String],
) -> Result<()> {
    let platform: Platform = platform_str.parse()?;

    let author = match author {
        Some(a) => a.to_string(),
        None => {
            // Try to get default from .corky.toml owner
            if let Some(cfg) = crate::config::corky_config::try_load_config(None) {
                if let Some(owner) = &cfg.owner {
                    if !owner.name.is_empty() {
                        owner.name.clone()
                    } else {
                        bail!("No --author given and no [owner] name in .corky.toml")
                    }
                } else {
                    bail!("No --author given and no [owner] section in .corky.toml")
                }
            } else {
                bail!("No --author given and no .corky.toml found")
            }
        }
    };

    let meta = SocialDraftMeta {
        platform,
        author,
        visibility: visibility.to_string(),
        status: DraftStatus::Draft,
        tags: tags.to_vec(),
        scheduled_at: None,
        published_at: None,
        post_id: None,
        post_url: None,
        images: vec![],
    };

    let body_text = body.unwrap_or("").to_string();
    let social_draft = SocialDraft::new(meta, body_text);
    let rendered = social_draft.render()?;

    // Create file in social/ directory
    let social_dir = resolve::social_dir();
    std::fs::create_dir_all(&social_dir)?;

    let slug = generate_draft_slug(platform);
    let file_path = social_dir.join(format!("{}.md", slug));

    std::fs::write(&file_path, rendered)?;
    println!("Created social draft: {}", file_path.display());
    Ok(())
}

/// Generate a slug for a social draft file.
fn generate_draft_slug(platform: Platform) -> String {
    let now = chrono::Local::now();
    format!("{}-{}", now.format("%Y%m%d-%H%M%S"), platform)
}

/// Run the `social publish` command.
pub fn run_publish(file: &Path) -> Result<()> {
    publish::publish(file)
}

/// Run the `social check` command: validate profiles.toml.
pub fn run_check() -> Result<()> {
    let path = resolve::profiles_toml();
    if !path.exists() {
        println!("profiles.toml not found at {}", path.display());
        println!("\nCreate it with content like:");
        println!("  [btakita]");
        println!("  [btakita.linkedin]");
        println!("  handle = \"brian-takita\"");
        println!("  urn = \"urn:li:person:abc123\"");
        return Ok(());
    }

    let profiles = ProfilesFile::load_from(&path)?;
    let result = profiles.validate();

    if result.errors.is_empty() && result.warnings.is_empty() && result.info.is_empty() {
        println!("profiles.toml OK ({} profiles)", profiles.profiles.len());
        return Ok(());
    }

    for msg in &result.errors {
        eprintln!("ERROR: {}", msg);
    }
    for msg in &result.warnings {
        eprintln!("WARNING: {}", msg);
    }
    for msg in &result.info {
        println!("INFO: {}", msg);
    }

    if !result.is_ok() {
        bail!("profiles.toml has {} error(s)", result.errors.len());
    }
    Ok(())
}

/// Run the `social list` command: list social drafts.
pub fn run_list(status_filter: Option<&str>) -> Result<()> {
    let social_dir = resolve::social_dir();
    if !social_dir.exists() {
        println!("No social drafts found.");
        return Ok(());
    }

    let filter: Option<DraftStatus> = status_filter
        .map(|s| s.parse())
        .transpose()?;

    let mut entries: Vec<_> = std::fs::read_dir(&social_dir)?
        .filter_map(|e| e.ok())
        .filter(|e| e.path().extension().map(|x| x == "md").unwrap_or(false))
        .collect();
    entries.sort_by_key(|e| e.file_name());

    let mut count = 0;
    for entry in entries {
        let content = std::fs::read_to_string(entry.path())?;
        if let Ok(draft) = SocialDraft::parse(&content) {
            if let Some(ref f) = filter {
                if draft.meta.status != *f {
                    continue;
                }
            }
            let name = entry.file_name();
            let name_str = name.to_string_lossy();
            let preview = util::truncate_preview(&draft.body, 60);
            println!(
                "  {} [{}] {} @{} — {}",
                name_str,
                draft.meta.status,
                draft.meta.platform,
                draft.meta.author,
                preview,
            );
            count += 1;
        }
    }

    if count == 0 {
        println!("No social drafts found.");
    }
    Ok(())
}

/// Run the `social rename-author` command.
pub fn run_rename_author(old: &str, new: &str) -> Result<()> {
    let mut count = 0;

    // Rename in profiles.toml
    let profiles_path = resolve::profiles_toml();
    if profiles_path.exists() {
        let content = std::fs::read_to_string(&profiles_path)?;
        let mut profiles: ProfilesFile = toml::from_str(&content)?;
        if let Some(profile) = profiles.profiles.remove(old) {
            profiles.profiles.insert(new.to_string(), profile);
            let updated = toml::to_string_pretty(&profiles)?;
            std::fs::write(&profiles_path, updated)?;
            println!("Renamed profile '{}' -> '{}' in profiles.toml", old, new);
            count += 1;
        }
    }

    // Rename in social drafts
    let social_dir = resolve::social_dir();
    if social_dir.exists() {
        for entry in std::fs::read_dir(&social_dir)? {
            let entry = entry?;
            if entry.path().extension().map(|x| x == "md").unwrap_or(false) {
                let content = std::fs::read_to_string(entry.path())?;
                if let Ok(mut draft) = SocialDraft::parse(&content) {
                    if draft.meta.author == old {
                        draft.meta.author = new.to_string();
                        let rendered = draft.render()?;
                        std::fs::write(entry.path(), rendered)?;
                        println!("Updated author in {}", entry.path().display());
                        count += 1;
                    }
                }
            }
        }
    }

    if count == 0 {
        println!("No references to '{}' found.", old);
    } else {
        println!("Renamed {} reference(s).", count);
    }
    Ok(())
}
