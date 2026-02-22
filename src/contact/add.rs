//! Add a new contact: scaffold mail/contacts/{name}/ with AGENTS.md.

use anyhow::Result;

use crate::config::contact::{load_contacts, save_contacts, Contact};
use crate::resolve;

fn generate_agents_md(name: &str) -> String {
    format!(
        r#"# Contact: {name}

Context for drafting emails to or about {name}.

## Relationship

<!-- How you know this person, what they work on, shared history -->

## Tone

<!-- Communication style for this person.
     Defaults to voice.md; note overrides here.
     e.g. "More formal than usual" or "Very casual, first-name basis" -->

## Topics

<!-- Recurring subjects, current projects, things to reference or avoid -->

## Notes

<!-- Freeform: quirks, preferences, pending items, important dates -->
"#,
        name = name,
    )
}

pub fn run(name: &str, emails: &[String], labels: &[String], account: &str) -> Result<()> {
    // Check not already configured
    let mut contacts = load_contacts(None)?;
    if contacts.contains_key(name) {
        anyhow::bail!("Contact '{}' already exists in contacts.toml", name);
    }

    let contact_dir = resolve::contacts_dir().join(name);
    if contact_dir.exists() {
        anyhow::bail!("Directory {} already exists", contact_dir.display());
    }

    // 1. Create contact directory with AGENTS.md + CLAUDE.md symlink
    std::fs::create_dir_all(&contact_dir)?;
    let agents_md = contact_dir.join("AGENTS.md");
    std::fs::write(&agents_md, generate_agents_md(name))?;

    #[cfg(unix)]
    std::os::unix::fs::symlink("AGENTS.md", contact_dir.join("CLAUDE.md"))?;

    println!("Created {}/AGENTS.md", contact_dir.display());

    // 2. Update contacts.toml
    contacts.insert(
        name.to_string(),
        Contact {
            emails: emails.to_vec(),
            labels: labels.to_vec(),
            account: account.to_string(),
        },
    );
    save_contacts(&contacts, None)?;
    println!("Updated contacts.toml");

    // 3. Add labels to account sync config if both --label and --account given
    if !labels.is_empty() && !account.is_empty() {
        for label in labels {
            match crate::accounts::add_label_to_account(account, label, None) {
                Ok(true) => {
                    println!(
                        "Added label '{}' to account '{}' in accounts.toml",
                        label, account
                    );
                }
                Ok(false) => {}
                Err(e) => {
                    eprintln!("Warning: failed to add label to account: {}", e);
                }
            }
        }
    }

    // 4. Next steps
    println!();
    println!("Done! Next steps:");
    println!(
        "  - Edit {}/AGENTS.md with relationship context",
        contact_dir.display()
    );
    if labels.is_empty() {
        println!("  - Add --label flags or edit contacts.toml to map conversation labels");
    }

    Ok(())
}
