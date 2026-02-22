use anyhow::Result;
use clap::Parser;

use corrkit::cli::{Cli, Commands, MailboxCommands, SyncCommands};

fn main() -> Result<()> {
    let cli = Cli::parse();

    // Handle --mailbox: resolve named mailbox and set CORRKIT_DATA
    if let Some(ref mailbox_name) = cli.mailbox {
        let path = corrkit::app_config::resolve_mailbox(Some(mailbox_name))?;
        if let Some(p) = path {
            std::env::set_var("CORRKIT_DATA", p.to_string_lossy().as_ref());
        } else {
            eprintln!("No mailboxes configured. Run 'corrkit init' first.");
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
        } => corrkit::init::run(
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
            None => corrkit::sync::run(false, None),
            Some(SyncCommands::Full) => corrkit::sync::run(true, None),
            Some(SyncCommands::Account { name }) => corrkit::sync::run(false, Some(&name)),
            Some(SyncCommands::Routes) => corrkit::sync::routes::run(),
            Some(SyncCommands::Mailbox { name }) => corrkit::mailbox::sync::run(name.as_deref()),
        },
        Commands::SyncAuth => corrkit::sync::auth::run(),
        Commands::ListFolders { account } => corrkit::sync::folders::run(account.as_deref()),
        Commands::PushDraft { file, send } => corrkit::draft::run(&file, send),
        Commands::AddLabel { label, account } => corrkit::accounts::add_label_cmd(&label, &account),
        Commands::ContactAdd {
            name,
            emails,
            labels,
            account,
        } => corrkit::contact::add::run(&name, &emails, &labels, &account),
        Commands::Watch { interval } => corrkit::watch::run(interval),
        Commands::InstallSkill { name } => corrkit::skill::run(&name),
        Commands::AuditDocs => corrkit::audit_docs::run(),
        Commands::Help { filter } => corrkit::help::run(filter.as_deref()),
        Commands::FindUnanswered { from_name } => {
            corrkit::mailbox::find_unanswered::run(&from_name)
        }
        Commands::ValidateDraft { files } => corrkit::mailbox::validate_draft::run(&files),
        Commands::Mailbox(cmd) => match cmd {
            MailboxCommands::List => corrkit::mailbox::list::run(),
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
            } => corrkit::mailbox::add::run(
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
            MailboxCommands::Sync { name } => corrkit::mailbox::sync::run(name.as_deref()),
            MailboxCommands::Status => corrkit::mailbox::sync::status(),
            MailboxCommands::Remove { name, delete_repo } => {
                corrkit::mailbox::remove::run(&name, delete_repo)
            }
            MailboxCommands::Rename {
                old_name,
                new_name,
                rename_repo,
            } => corrkit::mailbox::rename::run(&old_name, &new_name, rename_repo),
            MailboxCommands::Reset { name, no_sync } => {
                corrkit::mailbox::reset::run(name.as_deref(), no_sync)
            }
        },
        Commands::Migrate => corrkit::migrate::run(),
    }
}
