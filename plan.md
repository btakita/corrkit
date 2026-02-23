# Contact Enrichment — Plan

## Overview

Three phases:
0. **Sync pipeline: To/CC** — store recipient addresses so contacts are matched
   by what they *see*, not just what they *send*
1. **`corky contact add --from SLUG`** — create a contact from a conversation
2. **`corky contact info NAME`** — aggregate and display everything known about a contact
3. **Email skill update** — teach the agent to use these commands + web search

The `contact` command becomes a subcommand group (like `draft`, `mailbox`).
The existing `contact-add` stays as a hidden backward-compatible alias.

## CLI Design

```
# New subcommand group
corky contact add NAME --email EMAIL
corky contact add --from SLUG
corky contact info NAME

# Hidden backward-compatible alias (remove --label and --account)
corky contact-add NAME --email EMAIL
```

### `contact add` arguments

```rust
#[derive(Subcommand)]
pub enum ContactCommands {
    /// Add a new contact
    Add {
        /// Contact name (optional with --from)
        name: Option<String>,

        /// Email address(es) — conflicts with --from
        #[arg(long = "email")]
        emails: Vec<String>,

        /// Create from a conversation slug
        #[arg(long, conflicts_with = "emails")]
        from: Option<String>,
    },

    /// Show contact info
    Info {
        /// Contact name
        name: String,
    },
}
```

Validation (in the handler, not clap):
- `--from` without `--email`: OK (derive from conversation)
- `--email` without `--from`: requires `name` positional
- Both `--from` and `--email`: clap `conflicts_with` prevents this
- `--from` with multiple senders and no `--name`: print candidates, bail

### `contact info` output

```
Contact: alice

  Emails: alice@example.com, alice@work.com

--- AGENTS.md ---
# Contact: alice
(full content)

--- Threads (3) ---
  2025-02-15  re-project-update       Re: Project Update
  2025-02-10  meeting-follow-up       Meeting Follow-Up
  2025-01-28  intro                   Introduction

Last activity: Sat, 15 Feb 2025
```

---

## Phase 0: To/CC in the Sync Pipeline

Currently each message only stores `from`. To and CC headers are available in the
raw email but dropped during IMAP sync. This means a contact who is CC'd on every
thread but never replies is invisible to the manifest and to `contact add --from`.

### 0.1 `src/sync/types.rs` — add fields to `Message`

```rust
pub struct Message {
    pub id: String,
    pub thread_id: String,
    pub from: String,
    #[serde(default)]
    pub to: String,       // NEW — comma-separated "Name <email>, ..."
    #[serde(default)]
    pub cc: String,       // NEW — comma-separated "Name <email>, ..."
    pub date: String,
    pub subject: String,
    pub body: String,
}
```

Use `String` (not `Vec<String>`) to match the `from` field pattern — raw header
value stored verbatim. `#[serde(default)]` ensures backward compat with old
sync state.

### 0.2 `src/sync/imap_sync.rs` — parse To/CC headers

After the `from` extraction (line ~429), add:

```rust
let to = parsed
    .headers
    .iter()
    .find(|h| h.get_key_ref().eq_ignore_ascii_case("To"))
    .map(|h| h.get_value())
    .unwrap_or_default();

let cc = parsed
    .headers
    .iter()
    .find(|h| h.get_key_ref().eq_ignore_ascii_case("Cc"))
    .map(|h| h.get_value())
    .unwrap_or_default();
```

And add `to, cc` to the `Message` construction at line ~446.

### 0.3 `src/sync/markdown.rs` — serialize/parse To/CC per message

**Serialization** — in `thread_to_markdown()`, after the `## From — date` line,
emit optional metadata:

```markdown
---

## Alice <alice@example.com> — Mon, 10 Feb 2025 10:00:00 +0000

**To**: Bob <bob@example.com>, Charlie <charlie@example.com>
**CC**: Dave <dave@example.com>

Message body here
```

Only emit `**To**:` / `**CC**:` lines when non-empty. This keeps existing
conversations unchanged until re-synced.

**Parsing** — in `parse_thread_markdown()`, after capturing the message header,
look for `**To**:` and `**CC**:` lines before collecting body lines. These use
the same `META_RE` pattern (`^\*\*(.+?)\*\*:\s*(.+)$`). The parser should:

1. After `MSG_HEADER_RE` match, enter a "message metadata" state
2. While in this state, check each line against `META_RE` for `To` and `CC` keys
3. On first non-metadata, non-blank line, switch to body collection
4. Blank lines between metadata and body are consumed (not added to body)

**Backward compatibility**: Old conversation files without `**To**:`/`**CC**:` lines
parse correctly — the fields default to empty strings. No migration needed.

### 0.4 `src/sync/manifest.rs` — match contacts in To/CC

Currently `generate_manifest()` only extracts emails from `msg.from`. Expand to
also extract from `msg.to` and `msg.cc`:

```rust
for msg in &thread.messages {
    // Extract all email addresses from from, to, cc
    for field in [&msg.from, &msg.to, &msg.cc] {
        for cap in EMAIL_RE.captures_iter(field) {
            let addr = cap[1].to_lowercase();
            if let Some(cname) = email_to_contact.get(&addr) {
                if !thread_contacts.contains(cname) {
                    thread_contacts.push(cname.clone());
                }
            }
        }
    }
}
```

This means a contact will appear in `manifest.toml` if they sent, received, or
were CC'd on any message in the thread.

### 0.5 SPECS.md — update format and algorithm docs

- §3.1 (Conversation Markdown): add per-message `**To**:` and `**CC**:` lines
- §4.6 (Manifest Generation): note that contacts are matched by from, to, and cc
- §6.3 (Message Parsing): add To and CC to the parsed fields list

### 0.6 Existing conversation files

Old files without To/CC lines continue to work. A `corky sync full` will
regenerate all conversation files with the new format. No mandatory migration.

### 0.7 Tests for Phase 0

- `src/sync/markdown.rs` unit tests: roundtrip with to/cc fields
- `src/sync/markdown.rs` unit tests: parse old format (no to/cc) still works
- `tests/test_sync.rs`: manifest includes contacts matched by to/cc

---

## Phase 1: `contact add --from SLUG`

### 1.1 `src/cli.rs` — add `ContactCommands` enum and `Contact` subcommand

Add `ContactCommands` enum (above). Add to `Commands`:

```rust
/// Contact commands
#[command(subcommand)]
Contact(ContactCommands),
```

Keep existing `ContactAdd` variant but mark hidden:
```rust
#[command(hide = true)]
ContactAdd { ... }  // unchanged
```

### 1.2 `src/contact/mod.rs` — add modules

```rust
pub mod add;
pub mod from_conversation;
pub mod info;
```

### 1.3 `src/contact/add.rs` — extract `generate_agents_md` + add enriched variant

Make `generate_agents_md(name)` public (rename to `pub fn default_agents_md`).
Update the default template to include the new `## Formality` and `## Research`
sections (both the manual and enriched paths get the same structure).

Add `run_with_agents_md(name, emails, agents_md_content)` — shared creation logic
(directory, symlink, save_contact, print). The existing `run()` calls this with
`default_agents_md(name)`.

Add a new function for enriched AGENTS.md:

```rust
pub fn enriched_agents_md(
    name: &str,
    topics: &[String],
    other_participants: &[String],
    email_domain: Option<&str>,  // e.g. "example.com" for Research hints
) -> String
```

This generates the same template as `default_agents_md` but pre-fills:

- **Topics** — thread subjects the contact appears in
- **Formality** — defaults to `professional`, user can change to `casual`/`formal`
- **Tone** — lists other known participants who share threads, so the user
  can annotate tone adjustments

#### Multi-contact drafting principle

When multiple contacts are on the same thread, the agent reads all of their
AGENTS.md files. The rule is **maximum formality and maximum information gating**:
if alex is `casual` and suzy is `professional`, the draft should match suzy's
level — unless the thread is a known team/cohort context where informality is
established. The AGENTS.md is the full source of truth for each contact — the
`## Formality` and `## Tone` sections are scaffolding, but the entire document
(including free-form notes) is considered.

The SKILL.md workflow section should document this principle so the agent
applies it consistently.

#### Agentic population

The agentic loop does best-effort population of AGENTS.md when creating a
contact: pre-fill topics from conversation subjects, set formality default,
list shared participants. The user then edits and provides feedback in
iterative loops with the agent. AGENTS.md can also contain hints for where
to look for more details (e.g. "Check LinkedIn for current role",
"Company website: example.com").

Full output example for `enriched_agents_md("alice", &["Project Update"], &["bob"])`:

```markdown
# Contact: alice

Context for drafting emails to or about alice.

## Relationship

<!-- How you know this person, what they work on, shared history -->

## Formality

professional

<!-- Options: casual, professional, formal.
     Applies to group emails — use maximum formality across all recipients. -->

## Tone

<!-- Communication style for alice.
     Defaults to voice.md; note overrides here.

     Shared threads with: bob
     Note any tone adjustments when these people are also on the thread. -->

## Topics

- Project Update (from conversation)

## Research

<!-- Where to look for more details about this contact. -->
- Email domain: example.com

## Notes

<!-- Freeform: quirks, preferences, pending items, important dates -->
```

The `other_participants` list is built from all non-owner emails in the
conversation that are *not* the contact being created. If the list is empty
(1:1 thread), the "Shared threads with" hint is omitted.

**Name derivation**: The contact directory name is derived by slugifying the
display name from the email header (e.g. `Alice Smith` -> `alice-smith`).
The `--name` flag overrides this. The slugify function is the existing
`crate::util::slugify()`.

**Multiple emails**: If the same person appears with different email addresses
across from/to/cc in the conversation (e.g. `alice@work.com` in From,
`alice@personal.com` in CC), all distinct addresses are collected into the
contact's `emails` field. The output logs which addresses were found so the
user can review and edit the `[contacts.{name}]` section in `.corky.toml`.

### 1.4 `src/contact/from_conversation.rs` — new module

Core function:

```rust
pub fn run(slug: &str, name: Option<&str>) -> Result<()>
```

Algorithm (module doc comment in from_conversation):

1. **Find conversation file** — search `conversations/{slug}.md`, then
   `mailboxes/*/conversations/{slug}.md`. Bail with helpful error if not found.

2. **Parse thread** — use `parse_thread_markdown()` from `src/sync/markdown.rs`.

3. **Load config** — `CorkyConfig` for owner account emails.

4. **Extract non-owner participants** — for each message, extract `<email>` from
   `from`, `to`, and `cc` fields. Filter out owner emails using best-effort
   matching against `accounts.*.user`:
   - Exact email match (case-insensitive)
   - Display name match against `[owner] name` (case-insensitive)
   - Partial name match: strip titles (`Dr.`, `Prof.`), middle names, suffixes (`Jr.`, `III`)

   Collect unique `(display_name, email)` pairs. If a participant appears with
   multiple emails across messages, group them by display name (exact match)
   and collect all addresses.

   If a match is uncertain (partial name only, no email confirmation), log a
   warning: `"Assuming '{name}' is owner — check .corky.toml if incorrect"`.

5. **Handle participant count**:
   - 0 participants: bail "No non-owner participants found in this conversation"
   - 1 participant: auto-derive name from display name (slugify), use `--name`
     override if given
   - 2+ participants: if `--name` given, find matching participant; otherwise print
     candidates and bail "Multiple participants found. Use --name to select one."

   If the auto-derived slug is wrong, the user can re-run with `--name` to
   override. A future `corky contact rename` command could rename an existing
   contact directory — out of scope for this feature.

6. **Build contact** — `Contact { emails }`. The `labels` and `account` fields
   on Contact are redundant with manifest.toml (which aggregates them from
   conversations). Remove them from the `Contact` struct:

   ```rust
   pub struct Contact {
       #[serde(default)]
       pub emails: Vec<String>,
   }
   ```

   Existing `.corky.toml` files with `labels` and `account` fields will
   silently ignore them on parse (`#[serde(default)]` + missing fields are
   OK in serde). The `save_contact()` function stops writing them.

   The `--label` and `--account` flags on the old `contact-add` command
   become no-ops (hidden alias, backward compat). The new `contact add`
   path doesn't offer them. If users need to add a label to an account's
   sync config, they use `corky add-label LABEL --account NAME` directly.

7. **Collect other participants** — from the full participant list, remove the
   selected contact. These become `other_participants` for the AGENTS.md template.

8. **Generate enriched AGENTS.md** — call
   `enriched_agents_md(name, &[subject], &other_participants)`.
   Pre-fills Topics with the thread subject and Tone with shared-thread hints.
   See section 1.3 for the full template.

9. **Delegate to `add::run_with_agents_md()`** — shared creation logic
   (directory, symlink, save_contact, print).

### 1.5 `src/main.rs` — dispatch

Add match arm:
```rust
Commands::Contact(cmd) => match cmd {
    ContactCommands::Add { name, emails, from } => {
        if let Some(slug) = from {
            corky::contact::from_conversation::run(&slug, name.as_deref())
        } else {
            let name = name.ok_or_else(|| anyhow::anyhow!("NAME required when not using --from"))?;
            corky::contact::add::run(&name, &emails)
        }
    }
    ContactCommands::Info { name } => corky::contact::info::run(&name),
},
```

### 1.6 `src/help.rs` — update command reference

Replace `contact-add` line with:
```rust
("contact add NAME --email EMAIL", "Add a contact with context docs"),
("contact add --from SLUG", "Create contact from a conversation"),
("contact info NAME", "Show contact info and thread history"),
```

---

## Phase 2: `contact info NAME`

### 2.1 `src/contact/info.rs` — new module

```rust
pub fn run(name: &str) -> Result<()>
```

Algorithm:

1. **Load contact from config** — `load_contacts(None)?`. Bail if not found.

2. **Print config section** — emails.

3. **Print AGENTS.md** — read `contacts/{name}/AGENTS.md` if it exists.

4. **Scan manifest for threads** — load `manifest.toml` (root), then each
   `mailboxes/*/manifest.toml`. Each manifest only indexes threads in its
   own `conversations/` directory. A parent mailbox that routes to a child
   sees only the threads it routed — if the child has an independent email
   source adding threads, those appear only in the child's manifest.

   Iterate threads where `contacts` array contains `name`. With Phase 0,
   this includes threads where the contact was a To/CC recipient.
   Sort by `last_updated` descending.

5. **Print thread list** — date, slug, subject per line. Group by scope
   (root vs mailbox name) when threads come from multiple manifests.

6. **Print summary** — thread count, last activity date.

### 2.2 `draft push` credential bubbling

Child mailboxes may not have their own IMAP/SMTP credentials — they rely on
the parent's `.corky.toml` accounts to send. When `draft push --send` runs
from a mailbox context, resolve credentials bottom-up:

1. Check the leaf mailbox's `.corky.toml` for matching account credentials
2. Walk up to the parent mailbox, then root
3. If no credentials found at any level, bail with error

This is needed for the collaboration workflow where a child mailbox drafts
a reply and the parent's account sends it.

---

## Phase 3: Email Skill + Docs

### 3.1 `.claude/skills/email/SKILL.md` — add contact workflow

Add to "Use These Paths and Commands":
```
- `corky contact add --from SLUG` — create a contact from a conversation
- `corky contact info NAME` — show contact details and thread history
```

Add new workflow section:

```markdown
### Enrich contact context
1. After reviewing a thread, create a contact: `corky contact add --from SLUG`
2. Read the generated `contacts/{name}/AGENTS.md` — check the ## Research section
   for hints on where to look (LinkedIn, company website, GitHub, etc.)
3. Use web search to find the contact's role, company, and interests
4. Add findings to Topics, Notes, and Research sections of AGENTS.md
5. Set ## Formality to `casual`, `professional`, or `formal` based on thread tone
6. When drafting to multiple contacts, apply maximum formality across all recipients
```

### 3.2 `.claude/skills/email/README.md` — add commands

Add to Commands section:
```sh
corky contact add --from SLUG        # Create contact from conversation
corky contact info NAME              # Show contact details + threads
```

### 3.3 `SPECS.md` — add sections

**Section 5.22 — contact add**
```
corky contact add NAME --email EMAIL
corky contact add --from SLUG [--name NAME]
```

Document the `--from` flow: find conversation, extract participants (from + to + cc),
filter owner, handle single/multiple, create enriched AGENTS.md.

Hidden alias: `corky contact-add` (backward-compatible, unchanged).

**Section 5.23 — contact info**
```
corky contact info NAME
```

Print contact config, AGENTS.md content, matching threads from manifest.toml,
summary with thread count and last activity.

### 3.4 `docs/guide/commands.md` — update Contacts section

Replace single `contact-add` line with full section covering both commands.

### 3.5 `docs/reference/specs.md` — mirror SPECS.md changes

### 3.6 Tests

**`tests/test_contact_from_conversation.rs`** — integration tests:

- Single participant conversation: creates contact with correct name/email
- Contact found via To/CC (never sent a message): still detected
- Multiple participants without `--name`: prints candidates, exits 1
- Multiple participants with `--name`: creates correct contact
- Conversation not found: helpful error message
- No non-owner participants: appropriate error
- Contact already exists: bail
- AGENTS.md Topics section pre-filled from subject

**`tests/test_contact_info.rs`** — integration tests:

- Contact exists with threads in manifest: prints all sections
- Contact matched via To/CC appears in thread list
- Contact exists, no manifest: prints config + AGENTS.md, skip threads
- Contact not found: error message

**`tests/test_cli.rs`** — CLI parsing:

- `contact add NAME --email EMAIL` parses correctly
- `contact add --from SLUG` parses correctly
- `contact add --from SLUG --email EMAIL` fails (conflicts_with)
- `contact-add NAME --email EMAIL` still works (hidden alias)
- `contact info NAME` parses correctly

## New/Modified Files

| File | Change |
|------|--------|
| `src/sync/types.rs` | Add `to` and `cc` fields to `Message` |
| `src/sync/imap_sync.rs` | Parse To/CC headers |
| `src/sync/markdown.rs` | Serialize/parse per-message `**To**:`/`**CC**:` lines |
| `src/sync/manifest.rs` | Match contacts by from + to + cc |
| `src/contact/from_conversation.rs` | **New** — find conversation, extract participants, create enriched contact |
| `src/contact/info.rs` | **New** — aggregate and display contact info |
| `src/contact/mod.rs` | Add new modules |
| `src/contact/add.rs` | Make `generate_agents_md` public, add `enriched_agents_md` + `run_with_agents_md` |
| `src/cli.rs` | Add `ContactCommands` enum, `Contact` subcommand, keep hidden `ContactAdd` |
| `src/main.rs` | Dispatch for `Contact(cmd)` |
| `src/help.rs` | Update command reference |
| `.claude/skills/email/SKILL.md` | Add contact commands and workflow |
| `.claude/skills/email/README.md` | Add commands to table |
| `SPECS.md` | Update §3.1, §4.6, §6.3; add §5.22, §5.23 |
| `docs/guide/commands.md` | Update contacts section |
| `docs/reference/specs.md` | Mirror SPECS.md |
| `tests/test_contact_from_conversation.rs` | Integration tests |
| `tests/test_contact_info.rs` | Integration tests |
| `tests/test_cli.rs` | CLI parsing tests |

## Edge Cases

- **Contact already exists** — bail with message (existing behavior)
- **Conversation not found** — search root + all mailboxes, bail with "not found" listing searched paths
- **No non-owner participants** — bail "No non-owner participants found"
- **Multiple participants** — print list with index, require `--name`
- **`--from` and `--email` both given** — clap `conflicts_with` rejects
- **No manifest.toml** — `contact info` prints config + AGENTS.md, shows "No manifest.toml found" note
- **Participant has no `<email>`** — skip (some messages may have bare names)
- **Display name is just an email** — use email local part as name (e.g. `alice` from `alice@example.com`)
- **BCC** — not available in received email headers; cannot be extracted
- **Old conversation files** — no `**To**:`/`**CC**:` lines; parse as empty, still work
- **Tone-switching in group threads** — when multiple people are on a thread, the user's tone may differ per person (e.g. chummy with one, formal with another). The enriched AGENTS.md Tone section lists other known participants in shared threads as a prompt for the user to annotate adjustments.

## Verification

1. `make check` passes
2. `corky sync full` regenerates conversations with To/CC lines
3. `manifest.toml` includes contacts matched by To/CC
4. `corky contact add --from SLUG` finds participants from from + to + cc
5. `corky contact info NAME` shows threads where contact was sender or recipient
6. `corky contact-add` (hidden alias) still works
7. `corky audit-docs` clean
