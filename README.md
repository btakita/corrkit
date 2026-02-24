# Corky

> **Alpha software.** Expect breaking changes between minor versions. See [VERSIONS.md](VERSIONS.md) for migration notes.

**Full documentation: https://btakita.github.io/corky**

Sync email threads from IMAP to Markdown. Draft replies with AI assistance. Share scoped threads with collaborators via git.

Corky syncs threads from any IMAP provider (Gmail, Protonmail Bridge, self-hosted) into `mail/conversations/` — one file per thread, regardless of source. A thread that arrives via both Gmail and Protonmail merges into one file. Labels, accounts, and contacts are metadata, not directory structure.

## Install

```sh
pip install corky        # or: pipx install corky
```

Or via shell installer:

```sh
curl -sSf https://raw.githubusercontent.com/btakita/corky/main/install.sh | sh
```

Or from source: `cargo install --path .`

## Quick start

```sh
corky init --user you@gmail.com
# Edit mail/.corky.toml with credentials
corky sync
```

See the [getting started guide](https://btakita.github.io/corky/getting-started/quick-start.html) for full setup instructions.

## Key features

- **Flat conversations** — one Markdown file per thread, all sources merged
- **Sandboxed sharing** — label-based routing gives collaborators only the threads you choose
- **AI-native** — files, CLI, and git work the same for humans and agents
- **Multi-account** — Gmail, Protonmail Bridge, generic IMAP, all in one directory
- **Watch daemon** — poll IMAP on an interval with `corky watch`

## Usage

```sh
corky sync                      # Incremental IMAP sync
corky unanswered                # Threads awaiting a reply
corky draft push FILE           # Save as email draft
corky mailbox add NAME --label LABEL  # Share threads
corky contact sync              # Sync contact CLAUDE.md between root and mailboxes
corky watch                     # Poll and sync automatically
corky --help                    # All commands
```

### Telegram import

Import Telegram Desktop JSON exports into corky conversations:

```sh
corky sync telegram-import ~/Downloads/telegram-export/result.json
corky sync telegram-import ~/Downloads/telegram-export/           # directory of exports
corky sync telegram-import result.json --label personal --account tg-personal
```

Export from Telegram Desktop: Settings > Advanced > Export Telegram data > JSON format.

### Slack import

Import Slack workspace export ZIPs:

```sh
corky slack import ~/Downloads/my-workspace-export.zip
corky slack import export.zip --label work --account slack-work
```

Export from Slack: Workspace admin > Settings > Import/Export Data > Export.

See the [command reference](https://btakita.github.io/corky/guide/commands.html) for details.

## Development

```sh
cp .corky.toml.example mail/.corky.toml
make check    # clippy + test
make release  # build + symlink to .bin/corky
```

See [building](https://btakita.github.io/corky/development/building.html) and [conventions](https://btakita.github.io/corky/development/conventions.html).

## AI agent instructions

Project instructions live in `AGENTS.md` (symlinked as `CLAUDE.md`). Personal overrides go in `CLAUDE.local.md` / `AGENTS.local.md` (gitignored).
