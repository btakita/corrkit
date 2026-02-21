# Versions

Corrkit is alpha software. Expect breaking changes between minor versions.

Use `BREAKING CHANGE:` prefix in version entries to flag incompatible changes.

## 0.6.0

Path resolution, `corrkit init`, and functional specification.

- **`corrkit init`**: New command to initialize a data directory for general users. `corrkit init --user you@gmail.com` creates `~/Documents/correspondence` with directory structure, `accounts.toml`, and empty config files. Supports `--provider`, `--password-cmd`, `--labels`, `--github-user`, `--name`, `--sync`, `--force`, `--data-dir` flags.
- **Path resolution (`src/resolve.py`)**: New module centralizes all path resolution. Data directory resolves in order: `correspondence/` in cwd (developer), `CORRKIT_DATA` env, `~/Documents/correspondence` (general user). Config directory: `.` if local `correspondence/` exists, otherwise same as data dir.
- **BREAKING CHANGE: Removed module-level path constants**: `CONFIG_PATH` removed from `accounts.py`, `collab/__init__.py`, `contact/__init__.py`. `CONTACTS_DIR` removed from `contact/add.py`. `STATE_FILE` and `CONVERSATIONS_DIR` removed from `sync/imap.py`. `CREDENTIALS_FILE` removed from `sync/auth.py`. `VOICE_FILE` removed from `collab/add.py`, `collab/sync.py`, `collab/reset.py`. `_DIR_PREFIXES` removed from `collab/rename.py`. All replaced by `resolve.*()` function calls. Tests that monkeypatched these constants must now patch `resolve.<function>` instead.
- **`SPECS.md`**: Language-independent functional specification for an eventual Rust port. Covers file formats, algorithms (slugify, thread key, dedup, label routing), all 18 commands, sync algorithm, collaborator lifecycle, provider presets.

**Migration from 0.5.x**: If your code or tests monkeypatch `CONFIG_PATH`, `CONTACTS_DIR`, `STATE_FILE`, `CONVERSATIONS_DIR`, `CREDENTIALS_FILE`, `VOICE_FILE`, or `_DIR_PREFIXES`, switch to patching `resolve.accounts_toml`, `resolve.contacts_dir`, `resolve.sync_state_file`, `resolve.conversations_dir`, `resolve.credentials_json`, `resolve.voice_md`, or `resolve.data_dir` respectively.

## 0.5.0

Directional collaborator repos, nested CLI, owner identity, GitHub username keys.

- **Rename `shared/` to `for/{gh-user}/`**: Collaborator submodules now live under `for/{github_user}/` instead of `shared/{name}/`. Repo naming: `{owner}/to-{collab-gh}`. This supports multi-user corrkit setups where each party has directional directories (`for/` outgoing, `by/` incoming).
- **BREAKING CHANGE: `collab-*` → `for *` / `by *`**: Flat `collab-add`, `collab-sync`, `collab-remove`, `collab-rename`, `collab-reset`, `collab-status` replaced with nested `for add`, `for sync`, `for remove`, `for rename`, `for reset`, `for status`. `find-unanswered` and `validate-draft` moved to `by find-unanswered` and `by validate-draft`. Standalone `find-unanswered` and `validate-draft` entry points kept for `uvx` use.
- **Owner identity**: New `[owner]` section in `accounts.toml` with `github_user` and optional `name`. Required for collaborator features.
- **GitHub username as collaborator key**: `collaborators.toml` section keys are now GitHub usernames (was display names). `github_user` is derived from the key. Optional `name` field stores display name.
- **Auto-derived repo**: `repo` field in `collaborators.toml` is auto-derived as `{owner_gh}/to-{collab_gh}` if omitted.
- **`for add` CLI change** (was `collab-add`): Positional arg is now `GITHUB_USER` (was `NAME`). `--github-user` flag removed (redundant). Added `--name` flag for display name.
- **Parameterized templates**: AGENTS.md and README.md templates use owner name from config instead of hardcoded "Brian".
- Help output now groups commands into sections: corrkit commands, collaborator commands (for/by), dev commands.
- `.gitignore`: `shared/` replaced with `for/` and `by/`.

**Migration from 0.4.x**: Remove existing `shared/` submodules (`git submodule deinit -f shared/{name} && git rm -f shared/{name}`), update `collaborators.toml` keys to GitHub usernames, add `[owner]` section to `accounts.toml`, re-add collaborators with `corrkit for add`. Replace `collab-*` with `for *` and `find-unanswered` / `validate-draft` with `by find-unanswered` / `by validate-draft` in scripts and aliases. Run `for reset` to update shared repo templates.

## 0.4.1

Add-label command and audit-docs fixes.

- `corrkit add-label LABEL --account NAME`: Add a label to an account's sync config via text-level TOML edit (preserves comments).
- `contact-add` integration: `--label` + `--account` automatically adds label to account sync config.
- audit-docs: Fix tree parser for symlink-to-directory entries.
- SKILL.md: Updated to reflect flat conversation directory, contacts, manifest.

## 0.4.0

Flat conversation directory, contacts, manifest.

- **Flat conversations**: All threads in `correspondence/conversations/` as `[slug].md`. No account or label subdirectories. Consolidates correspondence across multiple email accounts into one directory.
- **Immutable filenames**: Slug derived from subject on first write, never changes. Thread identity tracked by `**Thread ID**` metadata.
- **File mtime**: Set to last message date via `os.utime()`. `ls -t` sorts by thread activity.
- **Multi-source accumulation**: Threads fetched from multiple labels or accounts accumulate all sources in `**Labels**` and `**Accounts**` metadata.
- **Orphan cleanup**: `--full` sync deletes files not touched during the run.
- **manifest.toml**: Generated after sync. Indexes threads by labels, accounts, contacts, and last-updated date.
- **Contacts**: `contacts.toml` maps contacts to email addresses. Per-contact `AGENTS.md` in `correspondence/contacts/{name}/` provides drafting context. `corrkit contact-add` scaffolds new contacts.
- **tomli-w**: Added as dependency for TOML writing.
- Backward-compatible parsing of legacy `**Label**` format.

## 0.3.0

IMAP polling daemon.

- `corrkit watch` polls IMAP on an interval and syncs automatically.
- Configurable poll interval and desktop notifications via `accounts.toml` `[watch]` section.
- systemd and launchd service templates.

## 0.2.1

Maintenance release.

- CI workflow: ty, ruff, pytest on push and PR.

## 0.2.0

Collaborator tooling and multi-account support.

- `collab-reset` command (now `for reset`): pull, regenerate templates, commit and push.
- Reframed docs as human-and-agent friendly.
- `account:label` scoped routing for collaborators.
- `list-folders` command and self-signed cert support.
- Multi-account IMAP support via `accounts.toml` with provider presets.
- Collaborator tooling: `collab-add` (now `for add`), `collab-sync` (now `for sync`), `collab-remove` (now `for remove`), `find-unanswered` (now `by find-unanswered`), `validate-draft` (now `by validate-draft`).
- Multi-collaborator architecture with submodule-based sharing.

## 0.1.0

Renamed to corrkit. Unified CLI dispatcher.

- `corrkit` CLI with subcommands.
- `push-draft` command to create drafts or send emails from markdown.
- Incremental IMAP sync with `--full` option.
- Gmail sync workspace with drafting support.
