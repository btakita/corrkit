//! Publish orchestration: draft → resolve author → get token → upload images → API → update draft.

use anyhow::{bail, Result};
use chrono::Utc;
use std::path::Path;

use super::draft::{DraftStatus, SocialDraft};
use super::linkedin;
use super::platform::Platform;
use super::profiles::ProfilesFile;
use super::token_store::TokenStore;

/// Publish a social draft file. When `dry_run` is true, validates everything
/// (auth, images) but prints the payload instead of creating the post.
pub fn publish(path: &Path, dry_run: bool) -> Result<()> {
    let content = std::fs::read_to_string(path)?;
    let draft = SocialDraft::parse(&content)?;

    // PB1: Check status
    // - Published → always reject (prevents double-publish)
    // - Draft + scheduled_at set → allowed (scheduling implies readiness)
    // - Draft + no scheduled_at + not dry-run → reject (manual publish requires ready)
    // - Ready → always allowed
    // - dry-run → always allowed (for testing)
    if draft.meta.status == DraftStatus::Published {
        bail!(
            "Draft has already been published.\n\
             Published at: {}",
            draft.meta.published_at.map(|t| t.to_string()).unwrap_or_default()
        );
    }
    if !dry_run && draft.meta.status != DraftStatus::Ready && draft.meta.scheduled_at.is_none() {
        bail!(
            "Draft is not ready for publishing (status: draft).\n\
             Set status to 'ready' or add scheduled_at to the frontmatter."
        );
    }

    // Resolve author in profiles.toml
    let profiles = ProfilesFile::load()?;
    let platform = draft.meta.platform;
    let author = &draft.meta.author;

    // PB3: Author not in profiles.toml
    let urn = profiles.resolve_urn(author, platform)?;

    // PB5/PB6: Token lookup
    let store = TokenStore::load()?;
    let token = store.get_valid(&urn).ok_or_else(|| {
        if store.tokens.contains_key(&urn) {
            anyhow::anyhow!(
                "Token for {} ({}) has expired.\n\
                 Run `corky linkedin auth` to re-authenticate.",
                author,
                urn,
            )
        } else {
            anyhow::anyhow!(
                "No token found for {} ({}).\n\
                 Run `corky linkedin auth --profile {}` to authenticate.",
                author,
                urn,
                author
            )
        }
    })?;

    // Upload images if present (even in dry-run, to verify they work)
    let image_urns = upload_images(path, &draft, &token.access_token, &urn, platform)?;

    if dry_run {
        println!("[dry-run] Validation passed. Would publish to {}.", platform);
        println!("[dry-run] Author: {} ({})", author, urn);
        println!("[dry-run] Visibility: {}", draft.meta.visibility);
        if !image_urns.is_empty() {
            println!("[dry-run] Images uploaded: {}", image_urns.len());
            for (i, urn) in image_urns.iter().enumerate() {
                println!("[dry-run]   {}: {}", i + 1, urn);
            }
        }
        println!("[dry-run] Body ({} chars):", draft.body.len());
        println!("---");
        println!("{}", draft.body.trim());
        println!("---");
        println!("[dry-run] No post created. Set status to 'ready' and run without --dry-run to publish.");
        return Ok(());
    }

    // Call platform API
    let (post_id, post_url) = match platform {
        Platform::LinkedIn => {
            linkedin::create_post(
                &token.access_token,
                &urn,
                &draft.body,
                &draft.meta.visibility,
                &image_urns,
            )?
        }
        _ => bail!("Publishing not yet implemented for {}", platform),
    };

    // Update draft frontmatter
    let mut draft = draft;
    draft.meta.status = DraftStatus::Published;
    draft.meta.post_id = Some(post_id.clone());
    draft.meta.post_url = Some(post_url.clone());
    draft.meta.published_at = Some(Utc::now());

    let rendered = draft.render()?;
    std::fs::write(path, rendered)?;

    println!("Published to {}: {}", platform, post_url);
    Ok(())
}

/// Resolve image paths relative to the draft file and upload them.
/// Returns a list of image URNs for the platform API.
fn upload_images(
    draft_path: &Path,
    draft: &SocialDraft,
    access_token: &str,
    author_urn: &str,
    platform: Platform,
) -> Result<Vec<String>> {
    if draft.meta.images.is_empty() {
        return Ok(vec![]);
    }

    let draft_dir = draft_path
        .parent()
        .ok_or_else(|| anyhow::anyhow!("Cannot determine parent directory of draft file"))?;

    let mut urns = Vec::new();
    for image_path_str in &draft.meta.images {
        let image_path = draft_dir.join(image_path_str);
        if !image_path.exists() {
            bail!(
                "Image file not found: {} (resolved from draft directory: {})",
                image_path.display(),
                draft_dir.display()
            );
        }

        let image_bytes = std::fs::read(&image_path)?;

        let urn = match platform {
            Platform::LinkedIn => linkedin::upload_image(access_token, author_urn, &image_bytes)?,
            _ => bail!("Image upload not yet implemented for {}", platform),
        };

        urns.push(urn);
    }

    Ok(urns)
}
