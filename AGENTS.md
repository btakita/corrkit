# Correspondence Kit

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

## Two Repos

**corrkit** is the tool — Rust source, tests, config templates. It is a public repo.

**correspondence** is the data — synced threads, drafts, contacts, collaborator submodules.
It is a separate, private repo. corrkit accesses it via a `correspondence/` path in the
working directory, which can be either:

- A **symlink** to an external clone (e.g. `correspondence -> ~/data/correspondence`)
- A **subdirectory** or nested clone inside the corrkit checkout

**Developer workflow:** `correspondence/` exists at the working directory root (symlink or subdirectory).
The `correspondence` entry in `.gitignore` keeps the data repo out of corrkit's git history.

**General user workflow:** `corrkit init --user EMAIL` creates `~/Documents/correspondence` with
config and data, and registers it as a named space. Commands find the data dir via the resolution
order in `src/resolve.rs`: local `correspondence/`, `CORRKIT_DATA` env, app config space,
`~/Documents` fallback. Use `--space NAME` to select a specific space.

## Project Structure

```
./                                 # Tool repo (this repo)
  AGENTS.md                        # Project instructions (CLAUDE.md symlinks here)
  SPECS.md                         # Functional specification
  Cargo.toml
  install.sh                       # POSIX shell installer (curl | sh)
  voice.md                         # Writing voice guidelines (committed)
  accounts.toml                    # Multi-account IMAP config (gitignored)
  accounts.toml.example            # Template with provider presets (committed)
  contacts.toml                    # Contact metadata (gitignored)
  contacts.toml.example            # Template (committed)
  collaborators.toml               # Collaborator config (committed)
  .env                             # Legacy credentials fallback (gitignored)
  .claude/
    skills/
      email/
        SKILL.md                   # Email drafting & management skill
  src/
    main.rs                        # Minimal: clap parse + dispatch
    lib.rs                         # Module declarations, re-exports
    cli.rs                         # clap derive structs (Commands, ForCommands, ByCommands)
    util.rs                        # slugify(), thread_key_from_subject(), run_cmd()
    resolve.rs                     # Path resolution (data_dir, config_dir, all derived paths)
    app_config.rs                  # Spaces, config.toml via `directories` crate
    accounts.rs                    # accounts.toml parser, provider presets, Account struct
    init.rs                        # corrkit init
    spaces.rs                      # corrkit spaces
    help.rs                        # corrkit help
    audit_docs.rs                  # corrkit audit-docs
    watch.rs                       # IMAP polling daemon (tokio for timer/signals)
    config/
      mod.rs                       # Re-exports collaborator and contact
      collaborator.rs              # collaborators.toml, Collaborator struct
      contact.rs                   # contacts.toml, Contact struct
    sync/
      mod.rs                       # sync_account, sync command entry point
      types.rs                     # Message, Thread, SyncState, LabelState
      markdown.rs                  # Thread <-> Markdown serialization/parsing
      imap_sync.rs                 # IMAP connect, fetch, merge, dedup, label routing
      manifest.rs                  # manifest.toml generation
      folders.rs                   # list-folders command
      auth.rs                      # Gmail OAuth (stub — use Python fallback)
    draft/
      mod.rs                       # parse_draft, compose_email, push/send
    collab/
      mod.rs                       # Re-exports all submodules
      add.rs                       # for add
      sync.rs                      # for sync / for status
      remove.rs                    # for remove
      rename.rs                    # for rename
      reset.rs                     # for reset
      find_unanswered.rs           # by find-unanswered
      validate_draft.rs            # by validate-draft
      templates.rs                 # AGENTS.md, README.md template generators
    contact/
      mod.rs                       # Re-exports add
      add.rs                       # contact-add
  wrapper/                           # Python wrapper package (pip install corrkit)
    pyproject.toml
    src/corrkit/__init__.py
    src/corrkit/__main__.py
  services/
    corrkit-watch.service          # systemd user unit template
    com.corrkit.watch.plist        # launchd agent template
  tests/
    common/mod.rs                  # Shared fixtures (temp data dirs, config writers)
    test_resolve.rs
    test_accounts.rs
    test_app_config.rs
    test_init.rs
    test_sync.rs
    test_draft.rs
    test_collab.rs
    test_contact.rs
    test_cli.rs

correspondence/                    # Data repo (separate, gitignored)
  conversations/                   # Synced threads (flat, one file per thread)
    [subject-slug].md              # Immutable filename, mtime = last message date
  contacts/                        # Per-contact context docs
    [name]/
      AGENTS.md                    # Relationship, tone, topics, notes
      CLAUDE.md                    # Symlink -> AGENTS.md
  drafts/                          # Outgoing email drafts
    [YYYY-MM-DD]-[subject].md
  for/                             # Collaborator submodules (outgoing)
    [gh-user]/                     # submodule -> {owner}/to-{collab-gh}
      conversations/*.md
      drafts/*.md
      AGENTS.md
      voice.md
  by/                              # Collaborator submodules (incoming, planned)
  manifest.toml                    # Thread index (generated by sync)
  .sync-state.json                 # IMAP sync state
```

## Writing Voice

See `voice.md` (committed) for tone, style, and formatting guidelines.

## Safety Rules

- **Never send email directly.** Always save as a Gmail draft for review first.
- **Never guess at intent.** If the right response is unclear, ask rather than assume.
- **Never share conversation content** outside this local environment (no third-party APIs) unless explicitly instructed.

## Environment Setup

**New user (quick install):**
```sh
curl -sSf https://raw.githubusercontent.com/btakita/corrkit/main/install.sh | sh
corrkit init --user you@gmail.com
```

**New user (from source):**
```sh
cargo install --path .
corrkit init --user you@gmail.com
```

**Developer (from repo checkout):**
```sh
cp accounts.toml.example accounts.toml   # configure your email accounts
cargo build
```

See README.md for full config reference (accounts.toml, contacts.toml, Gmail OAuth).

## Sync Behavior

- **Immutable filenames**: Slug derived from subject on first write, never changes.
  Thread identity tracked by `**Thread ID**` metadata inside the file.
- **File mtime**: Set to last message date via `libc::utime()`.
- **Multi-label accumulation**: Thread fetched from multiple labels/accounts accumulates all in metadata.
- **Incremental by default**: Tracks IMAP UIDs per-account in `.sync-state.json`. `--full` re-fetches everything.
- **Streaming writes**: Each message merged immediately. If sync crashes, state is not saved; next run re-fetches.
- **Shared label routing**: Labels in `collaborators.toml` route to `correspondence/for/{gh-user}/conversations/`.
  Supports `account:label` syntax for per-label account binding.
- **Dedup**: Messages deduplicated by `(sender, date)` tuple when merging into existing files.
- **Slug collisions**: Different threads with same slug get `-2`, `-3` suffix.
- **Orphan cleanup**: On `--full`, files not touched during sync are deleted.

## Conversation Markdown Format

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

## Draft Format

Drafts live in `correspondence/drafts/` (private) or `correspondence/for/{gh-user}/drafts/` (collaborator).
Filename convention: `[YYYY-MM-DD]-[slug].md`.

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

## Collaborators Config

The TOML section key is the collaborator's GitHub username. `repo` is auto-derived as
`{owner_gh}/to-{collab_gh}` if omitted.

```toml
[alex-gh]
labels = ["for-alex"]
name = "Alex"
account = "personal"                    # optional — bind ALL plain labels to one account

[bot-agent]
labels = ["for-bot", "proton-dev:INBOX"]   # account:label scopes to one account
```

**Label scoping**: `account:label` syntax binds a label to one account.
Plain labels use the collaborator-level `account` field, or match all accounts if unset.

## Package-Level Instruction Files

Each module directory can contain its own `AGENTS.md` with package-specific conventions.
Keep the root `AGENTS.md` focused on cross-cutting concerns.

**Dual-name convention:** `AGENTS.md` is canonical (committed). `CLAUDE.md` is a symlink.
Personal overrides: `CLAUDE.local.md` / `AGENTS.local.md` (gitignored).

**Actionable over informational.** Instruction files contain the minimum needed to generate
correct code. Reference material belongs in `README.md`.

**Update with the code.** When a change affects patterns, conventions, or module boundaries,
update instruction files as part of the same change.

**Stay concise.** Combined root + package files should stay well under 1000 lines.

## Conventions

- Use `cargo build` / `cargo test` / `cargo clippy -- -D warnings` for development
- Use `serde` derive for all data types
- Use `anyhow` for application errors, `thiserror` for domain errors
- Use `toml_edit` for format-preserving TOML edits (add-label)
- Use `std::process::Command` for git operations (not `git2`)
- Use `regex` + `once_cell::Lazy` for compiled regex patterns
- Keep sync, draft, collab, contact logic in separate modules
- Do not commit `.env`, `accounts.toml`, `contacts.toml`, `CLAUDE.local.md` / `AGENTS.local.md`, or `correspondence`
- Never bump versions automatically — the user will bump versions explicitly
- Commits that include a version change should include the version number in the commit message
- Use `BREAKING CHANGE:` prefix in VERSIONS.md entries for incompatible changes
- Update `SPECS.md` when corrkit functionality changes (commands, formats, algorithms)
- Commits must be clean — no dangling unstaged files. When splitting work across commits, stage all related files (including `Cargo.lock`)

## .gitignore

```
.env
accounts.toml
contacts.toml
CLAUDE.local.md
AGENTS.local.md
correspondence
*.credentials.json
credentials.json
.idea/
tmp/
target/
.agents/
.junie/
.kilocode/
skills/
skills-lock.json
```
