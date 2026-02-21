//! Command reference for corrkit.

use anyhow::Result;

const COMMANDS: &[(&str, &str)] = &[
    ("init --user EMAIL [PATH]", "Initialize a new project directory"),
    ("install-skill NAME", "Install an agent skill (e.g. email)"),
    ("sync [--full] [--account NAME]", "Sync email threads to markdown"),
    ("sync-auth", "Gmail OAuth setup"),
    ("list-folders [ACCOUNT]", "List IMAP folders for an account"),
    ("push-draft FILE [--send]", "Save draft to email"),
    ("add-label LABEL --account NAME", "Add a label to an account's sync config"),
    ("contact-add NAME --email EMAIL", "Add a contact with context docs"),
    ("watch [--interval N]", "Poll IMAP and sync on an interval"),
    ("spaces", "List configured spaces"),
    ("audit-docs", "Audit instruction files"),
    ("help", "Show this reference"),
];

const FOR_COMMANDS: &[(&str, &str)] = &[
    ("for add NAME --label LABEL", "Add a collaborator"),
    ("for sync [NAME]", "Push/pull shared submodules"),
    ("for status", "Check for pending changes"),
    ("for remove NAME [--delete-repo]", "Remove a collaborator"),
    ("for rename OLD NEW", "Rename a collaborator directory"),
    ("for reset [NAME] [--no-sync]", "Pull, regenerate templates, commit & push"),
];

const BY_COMMANDS: &[(&str, &str)] = &[
    ("by find-unanswered [--from NAME]", "Find threads awaiting a reply"),
    ("by validate-draft FILE [FILE...]", "Validate draft markdown files"),
];

const DEV_COMMANDS: &[(&str, &str)] = &[
    ("cargo test", "Run tests"),
    ("cargo clippy", "Lint"),
    ("cargo fmt", "Format"),
];

pub fn run(filter: Option<&str>) -> Result<()> {
    if let Some(filter) = filter {
        if filter != "--dev" {
            let all_cmds: Vec<(&str, &str)> = COMMANDS
                .iter()
                .chain(FOR_COMMANDS.iter())
                .chain(BY_COMMANDS.iter())
                .chain(DEV_COMMANDS.iter())
                .copied()
                .collect();
            let matches: Vec<_> = all_cmds
                .iter()
                .filter(|(name, _)| name.contains(filter))
                .collect();
            if matches.is_empty() {
                println!("No command matching '{}'", filter);
                std::process::exit(1);
            }
            print_table(&matches.iter().map(|&&(a, b)| (a, b)).collect::<Vec<_>>());
            return Ok(());
        }
    }

    println!("corrkit commands\n");
    print_table(COMMANDS);

    println!("\ncollaborator commands (for = outbound, by = inbound)\n");
    let collab: Vec<_> = FOR_COMMANDS
        .iter()
        .chain(BY_COMMANDS.iter())
        .copied()
        .collect();
    print_table(&collab);

    if filter == Some("--dev") || filter.is_none() {
        println!("\ndev commands\n");
        print_table(DEV_COMMANDS);
    }

    Ok(())
}

fn print_table(rows: &[(&str, &str)]) {
    let name_w = rows.iter().map(|(n, _)| n.len()).max().unwrap_or(0);
    for (name, desc) in rows {
        println!("  {:<width$}  {}", name, desc, width = name_w);
    }
}
