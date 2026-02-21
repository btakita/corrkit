//! Install agent skills into a project directory.

use anyhow::{bail, Result};
use std::path::Path;

const EMAIL_SKILL_MD: &str = include_str!("../.claude/skills/email/SKILL.md");
const EMAIL_README_MD: &str = include_str!("../.claude/skills/email/README.md");

/// Install a named skill into a project directory.
/// Currently only "email" is supported.
pub fn install(name: &str, project_dir: &Path) -> Result<()> {
    match name {
        "email" => install_email(project_dir),
        _ => bail!("Unknown skill '{}'. Available: email", name),
    }
}

fn install_email(project_dir: &Path) -> Result<()> {
    let skill_dir = project_dir.join(".claude").join("skills").join("email");
    std::fs::create_dir_all(&skill_dir)?;

    let skill_path = skill_dir.join("SKILL.md");
    if skill_path.exists() {
        println!("  {} already exists, skipping", skill_path.display());
    } else {
        std::fs::write(&skill_path, EMAIL_SKILL_MD)?;
        println!("Created {}", skill_path.display());
    }

    let readme_path = skill_dir.join("README.md");
    if readme_path.exists() {
        println!("  {} already exists, skipping", readme_path.display());
    } else {
        std::fs::write(&readme_path, EMAIL_README_MD)?;
        println!("Created {}", readme_path.display());
    }

    Ok(())
}

/// CLI entry point for `corrkit install-skill`.
pub fn run(name: &str) -> Result<()> {
    let project_dir = std::env::current_dir()?;
    install(name, &project_dir)
}
