# Correspondence Kit

Sync email threads from any IMAP provider to local Markdown files, draft replies with AI assistance, and push routing intelligence to Cloudflare.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

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

Provider presets fill in IMAP/SMTP connection defaults. See `AGENTS.md` for the full preset table.

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
corrkit sync                     # Sync all accounts
corrkit sync --account personal  # Sync one account
corrkit sync --full              # Full re-sync (ignore saved state)
corrkit sync-gmail               # Alias for sync (backward compat)
corrkit list-folders [ACCOUNT]   # List IMAP folders for an account
corrkit push-draft correspondence/drafts/FILE.md # Save a draft via IMAP
corrkit push-draft correspondence/drafts/FILE.md --send  # Send via SMTP
corrkit collab-add NAME --label LABEL     # Add a collaborator
corrkit collab-sync [NAME]        # Push/pull shared submodules
corrkit collab-status             # Check for pending changes
corrkit collab-remove NAME        # Remove a collaborator
corrkit audit-docs                # Audit instruction files for staleness
corrkit help                      # Show command reference
```

Run with `uv run corrkit <subcommand>` if the package isn't installed globally.

Synced threads are written to `correspondence/conversations/[account]/[label]/[YYYY-MM-DD]-[slug].md`.

## Development

```sh
uv run pytest             # Run tests
uv run ruff check .       # Lint
uv run ruff format .      # Format
uv run ty check           # Type check
uv run poe precommit      # Run ty + ruff + tests
```

## Sandboxing

Most AI email tools (OpenClaw, etc.) require OAuth access to your entire account. Once authorized, the agent can read every message, every contact, every thread — and you're trusting the service not to overreach.

Correspondence-kit inverts this. You control what any agent or collaborator can see:

1. **You label threads in your email client.** Only threads you explicitly label get synced locally.
2. **Labels route to scoped views.** Each collaborator/agent gets a submodule containing only the threads labeled for them — nothing else.
3. **Credentials never leave your machine.** `accounts.toml` is gitignored. Agents draft replies in markdown; only you can push to your email.

An agent added with `collab-add assistant --label for-assistant` can only see threads you've tagged `for-assistant`. It can't see your other conversations, your contacts, or other collaborators' repos. If the agent is compromised, the blast radius is limited to the threads you chose to share.

This works across multiple email accounts — Gmail, Protonmail, self-hosted — each with its own labels and routing rules, all funneling through the same scoped collaborator model.

## AI agent instructions

Project instructions live in `AGENTS.md` (symlinked as `CLAUDE.md`). Personal overrides go in `AGENTS.override.md` / `CLAUDE.local.md` (gitignored).
