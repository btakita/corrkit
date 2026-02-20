# Email Skill

Manage and draft correspondence using locally synced email threads.

## Core Principles

- **Draft only** — never send email directly; always save as a draft for human review
- **Match voice** — follow the Writing Voice guidelines in CLAUDE.md exactly
- **Use context** — always read the relevant thread in `conversations/` before drafting a reply
- **Be concise** — prefer shorter responses; ask before writing anything long

## Available Tools

- `correspondence/conversations/` — synced email threads as Markdown, organized by label
- `correspondence/drafts/` — outgoing email drafts being worked on
- `uv run .claude/skills/email/find_unanswered.py` — list threads awaiting a reply
- `corrkit sync` — re-sync threads from all accounts
- `corrkit list-folders ACCOUNT` — list IMAP folders for an account

## Workflows

### Review inbox
1. Run `find_unanswered.py` to identify threads needing a reply
2. Read each thread and assess priority
3. Present a prioritized list with a one-line summary per thread
4. Wait for instruction before drafting anything

### Draft a reply
1. Read the full thread from `correspondence/conversations/`
2. Identify the key ask or context requiring a response
3. Draft a reply in `correspondence/drafts/[YYYY-MM-DD]-[slug].md` matching the voice guidelines
4. Present the draft and ask for feedback before finalizing
5. Iterate until approved — then offer to save as a draft

### Draft a new email
1. Ask for: recipient, topic, any relevant context or linked threads
2. Draft in `correspondence/drafts/[YYYY-MM-DD]-[slug].md`
3. Iterate until approved

## Success Criteria

- Drafts sound like the user wrote them, not like an AI
- No email is ever sent without explicit approval
- Threads are read in full before drafting — no assumptions from subject alone
- Priority assessment reflects the user's relationships and context, not just recency
