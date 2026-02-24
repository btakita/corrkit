# Slack Integration — corky

## Status

Research complete. Phase 1 ready to implement.

## Recommended Crate

`slack-morphism` (full type-safe Web API + Socket Mode)

Feature-gated: `[features] slack = ["slack-morphism"]`

## Phases

### Phase 1: Export/Import (current target)

`corky slack import FILE.zip` — parse Slack workspace export ZIPs.

- Only needs `zip` crate (+ `serde_json`, already present)
- Thread ID: `slack:{channel_id}:{thread_ts}`
- Groups messages by `thread_ts`
- Subject = first line of parent message (truncated to 60 chars)
- Reuses `merge_message_to_file()`

Slack export structure:
```
export/
  channels.json    # [{id, name, purpose, members}]
  users.json       # [{id, name, real_name, profile: {email}}]
  #general/
    2024-01-15.json  # [{type, user, text, ts, thread_ts?}]
```

### Phase 2: API Sync

Via `slack-morphism` — `conversations.history` + `conversations.replies`.
Incremental via `oldest` timestamp parameter.
Needs Slack mrkdwn-to-plain text conversion.

**Rate limit warning**: Non-Marketplace apps get 1 req/min on `conversations.history` since May 2025.
Mitigation: register as an internal app (retains Tier 3: ~50 req/min).

### Phase 3: Socket Mode

Real-time push via WebSocket. Needs app-level token (`xapp-...`).
No public HTTP endpoint needed (ideal for CLI).

## Config

```toml
[accounts.slack-work]
provider = "slack"
password_cmd = "pass slack/bot-token"  # xoxb-...
labels = ["general", "project-x"]
```

## Conversation Mapping

| Slack Concept | Corky Mapping |
|---|---|
| Thread (messages sharing `thread_ts`) | One Thread file |
| Top-level message (no replies) | Single-message Thread |
| Channel name | Label with `slack:` prefix |
| `ts` timestamp | Message ID |
| `user` (resolved via users.json) | Message `from` field |
