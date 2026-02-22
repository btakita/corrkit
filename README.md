# Correspondence Kit

> **Alpha software.** Expect breaking changes between minor versions. See [VERSIONS.md](VERSIONS.md) for migration notes.

Consolidate conversations from multiple email accounts into a single flat directory of Markdown files. Draft replies with AI assistance. Push routing intelligence to Cloudflare.

Corky syncs threads from any IMAP provider (Gmail, Protonmail Bridge, self-hosted) into `correspondence/conversations/` — one file per thread, regardless of source. A thread that arrives via both Gmail and Protonmail merges into one file. Labels, accounts, and contacts are metadata, not directory structure. Slack and social media sources are planned.

## Tech Stack

- **Language**: Rust (2021 edition)
- **Build**: `cargo build`, `cargo test`, `cargo clippy`
- **CLI**: `clap` (derive macros)
- **Serialization**: `serde` + `toml` / `toml_edit` (format-preserving) / `serde_json`
- **IMAP**: `imap` + `native-tls`
- **Email parsing**: `mailparse`
- **SMTP**: `lettre`
- **Dates**: `chrono`
- **Storage**: Markdown files (one flat directory, one file per conversation thread)
- **Sources**: Any IMAP provider (Gmail, Protonmail Bridge, generic IMAP); Slack and social media planned

## Install

**Quick install (Linux & macOS):**
```sh
curl -sSf https://raw.githubusercontent.com/btakita/corky/main/install.sh | sh
```

This downloads a prebuilt binary to `~/.local/bin/corky`. Use `--system` to install
to `/usr/local/bin` instead (requires sudo).

**Via pip/uvx (wrapper):**
```sh
pip install corky    # installs a thin wrapper that calls the Rust binary
uvx corky --help     # one-shot execution
```

The pip package is a thin wrapper — it requires the Rust binary to be installed separately.

**From source:**
```sh
cargo install --path .
```

**Initialize:**
```sh
corky init --user you@gmail.com
```

This creates `~/Documents/correspondence` with directory structure, `.corky.toml`,
and empty config files inside it. Edit `correspondence/.corky.toml` with credentials, then run `corky sync`.

**Developer setup (from repo checkout):**
```sh
cp .corky.toml.example correspondence/.corky.toml   # configure your email accounts
cargo build
```

### Account configuration

Define email accounts in `correspondence/.corky.toml` with provider presets:

```toml
[accounts.personal]
provider = "gmail"                      # gmail | protonmail-bridge | imap
user = "you@gmail.com"
password_cmd = "pass email/personal"    # or: password = "inline-secret"
labels = ["correspondence"]
default = true

[accounts.proton]
provider = "protonmail-bridge"
user = "you@proton.me"
password_cmd = "pass email/proton"
labels = ["private"]

[accounts.selfhosted]
provider = "imap"
imap_host = "mail.example.com"
smtp_host = "mail.example.com"
user = "user@example.com"
password_cmd = "pass email/selfhosted"
labels = ["important"]
```

Provider presets fill in IMAP/SMTP connection defaults:

| Field | `gmail` | `protonmail-bridge` | `imap` (generic) |
|---|---|---|---|
| imap_host | imap.gmail.com | 127.0.0.1 | (required) |
| imap_port | 993 | 1143 | 993 |
| imap_starttls | false | true | false |
| smtp_host | smtp.gmail.com | 127.0.0.1 | (required) |
| smtp_port | 465 | 1025 | 465 |
| drafts_folder | [Gmail]/Drafts | Drafts | Drafts |

Any preset value can be overridden per-account. Credential resolution: `password` (inline)
or `password_cmd` (shell command, e.g. `pass email/personal`).

**Backward compat**: If no `.corky.toml` exists, falls back to `.env` GMAIL_* vars.

### Legacy `.env` configuration

| Variable                     | Required | Description                                          |
| ---------------------------- | -------- | ---------------------------------------------------- |
| `GMAIL_USER_EMAIL`           | yes      | Your Gmail address                                   |
| `GMAIL_APP_PASSWORD`         | yes      | [App password](https://myaccount.google.com/apppasswords) |
| `GMAIL_SYNC_LABELS`         | yes      | Comma-separated Gmail labels to sync                 |
| `GMAIL_SYNC_DAYS`           | no       | How far back to sync (default: 3650)                 |
| `CLOUDFLARE_ACCOUNT_ID`     | no       | For routing intelligence push                        |
| `CLOUDFLARE_API_TOKEN`      | no       | For routing intelligence push                        |
| `CLOUDFLARE_D1_DATABASE_ID` | no       | For routing intelligence push                        |

## Usage

All commands are available through the `corky` CLI:

```sh
corky --help                    # Show all commands
corky init --user EMAIL        # Initialize in current directory
corky init --user EMAIL /path # Initialize at specific path
corky install-skill email     # Install the email agent skill
corky sync                     # Incremental IMAP sync (all accounts)
corky sync full                # Full re-sync (ignore saved state)
corky sync account personal    # Sync one account
corky sync routes              # Apply routing rules to existing conversations
corky sync mailbox [NAME]      # Push/pull shared mailboxes
corky list-folders [ACCOUNT]   # List IMAP folders for an account
corky push-draft correspondence/drafts/FILE.md # Save a draft via IMAP
corky push-draft correspondence/drafts/FILE.md --send  # Send via SMTP
corky add-label LABEL --account NAME   # Add a label to an account's sync config
corky contact-add NAME --email EMAIL    # Add a contact with context docs
corky mailbox add NAME --label LABEL        # Add a mailbox
corky mailbox sync [NAME]                   # Push/pull shared mailboxes
corky mailbox status                        # Check mailbox status
corky mailbox remove NAME                   # Remove a mailbox
corky mailbox rename OLD NEW                # Rename a mailbox
corky mailbox reset [NAME]                  # Regenerate mailbox templates
corky migrate                               # Migrate old config to .corky.toml
corky find-unanswered                   # Find threads awaiting a reply
corky validate-draft FILE               # Validate draft markdown files
corky watch                             # Poll IMAP and sync on an interval
corky watch --interval 60               # Override poll interval (seconds)
corky mailbox list                     # List registered mailboxes
corky --mailbox work sync              # Sync a specific mailbox
corky audit-docs                        # Audit instruction files for staleness
corky help                              # Show command reference
```

Windows users can download `.zip` from [GitHub Releases](https://github.com/btakita/corky/releases)
or build from source with `cargo install --path .`.

### Multiple mailboxes

Manage multiple correspondence directories (personal, work, etc.) with named mailboxes:

```sh
# Init registers a mailbox automatically
corky init --user you@gmail.com                                   # init in cwd
corky init --user work@company.com ~/work/project --mailbox-name work  # init at path

# List registered mailboxes
corky mailbox list

# Use a specific mailbox for any command
corky --mailbox work sync
corky --mailbox personal mailbox status
```

Mailboxes are stored in `~/.config/corky/config.toml` (Linux), `~/Library/Application Support/corky/config.toml` (macOS), or `%APPDATA%/corky/config.toml` (Windows). The first mailbox added becomes the default. With one mailbox configured, `--mailbox` is optional.

Synced threads are written to `correspondence/conversations/[slug].md` (flat, one file per thread). Labels and accounts are metadata inside each file. A `manifest.toml` index is generated after each sync.

## Development

```sh
make build                        # Debug build
make release                      # Release build + symlink to .bin/corky
make test                         # Run tests
make clippy                       # Lint
make check                        # Lint + test
make install                      # Install to ~/.cargo/bin
make init-python                  # Set up Python venv for wrapper development
```

### .gitignore

```
.env
accounts.toml
credentials.json
*.credentials.json
CLAUDE.local.md
AGENTS.local.md
correspondence
.idea/
tmp/
target/
.bin/
.agents/
.junie/
.kilocode/
skills/
skills-lock.json
```

Config files (`.corky.toml`, `contacts.toml`, `voice.md`) live inside `correspondence/`
which is already gitignored. `credentials.json` is also gitignored in `correspondence/.gitignore`.

## Unified conversation directory

All synced threads live in one flat directory:

```
correspondence/
  conversations/          # one file per thread, all sources merged
    project-update.md     # immutable slug filename
    lunch-plans.md        # mtime = last message date (ls -t sorts by activity)
    quarterly-review.md
  contacts/               # per-contact context for drafting
    alex/
      AGENTS.md           # relationship, tone, topics, notes
      CLAUDE.md -> AGENTS.md
  drafts/                 # outgoing messages
  manifest.toml           # thread index (generated by sync)
```

**No subdirectories for accounts or labels.** A conversation with the same person may arrive via
Gmail, Protonmail, or both — it merges into one file. Source metadata is tracked inside each file
(`**Labels**`, `**Accounts**`) and in `manifest.toml`.

**Immutable filenames.** Each thread gets a `[slug].md` name derived from the subject on first write.
The filename never changes, even as new messages arrive. Thread identity is tracked by `**Thread ID**`
metadata inside the file.

**manifest.toml** indexes every thread by subject, labels, accounts, contacts, and last-updated date.
Agents read the manifest for discovery, then go straight to the file for content.

**Extensible to new sources.** The flat model means adding Slack or social media sync doesn't change
the directory layout — new messages merge into the same directory with their source tracked in metadata.

### Conversation markdown format

```markdown
# [Subject]

**Labels**: [label1, label2]
**Accounts**: [account1, account2]
**Thread ID**: [thread key]
**Last updated**: [RFC 2822 date]

---

## [Sender Name] — [Date]

[Body text]

---

## [Reply sender] — [Date]

[Body text]
```

### Draft format

Drafts live in `correspondence/drafts/` (private) or `correspondence/mailboxes/{name}/drafts/` (collaborator).
Filename convention: `[YYYY-MM-DD]-[slug].md`.

```markdown
# [Subject]

**To**: [recipient]
**CC**: (optional)
**Status**: draft
**Author**: brian
**Account**: (optional — account name from .corky.toml, e.g. "personal")
**From**: (optional — email address, used to resolve account if Account not set)
**In-Reply-To**: (optional — message ID)

---

[Draft body]
```

Status values: `draft` -> `review` -> `approved` -> `sent`

## Sandboxing

Most AI email tools (OpenClaw, etc.) require OAuth access to your entire account. Once authorized, the agent can read every message, every contact, every thread — and you're trusting the service not to overreach.

Correspondence-kit inverts this. You control what any agent or collaborator can see:

1. **You label threads in your email client.** Only threads you explicitly label get synced locally.
2. **Labels route to scoped views.** Each mailbox gives the collaborator/agent a directory containing only the threads labeled for them — nothing else.
3. **Credentials never leave your machine.** Config lives inside `correspondence/` (your private data repo). Agents draft replies in markdown; only you can push to your email.

An agent added with `corky mailbox add assistant --label for-assistant` can only see threads you've tagged `for-assistant`. It can't see your other conversations, your contacts, or other collaborators' repos. If the agent is compromised, the blast radius is limited to the threads you chose to share.

This works across multiple email accounts — Gmail, Protonmail, self-hosted — each with its own labels and routing rules, all funneling through the same scoped mailbox model.

## Contacts

Per-contact directories give Claude context when drafting emails — relationship history, tone preferences, recurring topics.

### Adding a contact

```sh
corky contact-add alex --email alex@example.com --email alex@work.com --label correspondence --account personal
```

This creates `correspondence/contacts/alex/` with an AGENTS.md template (+ CLAUDE.md symlink) and updates `contacts.toml`.

### Contact context

Edit `correspondence/contacts/{name}/AGENTS.md` with:
- **Relationship**: How you know this person, shared history
- **Tone**: Communication style overrides (defaults to voice.md)
- **Topics**: Recurring subjects, current projects
- **Notes**: Freeform context — preferences, pending items, important dates

### contacts.toml

Maps contacts to email addresses and conversation labels (for lookup, not sync routing):

```toml
[alex]
emails = ["alex@example.com", "alex@work.com"]
labels = ["correspondence"]
account = "personal"
```

Copy `contacts.toml.example` to `contacts.toml` to get started.

## Mailboxes

Share specific email threads with people or AI agents via scoped directories or GitHub repos.

### Adding a mailbox

```sh
# Plain directory (default)
corky mailbox add alex --label for-alex --name "Alex"

# With GitHub submodule
corky mailbox add alex --label for-alex --name "Alex" --github

# AI agent (uses a PAT instead of GitHub invite)
corky mailbox add assistant-bot --label for-assistant --pat

# Bind all labels to one account
corky mailbox add alex --label for-alex --account personal

# Per-label account scoping (proton-dev account, INBOX folder)
# Use account:label syntax in .corky.toml directly
```

This creates a scoped directory under `mailboxes/{name}/`. With `--github`, it also creates a private GitHub repo (`{owner}/to-{name}`) and adds it as a submodule.

### Daily workflow

```sh
# 1. Sync emails -- shared labels route to mailboxes/{name}/conversations/
corky sync

# 2. Push synced threads to mailbox repos & pull their drafts
corky mailbox sync

# 3. Check what's pending without pushing
corky mailbox status

# 4. Review a collaborator's draft and push it as an email draft
corky push-draft mailboxes/alex/drafts/2026-02-19-reply.md
```

### Unattended sync with `corky watch`

Run as a daemon to poll IMAP, sync threads, and push to shared repos automatically:

```sh
# Interactive — polls every 5 minutes (default), Ctrl-C to stop
corky watch

# Custom interval
corky watch --interval 60
```

Configure in `correspondence/.corky.toml`:

```toml
[watch]
poll_interval = 300    # seconds between polls (default: 300)
notify = true          # desktop alerts on new messages (default: false)
```

#### Running as a system service

**Linux (systemd):**
```sh
cp services/corky-watch.service ~/.config/systemd/user/
# Edit WorkingDirectory in the unit file to match your setup
systemctl --user enable --now corky-watch
journalctl --user -u corky-watch -f   # view logs
```

**macOS (launchd):**
```sh
cp services/com.corky.watch.plist ~/Library/LaunchAgents/
# Edit WorkingDirectory in the plist to match your setup
launchctl load ~/Library/LaunchAgents/com.corky.watch.plist
tail -f /tmp/corky-watch.log          # view logs
```

### What collaborators can do

- Read conversations labeled for them
- Draft replies in `mailboxes/{name}/drafts/` following the format in AGENTS.md
- Run `corky find-unanswered` and `corky validate-draft` in their repo
- Push changes to their shared repo

### What only you can do

- Sync new emails (`corky sync`)
- Push synced threads to mailbox repos (`corky mailbox sync`)
- Send emails (`corky push-draft --send`)
- Change draft Status to `sent`

### Removing a mailbox

```sh
corky mailbox remove alex
corky mailbox remove alex --delete-repo  # also delete the GitHub repo
```

## Designed for humans and agents

Corky is built around files, CLI commands, and git — interfaces that work equally well for humans
and AI agents. No GUIs, no OAuth popups, no interactive prompts.

### Why this works

- **Everything is files.** Threads are Markdown. Config is TOML. Drafts are Markdown. Humans read
  them in any editor; agents read and write them natively.
- **CLI is the interface.** Every operation is a single `corky` command. Scriptable, composable,
  works the same whether a human or agent is at the keyboard.
- **Single-binary for collaborators.** One `curl | sh` install gives collaborators
  `corky find-unanswered` and `corky validate-draft` — no dev environment needed.
- **Self-documenting repos.** Each shared repo ships with `AGENTS.md` (full instructions),
  `CLAUDE.md` (symlink for Claude Code), `voice.md`, and a `README.md`. A new collaborator —
  human or agent — can start contributing immediately.
- **Templates stay current.** `corky mailbox reset` regenerates all template files in shared repos
  when the tool evolves. No manual sync of instructions across collaborators.

### Owner workflow

The owner can work directly or with an AI agent (Claude Code, Codex, etc.) that has full context of
both the codebase and the correspondence. In a single session:

1. Develop the tool — write code, run tests, commit
2. Sync emails — `corky sync`
3. Manage collaborators — add, reset templates, push synced threads
4. Draft replies — reading threads for context, writing drafts matching the voice guidelines
5. Review collaborator drafts — validate, approve, push to email

Humans and agents use the same commands. There's no separate "agent mode" — the CLI is the
universal interface.

### Collaborator workflow

Each collaborator — human or agent — gets a scoped directory with:

```
mailboxes/{name}/
  AGENTS.md          # Full instructions: formats, commands, status flow
  CLAUDE.md          # Symlink for Claude Code auto-discovery
  README.md          # Quick-start guide
  voice.md           # Writing style guidelines
  contacts/          # Per-contact context for drafting
  conversations/     # Synced threads (read-only for the collaborator)
  drafts/            # Where the collaborator writes replies
```

The collaborator reads conversations, drafts replies following the documented format, validates with
`corky validate-draft`, and pushes. The owner reviews and sends.

## Cloudflare architecture

Corky handles the heavy lifting locally. Distilled intelligence is pushed to Cloudflare storage
for use by a lightweight TypeScript Worker that handles email routing.

```
Gmail/Protonmail
      ↓
corky (local)
  - sync threads → markdown
  - extract intelligence (tags, contact metadata, routing rules)
  - push to Cloudflare
      ↓
Cloudflare D1 / KV
  - contact importance scores
  - thread tags / inferred topics
  - routing rules
      ↓
Cloudflare Worker (TypeScript)
  - email routing decisions using intelligence from corky
```

Full conversation threads stay local. Cloudflare only receives the minimal distilled signal
needed for routing.

## MCP alternative

Instead of pre-syncing to markdown files, Claude can access Gmail live via an MCP server during
a session. Options:

- **Pipedream** — hosted MCP with Gmail, Calendar, Contacts (note: data passes through Pipedream)
- **Local MCP server** — run a Gmail MCP server locally for fully private live access (future)

Current approach (file sync) is preferred for privacy and offline use. MCP is worth revisiting
for real-time workflows.

## Future work

- **Slack sync**: Pull conversations from Slack channels/DMs into the flat conversations/ directory
- **Social media sync**: Pull DMs and threads from social platforms into conversations/
- **Cloudflare routing**: TypeScript Worker consuming D1/KV data pushed from corky
- **Local MCP server**: Live email access during Claude sessions without Pipedream
- **Multi-user**: Per-user credential flow when shared with another developer

## AI agent instructions

Project instructions live in `AGENTS.md` (symlinked as `CLAUDE.md`). Personal overrides go in `CLAUDE.local.md` / `AGENTS.local.md` (gitignored).
