use anyhow::Result;
use clap::Parser;

use corky::cli::{Cli, Commands, MailboxCommands, SyncCommands};

fn main() -> Result<()> {
    let cli = Cli::parse();

    // Handle --mailbox: resolve named mailbox and set CORKY_DATA
    if let Some(ref mailbox_name) = cli.mailbox {
        let path = corky::app_config::resolve_mailbox(Some(mailbox_name))?;
        if let Some(p) = path {
            std::env::set_var("CORKY_DATA", p.to_string_lossy().as_ref());
        } else {
            eprintln!("No mailboxes configured. Run 'corky init' first.");
            std::process::exit(1);
        }
    }

    match cli.command {
        Commands::Init {
            path,
            user,
            with_skill,
            provider,
            password_cmd,
            labels,
            github_user,
            name,
            sync,
            mailbox_name,
            force,
        } => corky::init::run(
            &user,
            &path,
            &provider,
            &password_cmd,
            &labels,
            &github_user,
            &name,
            sync,
            &mailbox_name,
            force,
            with_skill,
        ),
        Commands::Sync { command } => match command {
            None => corky::sync::run(false, None),
            Some(SyncCommands::Full) => corky::sync::run(true, None),
            Some(SyncCommands::Account { name }) => corky::sync::run(false, Some(&name)),
            Some(SyncCommands::Routes) => corky::sync::routes::run(),
            Some(SyncCommands::Mailbox { name }) => corky::mailbox::sync::run(name.as_deref()),
        },
        Commands::SyncAuth => corky::sync::auth::run(),
        Commands::ListFolders { account } => corky::sync::folders::run(account.as_deref()),
        Commands::PushDraft { file, send } => corky::draft::run(&file, send),
        Commands::AddLabel { label, account } => corky::accounts::add_label_cmd(&label, &account),
        Commands::ContactAdd {
            name,
            emails,
            labels,
            account,
        } => corky::contact::add::run(&name, &emails, &labels, &account),
        Commands::Watch { interval } => corky::watch::run(interval),
        Commands::InstallSkill { name } => corky::skill::run(&name),
        Commands::AuditDocs => corky::audit_docs::run(),
        Commands::Help { filter } => corky::help::run(filter.as_deref()),
        Commands::FindUnanswered { from_name } => {
            corky::mailbox::find_unanswered::run(&from_name)
        }
        Commands::ValidateDraft { files } => corky::mailbox::validate_draft::run(&files),
        Commands::Mailbox(cmd) => match cmd {
            MailboxCommands::List => corky::mailbox::list::run(),
            MailboxCommands::Add {
                name,
                labels,
                display_name,
                github,
                github_user,
                pat,
                public,
                account,
                org,
            } => corky::mailbox::add::run(
                &name,
                &labels,
                &display_name,
                github,
                &github_user,
                pat,
                public,
                &account,
                &org,
            ),
            MailboxCommands::Sync { name } => corky::mailbox::sync::run(name.as_deref()),
            MailboxCommands::Status => corky::mailbox::sync::status(),
            MailboxCommands::Remove { name, delete_repo } => {
                corky::mailbox::remove::run(&name, delete_repo)
            }
            MailboxCommands::Rename {
                old_name,
                new_name,
                rename_repo,
            } => corky::mailbox::rename::run(&old_name, &new_name, rename_repo),
            MailboxCommands::Reset { name, no_sync } => {
                corky::mailbox::reset::run(name.as_deref(), no_sync)
            }
        },
    }
}
