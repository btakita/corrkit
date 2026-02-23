# Email Skill

Manage and draft correspondence using locally synced email threads.

## Core Principles

- **Draft only** — never send email directly; always save as a draft for human review
- **Match voice** — follow the Writing Voice guidelines in CLAUDE.md exactly
- **Use context** — always read the relevant thread in `conversations/` before drafting a reply
- **Be concise** — prefer shorter responses; ask before writing anything long

## Data Paths

- `conversations/` — synced email threads as Markdown (one file per thread)
- `contacts/{name}/AGENTS.md` — per-contact context for drafting
- `manifest.toml` — thread index by labels, accounts, contacts
- `drafts/` — outgoing email drafts being worked on

## Commands

- `corky unanswered` — list threads awaiting a reply
- `corky draft new --to EMAIL "Subject"` — scaffold a new draft
- `corky draft validate` — validate draft format
- `corky sync` — re-sync threads from all accounts
- `corky list-folders ACCOUNT` — list IMAP folders for an account
- `corky contact add --from SLUG` — create a contact from a conversation
- `corky contact info NAME` — show contact details and thread history

## Workflows

### Review inbox
1. Run `corky unanswered` to identify threads needing a reply
2. Read each thread and assess priority
3. Present a prioritized list with a one-line summary per thread
4. Wait for instruction before drafting anything

### Draft a reply
1. Read the full thread from `conversations/`
2. Identify the key ask or context requiring a response
3. Draft a reply in `drafts/[YYYY-MM-DD]-[slug].md` matching the voice guidelines
4. Present the draft and ask for feedback before finalizing
5. Iterate until approved — then offer to save as a draft

### Draft a new email
1. Ask for: recipient, topic, any relevant context or linked threads
2. Run `corky draft new --to EMAIL "Subject"` to scaffold the file
3. Fill in the body in the generated `drafts/[YYYY-MM-DD]-[slug].md`
4. Iterate until approved

### Enrich contact context
1. After reviewing a thread, create a contact: `corky contact add --from SLUG`
2. Read the generated `contacts/{name}/AGENTS.md` — check the ## Research section
   for hints on where to look (LinkedIn, company website, GitHub, etc.)
3. Use web search to find the contact's role, company, and interests
4. Add findings to Topics, Notes, and Research sections of AGENTS.md
5. Set ## Formality to `casual`, `professional`, or `formal` based on thread tone
6. When drafting to multiple contacts, apply maximum formality across all recipients

## Success Criteria

- Drafts sound like the user wrote them, not like an AI
- No email is ever sent without explicit approval
- Threads are read in full before drafting — no assumptions from subject alone
- Priority assessment reflects the user's relationships and context, not just recency
