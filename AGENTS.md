# Correspondence Kit

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
make release                              # build + symlink to .bin/corrkit
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

## File Formats

See README.md for conversation markdown format, draft format, and status values.

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

- Use `make check` (clippy + test), `make release` (build + .bin symlink) for development
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

