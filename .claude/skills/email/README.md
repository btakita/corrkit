# Email Skill

Claude Code skill for managing email correspondence using locally synced threads.

## Prerequisites

- `corrkit` installed and on PATH
- `accounts.toml` configured with at least one email account
- `corrkit sync` run at least once to populate `correspondence/conversations/`
- `voice.md` in the project root for writing style

## Data paths

| Path | Purpose |
|---|---|
| `correspondence/conversations/*.md` | Synced email threads (one file per thread) |
| `correspondence/drafts/*.md` | Outgoing drafts being worked on |
| `correspondence/contacts/{name}/AGENTS.md` | Per-contact context for tone and topics |
| `correspondence/manifest.toml` | Thread index by labels, accounts, contacts |

## Commands

```sh
corrkit by find-unanswered          # List threads awaiting a reply
corrkit by validate-draft FILE      # Validate draft markdown format
corrkit sync                        # Re-sync threads from all accounts
corrkit list-folders ACCOUNT        # List IMAP folders for an account
corrkit push-draft FILE             # Save draft to email provider
corrkit push-draft FILE --send      # Send via SMTP (owner only)
```

## Draft format

See the main [README.md](../../../README.md#draft-format) for the draft markdown format
and status values (`draft` -> `review` -> `approved` -> `sent`).

## Legacy files

- `find_unanswered.py` — Python predecessor of `corrkit by find-unanswered`. Requires
  `.env` with `GMAIL_USER_EMAIL`. Superseded by the Rust CLI command.