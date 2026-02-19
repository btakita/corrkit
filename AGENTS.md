# Correspondence

A personal workspace for drafting emails and syncing conversation threads from Gmail (and eventually Protonmail).

## Purpose

- Sync email threads from Gmail by label into local Markdown files
- Draft and refine outgoing emails with Claude's assistance
- Maintain a readable, version-controlled record of correspondence
- Push distilled intelligence (tags, routing rules, contact metadata) to Cloudflare for email routing

## Tech Stack

- **Runtime**: Python 3.12+ via `uv`
- **Linter/formatter**: `ruff`
- **Type checker**: `ty`
- **Types/serialization**: `msgspec` (Struct instead of dataclasses)
- **Storage**: Markdown files (one file per conversation thread)
- **Email sources**: Gmail (via Gmail API), Protonmail (planned)
- **Cloudflare** (routing layer): TypeScript Workers reading from D1/KV populated by Python

## Project Structure

```
correspondence/
  AGENTS.md                      # Project instructions (CLAUDE.md symlinks here)
  pyproject.toml
  voice.md                       # Writing voice guidelines (committed)
  collaborators.toml             # Collaborator config (committed)
  .env                          # OAuth credentials and config (gitignored)
  .gitignore
  .claude/
    skills/
      email/
        SKILL.md                # Email drafting & management skill
        find_unanswered.py      # Find threads needing a reply
  src/
    sync/
      __init__.py
      gmail.py                  # Gmail API sync logic
      types.py                  # msgspec Structs (Thread, Message, etc.)
      auth.py                   # One-time OAuth flow
    draft/
      __init__.py
      push.py                   # Push draft to Gmail (draft or send)
    collab/
      __init__.py               # Collaborator config parser (collaborators.toml)
      add.py                    # collab-add command
      sync.py                   # collab-sync / collab-status commands
      remove.py                 # collab-remove command
    cloudflare/
      __init__.py
      push.py                   # Push intelligence to Cloudflare D1/KV
  conversations/                # Synced threads (gitignored — private)
    [label]/
      [YYYY-MM-DD]-[subject].md
  drafts/                       # Outgoing email drafts
    [YYYY-MM-DD]-[subject].md
  shared/                       # Collaborator submodules (tracked by git)
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

Copy `.env.example` to `.env` and fill in credentials:

```sh
cp .env.example .env
uv sync
```

Required variables in `.env`:

```
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REDIRECT_URI=http://localhost:3000/oauth/callback
GMAIL_REFRESH_TOKEN=
GMAIL_USER_EMAIL=                # Your Gmail address (used to detect unanswered threads)
GMAIL_SYNC_LABELS=correspondence   # comma-separated Gmail labels to sync (your private labels)

# Cloudflare (optional — for routing intelligence)
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_D1_DATABASE_ID=
```

### Gmail OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable the **Gmail API**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download the credentials JSON and extract `client_id` and `client_secret` into `.env`
5. Run the auth flow once to obtain a refresh token:
   ```sh
   uv run sync-auth
   ```

## Commands

```sh
uv sync                                         # Install dependencies
uv run sync-auth                                # One-time Gmail OAuth setup
uv run sync-gmail                               # Incremental sync (only new messages)
uv run sync-gmail --full                        # Full re-sync (ignores saved state)
uv run .claude/skills/email/find_unanswered.py  # List threads needing a reply
uv run push-draft drafts/FILE.md                # Save draft to Gmail
uv run push-draft drafts/FILE.md --send         # Send email
uv run pytest                                    # Run tests
uv run ruff check .                             # Lint
uv run ruff format .                            # Format
uv run ty check                                 # Type check

# Collaborator management
uv run collab-add NAME --label LABEL [--github-user USER | --pat] [--public]
uv run collab-sync [NAME]                       # Push/pull shared submodules
uv run collab-status                            # Quick check for pending changes
uv run collab-remove NAME [--delete-repo]
```

## Workflows

### Daily email review

1. Run `uv run src/sync/gmail.py` to pull latest threads
2. Ask Claude: *"Review conversations/ and identify threads that need a response, ordered by priority"*
3. For each thread, ask Claude to draft a reply matching the voice guidelines above
4. Review and edit the draft in `drafts/`
5. When satisfied, ask Claude to save it as a Gmail draft (never send directly)

### Finding unanswered threads

```sh
uv run .claude/skills/email/find_unanswered.py
```

Lists all synced threads where the last message is not from you — i.e. threads awaiting your reply.

### Drafting a new email

Ask Claude: *"Draft an email to [person] about [topic]"* — point it at any relevant thread in `conversations/` for context.

## Gmail Sync Behavior

- **Incremental by default**: Tracks IMAP UIDs in `.sync-state.json` (gitignored). Only new messages since
  last sync are fetched. Use `--full` to ignore saved state and re-fetch everything.
- **Streaming writes**: Each message is merged into its thread file immediately after fetch — no batching.
  If sync crashes mid-run, state is not saved; next run re-fetches from last good state.
- **UIDVALIDITY**: If the IMAP server resets UIDVALIDITY for a folder, that label automatically does a full resync.
- **Label routing**: Labels from `GMAIL_SYNC_LABELS` go to `conversations/{label}/`. Labels listed in
  `collaborators.toml` are automatically included in the sync and routed to `shared/{name}/conversations/{label}/`.
  A thread only needs the shared label (e.g. `for-alex`) -- no need to also label it `correspondence`.
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

Drafts live in `drafts/` (private) or `shared/{name}/drafts/` (collaborator). Filename convention: `[YYYY-MM-DD]-[slug].md`.

```markdown
# [Subject]

**To**: [recipient]
**CC**: (optional)
**Status**: draft
**Author**: brian
**In-Reply-To**: (optional — message ID)

---

[Draft body]
```

Status values: `draft` -> `review` -> `approved` -> `sent`

When asking Claude to help draft or refine an email:
- Point it at the relevant thread in `conversations/` for context
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
```

### How it works

1. `collab-add` creates a private GitHub repo (or `--public`), initializes it with AGENTS.md + voice.md,
   and adds it as a submodule under `shared/{name}/`
2. `sync-gmail` routes shared labels to `shared/{name}/conversations/{label}/`
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
- Do not commit `.env`, `CLAUDE.local.md` / `AGENTS.local.md`, or `conversations/` (private data)
- Scripts must be runnable directly: `uv run src/sync/gmail.py`

## Future Work

- **Project setup script**: Interactive `collab-init` or `setup` command that configures .env defaults
- **Protonmail sync**: Protonmail Bridge (IMAP) or Protonmail API
- **Cloudflare routing**: TypeScript Worker consuming D1/KV data pushed from Python
- **Local Gmail MCP server**: Live Gmail access during Claude sessions without Pipedream
- **Send integration**: Push approved drafts back to Gmail as drafts or send directly
- **Multi-user**: Per-user OAuth credential flow documented here when shared with another developer

## .gitignore

```
.env
CLAUDE.local.md
AGENTS.local.md
conversations/
drafts/
*.credentials.json
.sync-state.json
.venv/
__pycache__/
```
