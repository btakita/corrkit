# Email Skill

Claude Code skill for managing email correspondence using locally synced threads.

## Prerequisites

- `corky` installed and on PATH
- `.corky.toml` configured with at least one email account
- `corky sync` run at least once to populate `conversations/`
- `voice.md` for writing style

## Data paths

| Path | Purpose |
|---|---|
| `conversations/*.md` | Synced email threads (one file per thread) |
| `drafts/*.md` | Outgoing drafts being worked on |
| `contacts/{name}/AGENTS.md` | Per-contact context for tone and topics |
| `manifest.toml` | Thread index by labels, accounts, contacts |

## Commands

```sh
corky unanswered                  # List threads awaiting a reply
corky draft new --to EMAIL "Subj" # Scaffold a new draft file
corky draft validate FILE         # Validate draft markdown format
corky draft validate              # Validate all drafts (root + mailboxes)
corky sync                        # Re-sync threads from all accounts
corky list-folders ACCOUNT        # List IMAP folders for an account
corky draft push FILE             # Save draft to email provider
corky draft push FILE --send      # Send via SMTP (owner only)
corky contact add --from SLUG     # Create contact from conversation
corky contact add NAME --email E  # Create contact manually
corky contact info NAME           # Show contact details + threads
```

## Draft format

See the main [README.md](../../../README.md#draft-format) for the draft markdown format
and status values (`draft` -> `review` -> `approved` -> `sent`).

