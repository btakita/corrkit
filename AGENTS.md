# Correspondence Kit

A personal workspace for drafting emails and syncing conversation threads from any IMAP provider (Gmail, Protonmail Bridge, self-hosted).

## Purpose

- Sync email threads from any IMAP provider by label into local Markdown files
- Draft and refine outgoing emails with Claude's assistance
- Maintain a readable, version-controlled record of correspondence
- Push distilled intelligence (tags, routing rules, contact metadata) to Cloudflare for email routing

## Tech Stack

- **Runtime**: Python 3.12+ via `uv`
- **Linter/formatter**: `ruff`
- **Type checker**: `ty`
- **Types/serialization**: `msgspec` (Struct instead of dataclasses)
- **Storage**: Markdown files (one file per conversation thread)
- **Email sources**: Any IMAP provider (Gmail, Protonmail Bridge, generic IMAP)
- **Cloudflare** (routing layer): TypeScript Workers reading from D1/KV populated by Python

## Project Structure

```
correspondence-kit/
  AGENTS.md                      # Project instructions (CLAUDE.md symlinks here)
  pyproject.toml
  voice.md                       # Writing voice guidelines (committed)
  accounts.toml                  # Multi-account IMAP config (gitignored)
  accounts.toml.example          # Template with provider presets (committed)
  collaborators.toml             # Collaborator config (committed)
  .env                          # Legacy credentials fallback (gitignored)
  .gitignore
  .claude/
    skills/
      email/
        SKILL.md                # Email drafting & management skill
        find_unanswered.py      # Find threads needing a reply
  src/
    accounts.py                  # Account config parser (accounts.toml)
    sync/
      __init__.py
      imap.py                   # Multi-account IMAP sync logic
      types.py                  # msgspec Structs (Thread, Message, SyncState, etc.)
      auth.py                   # One-time Gmail OAuth flow
    draft/
      __init__.py
      push.py                   # Push draft to email (draft or send)
    collab/
      __init__.py               # Collaborator config parser (collaborators.toml)
      add.py                    # collab-add command
      sync.py                   # collab-sync / collab-status commands
      remove.py                 # collab-remove command
    cloudflare/
      __init__.py               # Push intelligence to Cloudflare D1/KV (planned)
  correspondence -> ~/work/btakita/correspondence  # Symlink to personal data repo
    conversations/              # Synced threads
      [account]/                # Account-scoped (omitted for _legacy)
        [label]/
          [YYYY-MM-DD]-[subject].md
    drafts/                     # Outgoing email drafts
      [YYYY-MM-DD]-[subject].md
    .sync-state.json            # IMAP sync state
  shared/                       # Collaborator submodules (gitignored, local-only)
    [name]/                     # submodule → btakita/correspondence-shared-[name]
      conversations/[label]/*.md
      drafts/*.md
      AGENTS.md
      voice.md
```

## Writing Voice

See `voice.md` (committed) for tone, style, and formatting guidelines.

## Safety Rules

- **Never send email directly.** Always save as a Gmail draft for review first.
- **Never guess at intent.** If the right response is unclear, ask rather than assume.
- **Never share conversation content** outside this local environment (no third-party APIs) unless explicitly instructed.

## Environment Setup

```sh
cp accounts.toml.example accounts.toml   # configure your email accounts
uv sync
```

### accounts.toml

Define one or more email accounts with provider presets:

```toml
[accounts.personal]
provider = "gmail"                      # gmail | protonmail-bridge | imap
user = "brian@gmail.com"
password_cmd = "pass email/personal"    # or: password = "inline-secret"
labels = ["correspondence"]
default = true

[accounts.proton]
provider = "protonmail-bridge"
user = "brian@proton.me"
password_cmd = "pass email/proton"
labels = ["private"]
```

**Provider presets** fill in connection defaults:

| Field | `gmail` | `protonmail-bridge` | `imap` (generic) |
|---|---|---|---|
| imap_host | imap.gmail.com | 127.0.0.1 | (required) |
| imap_port | 993 | 1143 | 993 |
| imap_starttls | false | true | false |
| smtp_host | smtp.gmail.com | 127.0.0.1 | (required) |
| smtp_port | 465 | 1025 | 465 |
| drafts_folder | [Gmail]/Drafts | Drafts | Drafts |

Any preset value can be overridden per-account.

**Credential resolution**: `password` (inline) or `password_cmd` (runs shell command, e.g. `pass email/personal`). Resolved lazily at connection time.

**Backward compat**: If no `accounts.toml` exists, falls back to `.env` GMAIL_* vars as a synthetic `_legacy` account.

### Gmail OAuth Setup (legacy .env)

If using `.env` instead of `accounts.toml`:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable the **Gmail API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download the credentials JSON and extract `client_id` and `client_secret` into `.env`
5. Run the auth flow once to obtain a refresh token:
   ```sh
   corrkit sync-auth
   ```

## Commands

```sh
uv sync                                         # Install dependencies
corrkit sync                                    # Sync all accounts (incremental)
corrkit sync --full                             # Full re-sync (ignores saved state)
corrkit sync --account personal                 # Sync one account only
corrkit sync-auth                               # One-time Gmail OAuth setup
corrkit sync-gmail                              # Alias for sync (backward compat)
corrkit list-folders [ACCOUNT]                  # List IMAP folders for an account
corrkit push-draft correspondence/drafts/FILE.md               # Save draft via IMAP
corrkit push-draft correspondence/drafts/FILE.md --send        # Send email via SMTP
corrkit collab-add NAME --label LABEL [--github-user USER | --pat] [--public] [--account NAME]
corrkit collab-sync [NAME]                      # Push/pull shared submodules
corrkit collab-status                           # Quick check for pending changes
corrkit collab-remove NAME [--delete-repo]
corrkit audit-docs                              # Audit instruction files for staleness
corrkit help                                    # Show command reference

# Dev tools
uv run pytest                                    # Run tests
uv run ruff check .                             # Lint
uv run ruff format .                            # Format
uv run ty check                                 # Type check
```

## Workflows

### Daily email review

1. Run `corrkit sync` to pull latest threads
2. Ask Claude: *"Review correspondence/conversations/ and identify threads that need a response, ordered by priority"*
3. For each thread, ask Claude to draft a reply matching the voice guidelines above
4. Review and edit the draft in `correspondence/drafts/`
5. When satisfied, ask Claude to save it as a Gmail draft (never send directly)

### Finding unanswered threads

```sh
uv run .claude/skills/email/find_unanswered.py
```

Lists all synced threads where the last message is not from you — i.e. threads awaiting your reply.

### Drafting a new email

Ask Claude: *"Draft an email to [person] about [topic]"* — point it at any relevant thread in `correspondence/conversations/` for context.

## Sync Behavior

- **Multi-account**: Each account in `accounts.toml` is synced independently. Output goes to
  `correspondence/conversations/{account}/{label}/` (or just `{label}/` for legacy single-account setups).
- **Incremental by default**: Tracks IMAP UIDs per-account in `.sync-state.json` (gitignored). Only new messages since
  last sync are fetched. Use `--full` to ignore saved state and re-fetch everything.
- **Streaming writes**: Each message is merged into its thread file immediately after fetch — no batching.
  If sync crashes mid-run, state is not saved; next run re-fetches from last good state.
- **UIDVALIDITY**: If the IMAP server resets UIDVALIDITY for a folder, that label automatically does a full resync.
- **Label routing**: Labels from each account's config go to `correspondence/conversations/{account}/{label}/`.
  Labels listed in `collaborators.toml` are automatically included in the sync and routed to
  `shared/{name}/conversations/{label}/`. Collaborators can be bound to a specific account via `account = "name"`,
  or individual labels can use `account:label` syntax (e.g. `"proton-dev:INBOX"`) for per-label account scoping.
- Threads are written to `[YYYY-MM-DD]-[slug].md`
  - Date is derived from the most recent message in the thread
  - Slug is derived from the subject line
  - Existing thread files are matched by `**Thread ID**` metadata, not filename
- New messages are deduplicated by `(sender, date)` tuple when merging into existing files
- Attachments are noted inline but not downloaded

## Cloudflare Architecture

Python handles the heavy lifting locally. Distilled intelligence is pushed to Cloudflare storage for use by a lightweight TypeScript Worker that handles email routing.

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

Full conversation threads stay local. Cloudflare only receives the minimal distilled signal needed for routing.

## Conversation Markdown Format

Each synced thread is written in this format:

```markdown
# [Subject]

**Label**: [label]
**Thread ID**: [Gmail thread ID]
**Last updated**: [ISO date]

---

## [Sender Name] — [Date]

[Body text]

---

## [Reply sender] — [Date]

[Body text]
```

## Draft Format

Drafts live in `correspondence/drafts/` (private) or `shared/{name}/drafts/` (collaborator). Filename convention: `[YYYY-MM-DD]-[slug].md`.

```markdown
# [Subject]

**To**: [recipient]
**CC**: (optional)
**Status**: draft
**Author**: brian
**Account**: (optional — account name from accounts.toml, e.g. "personal")
**From**: (optional — email address, used to resolve account if Account not set)
**In-Reply-To**: (optional — message ID)

---

[Draft body]
```

Status values: `draft` -> `review` -> `approved` -> `sent`

When asking Claude to help draft or refine an email:
- Point it at the relevant thread in `correspondence/conversations/` for context
- Specify tone if it differs from the voice guidelines (formal, concise, etc.)
- Indicate any constraints (length, what to avoid, etc.)

## Collaborators

Share specific threads with collaborators via per-collaborator GitHub repos linked as submodules.
Collaborators can be people or AI agents -- anything that can read markdown and push to a git repo.

### Config: `collaborators.toml`

```toml
[alex]
labels = ["for-alex"]
repo = "btakita/correspondence-shared-alex"
github_user = "alex-github-username"
account = "personal"                    # optional — bind ALL plain labels to one account

[bot]
labels = ["for-bot", "proton-dev:INBOX"]   # account:label scopes to one account
repo = "btakita/correspondence-shared-bot"
```

**Label scoping**: Labels support `account:label` syntax for per-label account binding.
`"proton-dev:INBOX"` syncs the INBOX folder only from the `proton-dev` account.
Plain labels (no colon) use the collaborator-level `account` field for scoping, or match all accounts if unset.

### How it works

1. `collab-add` creates a private GitHub repo (or `--public`), initializes it with AGENTS.md + voice.md,
   and adds it as a submodule under `shared/{name}/`
2. `sync` routes shared labels to `shared/{name}/conversations/{label}/`
3. `collab-sync` pushes synced conversations to the shared repo and pulls collaborator drafts
4. Collaborators create drafts in `shared/{name}/drafts/` with Status/Author fields
5. Brian reviews, approves, and sends via `push-draft`

### AI agents as collaborators

An AI agent (Codex, Claude Code, a custom agent) can be a collaborator. It reads conversations,
drafts replies following voice.md, and pushes to the shared repo like any other collaborator.
Brian still reviews and sends. Use `--pat` for token-based access when the collaborator isn't a
GitHub user (e.g. a CI-driven agent).

### Security model

- `.env` is gitignored -- only Brian has Gmail credentials
- Each shared repo is separate with per-user access control
- Shared repos contain ONLY threads Brian explicitly labels for that person
- Collaborators cannot see each other's shared repos

## MCP Alternative

Instead of pre-syncing to markdown files, Claude can access Gmail live via an MCP server during a session. Options:

- **Pipedream** — hosted MCP with Gmail, Calendar, Contacts (note: data passes through Pipedream)
- **Local Python MCP server** — run a Gmail MCP server locally for fully private live access (future)

Current approach (file sync) is preferred for privacy and offline use. MCP is worth revisiting for real-time workflows.

## Package-Level Instruction Files

Each subpackage (`src/sync/`, `src/draft/`, `src/cloudflare/`) can contain its own `AGENTS.md` with package-specific
conventions and context. These files are committed to the repo and auto-loaded when an agent works in that directory.
They also surface when searching dependency code across packages.

Use package-level files for deep-dives on that package's types, patterns, and gotchas. Keep the root `AGENTS.md`
focused on cross-cutting project concerns.

**Dual-name convention:** `AGENTS.md` is the canonical committed file, readable by Codex and other agents. `CLAUDE.md`
is a symlink to `AGENTS.md`, readable natively by Claude Code. For personal overrides, use `CLAUDE.local.md` (Claude
Code) or `AGENTS.local.md` (Codex) — both are gitignored.

**Actionable over informational.** Instruction files should contain the minimum needed to generate correct code: type
names, import paths, patterns, conventions, constraints. Reference material like module tables, route lists, and
architecture overviews belongs in `README.md`.

**Update with the code.** When a change affects patterns, conventions, type names, import paths, or module boundaries
documented in `AGENTS.md` or `README.md`, update those files as part of the same change.

**Stay concise.** All instruction files loaded in a session share the context window. Combined root + package files
should stay well under 1000 lines to avoid crowding out working context.

## Conventions

- Use `uv run` for script execution, never bare `python`
- Use `msgspec.Struct` for all data types — not dataclasses or TypedDict
- Use `ruff` for linting and formatting
- Use `ty` for type checking
- Keep sync, draft, and cloudflare logic in separate subpackages
- Do not commit `.env`, `accounts.toml`, `CLAUDE.local.md` / `AGENTS.local.md`, or `correspondence` (symlink to private data repo)
- Scripts must be runnable directly: `uv run src/sync/imap.py`

## Future Work

- **Project setup script**: Interactive `collab-init` or `setup` command that configures accounts.toml
- **Cloudflare routing**: TypeScript Worker consuming D1/KV data pushed from Python
- **Local MCP server**: Live email access during Claude sessions without Pipedream
- **Multi-user**: Per-user credential flow documented here when shared with another developer

## .gitignore

```
.env
accounts.toml
CLAUDE.local.md
AGENTS.local.md
correspondence
shared/
*.credentials.json
.venv/
__pycache__/
```
