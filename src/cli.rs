use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "corrkit", version, about = "Sync email threads from IMAP to Markdown, draft replies, manage collaborators", disable_help_subcommand = true)]
pub struct Cli {
    /// Use a named space from app config
    #[arg(long, global = true)]
    pub space: Option<String>,

    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Initialize a new project directory
    Init {
        /// Project directory (default: current directory)
        #[arg(value_name = "PATH", default_value = ".")]
        path: PathBuf,

        /// Email address
        #[arg(long)]
        user: String,

        /// Install the email skill to .claude/skills/email/
        #[arg(long)]
        with_skill: bool,

        /// Email provider
        #[arg(long, default_value = "gmail", value_parser = ["gmail", "protonmail-bridge", "imap"])]
        provider: String,

        /// Shell command to retrieve password
        #[arg(long, default_value = "")]
        password_cmd: String,

        /// Comma-separated labels
        #[arg(long, default_value = "correspondence")]
        labels: String,

        /// GitHub username
        #[arg(long, default_value = "")]
        github_user: String,

        /// Display name
        #[arg(long, default_value = "")]
        name: String,

        /// Run first sync after setup
        #[arg(long)]
        sync: bool,

        /// Space name to register
        #[arg(long = "space-name", default_value = "default")]
        space_name: String,

        /// Overwrite existing accounts.toml
        #[arg(long)]
        force: bool,
    },

    /// Sync email threads to Markdown
    Sync {
        /// Ignore saved state and re-fetch all messages
        #[arg(long)]
        full: bool,

        /// Sync only the named account
        #[arg(long)]
        account: Option<String>,
    },

    /// Gmail OAuth setup
    SyncAuth,

    /// List IMAP folders for an account
    ListFolders {
        /// Account name from accounts.toml
        account: Option<String>,
    },

    /// Push a draft markdown file as an email draft
    PushDraft {
        /// Path to the draft markdown file
        file: PathBuf,

        /// Send the email immediately instead of saving as a draft
        #[arg(long)]
        send: bool,
    },

    /// Add a label to an account's sync config
    AddLabel {
        /// Label to add
        label: String,

        /// Account name in accounts.toml
        #[arg(long)]
        account: String,
    },

    /// Add a new contact
    ContactAdd {
        /// Contact name
        name: String,

        /// Email address(es)
        #[arg(long = "email", required = true)]
        emails: Vec<String>,

        /// Conversation label(s)
        #[arg(long = "label")]
        labels: Vec<String>,

        /// Bind contact labels to a specific account
        #[arg(long, default_value = "")]
        account: String,
    },

    /// IMAP polling daemon
    Watch {
        /// Poll interval in seconds
        #[arg(long)]
        interval: Option<u64>,
    },

    /// List configured spaces
    Spaces,

    /// Install an agent skill
    InstallSkill {
        /// Skill name (currently: email)
        name: String,
    },

    /// Audit instruction files
    AuditDocs,

    /// Show command reference
    Help {
        /// Filter commands by name
        filter: Option<String>,
    },

    /// Collaborator commands (outgoing)
    #[command(subcommand)]
    For(ForCommands),

    /// Collaborator commands (incoming)
    #[command(subcommand)]
    By(ByCommands),
}

#[derive(Subcommand)]
pub enum ForCommands {
    /// Add a new collaborator
    Add {
        /// Collaborator's GitHub username
        github_user: String,

        /// Gmail label(s) to share
        #[arg(long = "label", required = true)]
        labels: Vec<String>,

        /// Display name for the collaborator
        #[arg(long, default_value = "")]
        name: String,

        /// Use PAT-based access instead of GitHub collaborator invite
        #[arg(long)]
        pat: bool,

        /// Create the shared repo as public
        #[arg(long)]
        public: bool,

        /// Bind collaborator labels to a specific account name
        #[arg(long, default_value = "")]
        account: String,

        /// GitHub org/user for the shared repo
        #[arg(long, default_value = "")]
        org: String,
    },

    /// Push/pull shared submodules
    Sync {
        /// Collaborator GitHub username (default: all)
        name: Option<String>,
    },

    /// Check for pending changes
    Status,

    /// Remove a collaborator
    Remove {
        /// Collaborator GitHub username to remove
        name: String,

        /// Also delete the GitHub repo
        #[arg(long)]
        delete_repo: bool,
    },

    /// Rename a collaborator directory
    Rename {
        /// Current collaborator name
        old_name: String,

        /// New collaborator name
        new_name: String,

        /// Also rename the GitHub repo
        #[arg(long)]
        rename_repo: bool,
    },

    /// Pull, regenerate templates, commit & push
    Reset {
        /// Collaborator GitHub username (default: all)
        name: Option<String>,

        /// Regenerate files without pulling/pushing
        #[arg(long)]
        no_sync: bool,
    },
}

#[derive(Subcommand)]
pub enum ByCommands {
    /// Find threads awaiting a reply
    FindUnanswered {
        /// Name to match as 'your' messages
        #[arg(long = "from", default_value = "Brian")]
        from_name: String,
    },

    /// Validate draft markdown files
    ValidateDraft {
        /// Draft markdown file(s) to validate
        #[arg(required = true)]
        files: Vec<PathBuf>,
    },
}

