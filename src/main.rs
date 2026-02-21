use anyhow::Result;
use clap::Parser;

use corrkit::cli::{ByCommands, Cli, Commands, ForCommands};

fn main() -> Result<()> {
    let cli = Cli::parse();

    // Handle --space: resolve named space and set CORRKIT_DATA
    if let Some(ref space_name) = cli.space {
        let path = corrkit::app_config::resolve_space(Some(space_name))?;
        if let Some(p) = path {
            std::env::set_var("CORRKIT_DATA", p.to_string_lossy().as_ref());
        } else {
            eprintln!("No spaces configured. Run 'corrkit init' first.");
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
            space_name,
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
            &space_name,
            force,
            with_skill,
        ),
        Commands::Sync { full, account } => corrkit::sync::run(full, account.as_deref()),
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
        Commands::Spaces => corrkit::spaces::run(),
        Commands::AuditDocs => corrkit::audit_docs::run(),
        Commands::Help { filter } => corrkit::help::run(filter.as_deref()),
        Commands::For(cmd) => match cmd {
            ForCommands::Add {
                github_user,
                labels,
                name,
                pat,
                public,
                account,
                org,
            } => corrkit::collab::add::run(&github_user, &labels, &name, pat, public, &account, &org),
            ForCommands::Sync { name } => corrkit::collab::sync::run(name.as_deref()),
            ForCommands::Status => corrkit::collab::sync::status(),
            ForCommands::Remove { name, delete_repo } => {
                corrkit::collab::remove::run(&name, delete_repo)
            }
            ForCommands::Rename {
                old_name,
                new_name,
                rename_repo,
            } => corrkit::collab::rename::run(&old_name, &new_name, rename_repo),
            ForCommands::Reset { name, no_sync } => {
                corrkit::collab::reset::run(name.as_deref(), no_sync)
            }
        },
        Commands::By(cmd) => match cmd {
            ByCommands::FindUnanswered { from_name } => {
                corrkit::collab::find_unanswered::run(&from_name)
            }
            ByCommands::ValidateDraft { files } => corrkit::collab::validate_draft::run(&files),
        },
    }
}
