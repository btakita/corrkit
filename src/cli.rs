use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "corky", version, about = "Sync email threads from IMAP to Markdown, draft replies, manage mailboxes", disable_help_subcommand = true)]
pub struct Cli {
    /// Use a named mailbox from app config
    #[arg(long, global = true)]
    pub mailbox: Option<String>,

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

        /// Mailbox name to register
        #[arg(long = "mailbox-name", default_value = "default")]
        mailbox_name: String,

        /// Overwrite existing .corky.toml
        #[arg(long)]
        force: bool,
    },

    /// Sync email threads to Markdown
    Sync {
        #[command(subcommand)]
        command: Option<SyncCommands>,
    },

    /// Gmail OAuth setup
    SyncAuth,

    /// List IMAP folders for an account
    ListFolders {
        /// Account name from .corky.toml
        account: Option<String>,
    },

    /// Push a draft markdown file as an email draft
    #[command(hide = true)]
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

        /// Account name in .corky.toml
        #[arg(long)]
        account: String,
    },

    /// Contact commands
    #[command(subcommand)]
    Contact(ContactCommands),

    /// Add a new contact (hidden backward-compatible alias)
    #[command(hide = true)]
    ContactAdd {
        /// Contact name
        name: String,

        /// Email address(es)
        #[arg(long = "email", required = true)]
        emails: Vec<String>,

        /// Conversation label(s) (ignored, kept for backward compat)
        #[arg(long = "label")]
        labels: Vec<String>,

        /// Bind contact labels to a specific account (ignored, kept for backward compat)
        #[arg(long, default_value = "")]
        account: String,
    },

    /// IMAP polling daemon
    Watch {
        /// Poll interval in seconds
        #[arg(long)]
        interval: Option<u64>,
    },

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

    /// Find threads awaiting a reply
    #[command(alias = "find-unanswered")]
    Unanswered {
        /// Scope: "." for root only, mailbox name, or omit for all
        scope: Option<String>,

        /// Name to match as 'your' messages
        #[arg(long = "from")]
        from_name: Option<String>,
    },

    /// Validate draft markdown files
    #[command(hide = true)]
    ValidateDraft {
        /// Draft markdown file(s) to validate
        #[arg(required = true)]
        files: Vec<PathBuf>,
    },

    /// Draft commands
    #[command(subcommand)]
    Draft(DraftCommands),

    /// Mailbox commands
    #[command(subcommand, alias = "mb")]
    Mailbox(MailboxCommands),

    /// Slack commands
    #[command(subcommand)]
    Slack(SlackCommands),

    /// LinkedIn posting commands
    #[command(subcommand)]
    Linkedin(LinkedinCommands),

    /// Scheduled publishing commands
    #[command(subcommand)]
    Schedule(ScheduleCommands),

    /// Topic management commands
    #[command(subcommand)]
    Topics(TopicCommands),

    /// Label management commands
    #[command(subcommand)]
    Label(LabelCommands),

    /// Gmail filter management commands
    #[command(subcommand)]
    Filter(FilterCommands),

    /// Transcribe an audio file to text (requires --features transcribe)
    Transcribe {
        /// Path to audio file (WAV, MP3, FLAC, OGG, AMR, etc.)
        file: PathBuf,

        /// Whisper model name (default: from config or "large-v3-turbo")
        #[arg(long)]
        model: Option<String>,

        /// Language code (e.g. "en"). Omit for auto-detect.
        #[arg(long)]
        language: Option<String>,

        /// Output file (default: print to stdout)
        #[arg(long, short)]
        output: Option<String>,

        /// Comma-separated speaker names for speaker turn labeling (e.g. "Brian,Alice")
        #[arg(long, value_delimiter = ',')]
        speakers: Vec<String>,

        /// Use pyannote-rs for speaker diarization (requires --features diarize)
        #[arg(long)]
        diarize: bool,
    },

    /// Check for updates and upgrade to the latest version.
    Upgrade,
}

#[derive(Subcommand)]
pub enum ContactCommands {
    /// Add a new contact
    Add {
        /// Contact name (optional with --from)
        name: Option<String>,

        /// Email address(es) — conflicts with --from
        #[arg(long = "email")]
        emails: Vec<String>,

        /// Create from a conversation slug
        #[arg(long, conflicts_with = "emails")]
        from: Option<String>,
    },

    /// Show contact info
    Info {
        /// Contact name
        name: String,
    },

    /// Sync CLAUDE.md files between root contacts/ and mailbox contacts/
    Sync,
}

#[derive(Subcommand)]
pub enum SyncCommands {
    /// Full IMAP resync (ignore saved state)
    Full,

    /// Sync one account
    Account {
        /// Account name from .corky.toml
        name: String,
    },

    /// Apply routing rules to existing conversations
    Routes,

    /// Push/pull shared mailbox repos
    Mailbox {
        /// Mailbox name (default: all)
        name: Option<String>,
    },

    /// Import Telegram Desktop JSON export
    TelegramImport {
        /// Path to result.json or directory of exports
        path: PathBuf,
        /// Label for imported conversations
        #[arg(long, default_value = "telegram")]
        label: String,
        /// Account name for imported conversations
        #[arg(long, default_value = "telegram")]
        account: String,
    },
}

#[derive(Subcommand)]
pub enum DraftCommands {
    /// Scaffold a new draft file
    New {
        /// Subject line
        subject: String,

        /// Recipient email address
        #[arg(long)]
        to: String,

        /// CC email address
        #[arg(long)]
        cc: Option<String>,

        /// Sending account name from .corky.toml
        #[arg(long)]
        account: Option<String>,

        /// Sending email address (resolves account)
        #[arg(long)]
        from: Option<String>,

        /// Message ID to reply to
        #[arg(long)]
        in_reply_to: Option<String>,

        /// Create in a mailbox's drafts/ instead of root
        #[arg(long)]
        mailbox: Option<String>,

        /// Attach a file (can be repeated)
        #[arg(long = "attach")]
        attachments: Vec<String>,
    },
    /// Validate draft markdown files
    Validate {
        /// Files to validate, or scope: "." for root, mailbox name, omit for all
        args: Vec<String>,
    },
    /// Push a draft as an email draft or send it
    Push {
        /// Path to the draft markdown file
        file: PathBuf,

        /// Send the email immediately instead of saving as a draft
        #[arg(long)]
        send: bool,
    },
    /// Migrate legacy drafts to YAML frontmatter
    Migrate {
        /// Show what would change without writing
        #[arg(long)]
        dry_run: bool,
    },
}

#[derive(Subcommand)]
pub enum MailboxCommands {
    /// Add a new mailbox
    Add {
        /// Mailbox name
        name: String,

        /// Label(s) to route to this mailbox
        #[arg(long = "label", required = true)]
        labels: Vec<String>,

        /// Display name for the mailbox
        #[arg(long, default_value = "")]
        display_name: String,

        /// Create as a shared GitHub repo (submodule)
        #[arg(long)]
        github: bool,

        /// GitHub username for shared repo collaborator
        #[arg(long, default_value = "")]
        github_user: String,

        /// Use PAT-based access instead of GitHub collaborator invite
        #[arg(long)]
        pat: bool,

        /// Create the shared repo as public
        #[arg(long)]
        public: bool,

        /// Bind mailbox labels to a specific account name
        #[arg(long, default_value = "")]
        account: String,

        /// GitHub org/user for the shared repo
        #[arg(long, default_value = "")]
        org: String,
    },

    /// Push/pull shared mailboxes
    Sync {
        /// Mailbox name (default: all)
        name: Option<String>,
    },

    /// Check for pending changes
    Status,

    /// Remove a mailbox
    Remove {
        /// Mailbox name to remove
        name: String,

        /// Also delete the GitHub repo (if shared)
        #[arg(long)]
        delete_repo: bool,
    },

    /// Rename a mailbox
    Rename {
        /// Current mailbox name
        old_name: String,

        /// New mailbox name
        new_name: String,

        /// Also rename the GitHub repo (if shared)
        #[arg(long)]
        rename_repo: bool,
    },

    /// List registered mailboxes
    List,

    /// Find threads awaiting a reply
    Unanswered {
        /// Scope: "." for root only, mailbox name, or omit for all
        scope: Option<String>,

        /// Name to match as 'your' messages
        #[arg(long = "from")]
        from_name: Option<String>,
    },

    /// Draft commands
    #[command(subcommand)]
    Draft(DraftCommands),

    /// Pull, regenerate templates, commit & push
    Reset {
        /// Mailbox name (default: all)
        name: Option<String>,

        /// Regenerate files without pulling/pushing
        #[arg(long)]
        no_sync: bool,
    },
}

#[derive(Subcommand)]
pub enum LinkedinCommands {
    /// Authenticate with LinkedIn (OAuth)
    Auth {
        /// Profile name in profiles.toml to update with URN
        #[arg(long)]
        profile: Option<String>,
    },

    /// Create a new LinkedIn draft
    Draft {
        /// Post body text
        body: Option<String>,

        /// Author profile name
        #[arg(long)]
        author: Option<String>,

        /// Post visibility (public, connections)
        #[arg(long, default_value = "public")]
        visibility: String,

        /// Comma-separated tags
        #[arg(long, value_delimiter = ',')]
        tags: Vec<String>,
    },

    /// Publish a ready LinkedIn draft
    Publish {
        /// Path to the draft file
        file: PathBuf,
        /// Validate and show payload without actually publishing
        #[arg(long)]
        dry_run: bool,
    },

    /// Validate profiles.toml
    Check,

    /// List LinkedIn drafts
    List {
        /// Filter by status: draft, ready, published
        #[arg(long)]
        status: Option<String>,
    },

    /// Rename an author across drafts and profiles
    RenameAuthor {
        /// Old author name
        old: String,

        /// New author name
        new: String,
    },
}

#[derive(Subcommand)]
pub enum ScheduleCommands {
    /// Process due scheduled items (publish/send)
    Run {
        /// Show what would be published without doing it
        #[arg(long)]
        dry_run: bool,
    },

    /// List all pending scheduled items
    List,
}

#[derive(Subcommand)]
pub enum TopicCommands {
    /// List configured topics
    List {
        /// Show detailed info for each topic
        #[arg(long, short)]
        verbose: bool,
    },

    /// Add a new topic to .corky.toml
    Add {
        /// Topic name
        name: String,

        /// Keywords for matching conversations
        #[arg(long = "keyword", value_delimiter = ',')]
        keywords: Vec<String>,

        /// Topic description
        #[arg(long)]
        description: Option<String>,
    },

    /// Show topic details and matching conversations
    Info {
        /// Topic name
        name: String,
    },

    /// Auto-discover topic candidates from conversations
    Suggest {
        /// Maximum number of suggestions
        #[arg(long, default_value = "10")]
        limit: usize,

        /// Restrict to a specific mailbox
        #[arg(long)]
        mailbox: Option<String>,
    },
}

#[derive(Subcommand)]
pub enum SlackCommands {
    /// Import Slack workspace export ZIP
    Import {
        /// Path to export ZIP file
        path: PathBuf,
        /// Label for imported conversations
        #[arg(long, default_value = "slack")]
        label: String,
        /// Account name for imported conversations
        #[arg(long, default_value = "slack")]
        account: String,
    },
}

#[derive(Subcommand)]
pub enum FilterCommands {
    /// Build mailFilters.xml from filters.toml
    Build {
        /// Input TOML file (default: filters.toml in data dir)
        #[arg(long)]
        input: Option<String>,

        /// Output XML file (default: mailFilters.xml next to input)
        #[arg(long)]
        output: Option<String>,
    },

    /// Authenticate with Gmail for filter management
    Auth {
        /// Account name (token storage key, default: "default")
        #[arg(long)]
        account: Option<String>,
    },

    /// Pull current Gmail filters (read-only)
    Pull {
        /// Account name (must match the one used for auth)
        #[arg(long)]
        account: Option<String>,
    },

    /// Push local filters to Gmail (replaces all existing filters)
    Push {
        /// Account name (must match the one used for auth)
        #[arg(long)]
        account: Option<String>,

        /// Show what would be done without making changes
        #[arg(long)]
        dry_run: bool,
    },
}

#[derive(Subcommand)]
pub enum LabelCommands {
    /// Remove a label from all messages (or those matching a search query)
    Clear {
        /// Label/folder name to clear
        label: String,

        /// Account name from .corky.toml (default: all accounts)
        #[arg(long)]
        account: Option<String>,

        /// IMAP search query to filter messages (default: ALL)
        #[arg(long)]
        search: Option<String>,

        /// Show what would be done without making changes
        #[arg(long)]
        dry_run: bool,
    },
}
