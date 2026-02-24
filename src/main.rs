use anyhow::Result;
use clap::Parser;

use corky::cli::{Cli, Commands, ContactCommands, DraftCommands, MailboxCommands, SlackCommands, SyncCommands};

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


    // Warn about available upgrades (skip if running the upgrade command itself)
    if !matches!(cli.command, Commands::Upgrade) {
        corky::upgrade::warn_if_outdated();
    }

    match cli.command {
        Commands::Init {
            path,
            user,
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
        ),
        Commands::Sync { command } => match command {
            None => corky::sync::run(false, None),
            Some(SyncCommands::Full) => corky::sync::run(true, None),
            Some(SyncCommands::Account { name }) => corky::sync::run(false, Some(&name)),
            Some(SyncCommands::Routes) => corky::sync::routes::run(),
            Some(SyncCommands::Mailbox { name }) => corky::mailbox::sync::run(name.as_deref()),
            Some(SyncCommands::TelegramImport { path, label, account }) => {
                let out_dir = corky::resolve::conversations_dir();
                corky::sync::telegram_import::run(&path, &label, &out_dir, &account)
            }
        },
        Commands::SyncAuth => corky::sync::auth::run(),
        Commands::ListFolders { account } => corky::sync::folders::run(account.as_deref()),
        Commands::PushDraft { file, send } => corky::draft::run(&file, send),
        Commands::AddLabel { label, account } => corky::accounts::add_label_cmd(&label, &account),
        Commands::Contact(cmd) => match cmd {
            ContactCommands::Add { name, emails, from } => {
                if let Some(slug) = from {
                    corky::contact::from_conversation::run(&slug, name.as_deref())
                } else {
                    let name = name.ok_or_else(|| {
                        anyhow::anyhow!("NAME required when not using --from")
                    })?;
                    corky::contact::add::run(&name, &emails)
                }
            }
            ContactCommands::Info { name } => corky::contact::info::run(&name),
            ContactCommands::Sync => corky::contact::sync::run(),
        },
        Commands::ContactAdd {
            name,
            emails,
            labels: _,
            account: _,
        } => corky::contact::add::run(&name, &emails),
        Commands::Watch { interval } => corky::watch::run(interval),
        Commands::InstallSkill { name } => corky::skill::run(&name),
        Commands::AuditDocs => corky::audit_docs::run(),
        Commands::Help { filter } => corky::help::run(filter.as_deref()),
        Commands::Unanswered { scope, from_name } => {
            let from = resolve_from_name(from_name)?;
            let scope = corky::mailbox::find_unanswered::Scope::from_arg(scope.as_deref());
            corky::mailbox::find_unanswered::run(scope, &from)
        }
        Commands::ValidateDraft { files } => corky::mailbox::validate_draft::run(&files),
        Commands::Draft(cmd) => run_draft_command(cmd),
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
            MailboxCommands::Unanswered { scope, from_name } => {
                let from = resolve_from_name(from_name)?;
                let scope =
                    corky::mailbox::find_unanswered::Scope::from_arg(scope.as_deref());
                corky::mailbox::find_unanswered::run(scope, &from)
            }
            MailboxCommands::Draft(cmd) => run_draft_command(cmd),
        },
        Commands::Slack(cmd) => match cmd {
            SlackCommands::Import { path, label, account } => {
                let out_dir = corky::resolve::conversations_dir();
                corky::sync::slack_import::run(&path, &label, &out_dir, &account)
            }
        },
        Commands::Upgrade => corky::upgrade::run(),
    }
}

fn run_draft_command(cmd: DraftCommands) -> anyhow::Result<()> {
    match cmd {
        DraftCommands::New {
            subject,
            to,
            cc,
            account,
            from,
            in_reply_to,
            mailbox,
        } => corky::draft::new::run(
            &subject,
            &to,
            cc.as_deref(),
            account.as_deref(),
            from.as_deref(),
            in_reply_to.as_deref(),
            mailbox.as_deref(),
        ),
        DraftCommands::Validate { args } => {
            corky::mailbox::validate_draft::run_scoped(&args)
        }
        DraftCommands::Push { file, send } => corky::draft::run(&file, send),
    }
}

/// Resolve the --from name: CLI flag > owner.name in .corky.toml > error.
fn resolve_from_name(from_name: Option<String>) -> anyhow::Result<String> {
    if let Some(name) = from_name {
        return Ok(name);
    }
    if let Some(cfg) = corky::config::corky_config::try_load_config(None) {
        if let Some(owner) = cfg.owner {
            if !owner.name.is_empty() {
                return Ok(owner.name);
            }
        }
    }
    anyhow::bail!(
        "No --from name provided and no [owner] name in .corky.toml.\n\
         Use --from NAME or set name in [owner] section of .corky.toml."
    )
}
