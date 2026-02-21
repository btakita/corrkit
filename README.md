# Correspondence Kit

> **Alpha software.** Expect breaking changes between minor versions. See [VERSIONS.md](VERSIONS.md) for migration notes.

Consolidate conversations from multiple email accounts into a single flat directory of Markdown files. Draft replies with AI assistance. Push routing intelligence to Cloudflare.

Corrkit syncs threads from any IMAP provider (Gmail, Protonmail Bridge, self-hosted) into `correspondence/conversations/` — one file per thread, regardless of source. A thread that arrives via both Gmail and Protonmail merges into one file. Labels, accounts, and contacts are metadata, not directory structure. Slack and social media sources are planned.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

**Quick start (general user):**
```sh
uvx corrkit init --user you@gmail.com
```

This creates `~/Documents/correspondence` with directory structure, `accounts.toml`,
and empty config files. Edit `accounts.toml` with credentials, then run `corrkit sync`.

**Developer setup (from repo checkout):**
```sh
cp accounts.toml.example accounts.toml   # configure your email accounts
uv sync
```

### Account configuration

Define email accounts in `accounts.toml` with provider presets:

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

**Backward compat**: If no `accounts.toml` exists, falls back to `.env` GMAIL_* vars.

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

All commands are available through the `corrkit` CLI:

```sh
corrkit --help                    # Show all commands
corrkit init --user EMAIL        # Initialize a new data directory
corrkit sync                     # Sync all accounts
corrkit sync --account personal  # Sync one account
corrkit sync --full              # Full re-sync (ignore saved state)
corrkit sync-gmail               # Alias for sync (backward compat)
corrkit list-folders [ACCOUNT]   # List IMAP folders for an account
corrkit push-draft correspondence/drafts/FILE.md # Save a draft via IMAP
corrkit push-draft correspondence/drafts/FILE.md --send  # Send via SMTP
corrkit add-label LABEL --account NAME   # Add a label to an account's sync config
corrkit contact-add NAME --email EMAIL    # Add a contact with context docs
corrkit for add NAME --label LABEL        # Add a collaborator
corrkit for sync [NAME]                   # Push/pull shared submodules
corrkit for status                        # Check for pending changes
corrkit for remove NAME                   # Remove a collaborator
corrkit for rename OLD NEW                # Rename a collaborator directory
corrkit for reset [NAME]                  # Pull, regenerate templates, commit & push
corrkit by find-unanswered                # Find threads awaiting a reply
corrkit by validate-draft FILE            # Validate draft markdown files
corrkit watch                             # Poll IMAP and sync on an interval
corrkit watch --interval 60               # Override poll interval (seconds)
corrkit spaces                            # List configured spaces
corrkit --space work sync                 # Sync a specific space
corrkit audit-docs                        # Audit instruction files for staleness
corrkit help                              # Show command reference
```

Run with `uv run corrkit <subcommand>` if the package isn't installed globally.

### Spaces

Manage multiple correspondence directories (personal, work, etc.) with named spaces:

```sh
# Init creates a space automatically
corrkit init --user you@gmail.com                              # registers "default" space
corrkit init --user work@company.com --data-dir ~/work/correspondence --space work

# List configured spaces
corrkit spaces

# Use a specific space for any command
corrkit --space work sync
corrkit --space personal for status
```

Spaces are stored in `~/.config/corrkit/config.toml` (Linux), `~/Library/Application Support/corrkit/config.toml` (macOS), or `%APPDATA%/corrkit/config.toml` (Windows). The first space added becomes the default. With one space configured, `--space` is optional.

Synced threads are written to `correspondence/conversations/[slug].md` (flat, one file per thread). Labels and accounts are metadata inside each file. A `manifest.toml` index is generated after each sync.

## Development

```sh
uv run pytest             # Run tests
uv run ruff check .       # Lint
uv run ruff format .      # Format
uv run ty check           # Type check
uv run poe precommit      # Run ty + ruff + tests
```

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

## Sandboxing

Most AI email tools (OpenClaw, etc.) require OAuth access to your entire account. Once authorized, the agent can read every message, every contact, every thread — and you're trusting the service not to overreach.

Correspondence-kit inverts this. You control what any agent or collaborator can see:

1. **You label threads in your email client.** Only threads you explicitly label get synced locally.
2. **Labels route to scoped views.** Each collaborator/agent gets a submodule containing only the threads labeled for them — nothing else.
3. **Credentials never leave your machine.** `accounts.toml` is gitignored. Agents draft replies in markdown; only you can push to your email.

An agent added with `corrkit for add assistant --label for-assistant` can only see threads you've tagged `for-assistant`. It can't see your other conversations, your contacts, or other collaborators' repos. If the agent is compromised, the blast radius is limited to the threads you chose to share.

This works across multiple email accounts — Gmail, Protonmail, self-hosted — each with its own labels and routing rules, all funneling through the same scoped collaborator model.

## Contacts

Per-contact directories give Claude context when drafting emails — relationship history, tone preferences, recurring topics.

### Adding a contact

```sh
corrkit contact-add alex --email alex@example.com --email alex@work.com --label correspondence --account personal
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

## Collaborators

Share specific email threads with people or AI agents via scoped GitHub repos.

### Adding a collaborator

```sh
# Human collaborator (invited via GitHub)
corrkit for add alex-gh --label for-alex --name "Alex"

# AI agent (uses a PAT instead of GitHub invite)
corrkit for add assistant-bot --label for-assistant --pat

# Bind all labels to one account
corrkit for add alex-gh --label for-alex --account personal

# Per-label account scoping (proton-dev account, INBOX folder)
# Use account:label syntax in collaborators.toml directly
```

This creates a private GitHub repo (`{owner}/to-{gh-user}`), initializes it with instructions, and adds it as a submodule under `for/{gh-user}/`. Collaborators use `uvx corrkit by ...` for helper commands.

### Daily workflow

```sh
# 1. Sync emails -- shared labels route to for/{gh-user}/conversations/
corrkit sync

# 2. Push synced threads to collaborator repos & pull their drafts
corrkit for sync

# 3. Check what's pending without pushing
corrkit for status

# 4. Review a collaborator's draft and push it as an email draft
corrkit push-draft for/alex-gh/drafts/2026-02-19-reply.md
```

### Unattended sync with `corrkit watch`

Run as a daemon to poll IMAP, sync threads, and push to shared repos automatically:

```sh
# Interactive — polls every 5 minutes (default), Ctrl-C to stop
corrkit watch

# Custom interval
corrkit watch --interval 60
```

Configure in `accounts.toml`:

```toml
[watch]
poll_interval = 300    # seconds between polls (default: 300)
notify = true          # desktop alerts on new messages (default: false)
```

#### Running as a system service

**Linux (systemd):**
```sh
cp services/corrkit-watch.service ~/.config/systemd/user/
# Edit WorkingDirectory in the unit file to match your setup
systemctl --user enable --now corrkit-watch
journalctl --user -u corrkit-watch -f   # view logs
```

**macOS (launchd):**
```sh
cp services/com.corrkit.watch.plist ~/Library/LaunchAgents/
# Edit WorkingDirectory in the plist to match your setup
launchctl load ~/Library/LaunchAgents/com.corrkit.watch.plist
tail -f /tmp/corrkit-watch.log          # view logs
```

### What collaborators can do

- Read conversations labeled for them
- Draft replies in `for/{gh-user}/drafts/` following the format in AGENTS.md
- Run `uvx corrkit by find-unanswered` and `uvx corrkit by validate-draft` in their repo
- Push changes to their shared repo

### What only you can do

- Sync new emails (`corrkit sync`)
- Push synced threads to collaborator repos (`corrkit for sync`)
- Send emails (`corrkit push-draft --send`)
- Change draft Status to `sent`

### Removing a collaborator

```sh
corrkit for remove alex-gh
corrkit for remove alex-gh --delete-repo  # also delete the GitHub repo
```

## Designed for humans and agents

Corrkit is built around files, CLI commands, and git — interfaces that work equally well for humans
and AI agents. No GUIs, no OAuth popups, no interactive prompts.

### Why this works

- **Everything is files.** Threads are Markdown. Config is TOML. Drafts are Markdown. Humans read
  them in any editor; agents read and write them natively.
- **CLI is the interface.** Every operation is a single `corrkit` command. Scriptable, composable,
  works the same whether a human or agent is at the keyboard.
- **Zero-install for collaborators.** `uvx corrkit by find-unanswered` and `uvx corrkit by validate-draft`
  work without cloning the main repo or setting up a dev environment.
- **Self-documenting repos.** Each shared repo ships with `AGENTS.md` (full instructions),
  `CLAUDE.md` (symlink for Claude Code), `voice.md`, and a `README.md`. A new collaborator —
  human or agent — can start contributing immediately.
- **Templates stay current.** `corrkit for reset` regenerates all template files in shared repos
  when the tool evolves. No manual sync of instructions across collaborators.

### Owner workflow

The owner can work directly or with an AI agent (Claude Code, Codex, etc.) that has full context of
both the codebase and the correspondence. In a single session:

1. Develop the tool — write code, run tests, commit
2. Sync emails — `corrkit sync`
3. Manage collaborators — add, reset templates, push synced threads
4. Draft replies — reading threads for context, writing drafts matching the voice guidelines
5. Review collaborator drafts — validate, approve, push to email

Humans and agents use the same commands. There's no separate "agent mode" — the CLI is the
universal interface.

### Collaborator workflow

Each collaborator — human or agent — gets a scoped git repo with:

```
for/{gh-user}/
  AGENTS.md          # Full instructions: formats, commands, status flow
  CLAUDE.md          # Symlink for Claude Code auto-discovery
  README.md          # Quick-start guide
  voice.md           # Writing style guidelines
  conversations/     # Synced threads (read-only for the collaborator)
  drafts/            # Where the collaborator writes replies
```

The collaborator reads conversations, drafts replies following the documented format, validates with
`uvx corrkit validate-draft`, and pushes. The owner reviews and sends.

## Cloudflare architecture

Python handles the heavy lifting locally. Distilled intelligence is pushed to Cloudflare storage
for use by a lightweight TypeScript Worker that handles email routing.

```
Gmail/Protonmail
      ↓
Python (local, uv)
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
  - email routing decisions using intelligence from Python
```

Full conversation threads stay local. Cloudflare only receives the minimal distilled signal
needed for routing.

## MCP alternative

Instead of pre-syncing to markdown files, Claude can access Gmail live via an MCP server during
a session. Options:

- **Pipedream** — hosted MCP with Gmail, Calendar, Contacts (note: data passes through Pipedream)
- **Local Python MCP server** — run a Gmail MCP server locally for fully private live access (future)

Current approach (file sync) is preferred for privacy and offline use. MCP is worth revisiting
for real-time workflows.

## Future work

- **Slack sync**: Pull conversations from Slack channels/DMs into the flat conversations/ directory
- **Social media sync**: Pull DMs and threads from social platforms into conversations/
- **Cloudflare routing**: TypeScript Worker consuming D1/KV data pushed from Python
- **Local MCP server**: Live email access during Claude sessions without Pipedream
- **Multi-user**: Per-user credential flow when shared with another developer

## AI agent instructions

Project instructions live in `AGENTS.md` (symlinked as `CLAUDE.md`). Personal overrides go in `CLAUDE.local.md` / `AGENTS.local.md` (gitignored).
