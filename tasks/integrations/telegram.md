# Telegram Integration — corky

## Status

Research complete. Phase 1 ready to implement.

## Recommended Crate

`grammers` (MTProto user API — full history access, unlike bot API)

Feature-gated: `[features] telegram = ["grammers-client", "grammers-session", "grammers-tl-types"]`

## Phases

### Phase 1: Offline Import (current target)

`corky sync telegram-import FILE` — parse Telegram Desktop JSON exports.

- Zero new dependencies (only `serde_json`, already present)
- Thread ID: `tg:{chat_id}`
- Reuses `merge_message_to_file()`
- Messages deduplicated by `(from, date)` — existing mechanism works

Telegram Desktop JSON structure:
```json
{
  "name": "Chat Name",
  "type": "personal_chat",
  "id": 123456789,
  "messages": [
    {
      "id": 642,
      "type": "message",
      "date": "2024-10-09T19:32:23",
      "from": "Alice Smith",
      "from_id": "user653911985",
      "text": "Hello!",
      "reply_to_message_id": 640
    }
  ]
}
```

### Phase 2: Live Sync

Via `grammers-client` — connect with user auth, iterate dialogs, fetch history incrementally.
Sync state: per-chat `last_message_id`.

### Phase 3: Watch

Extend `corky watch` to call `sync_telegram_account()`. Or use `client.next_update()` for real-time.

### Phase 4: Send

Extend `draft push` to detect `tg:` prefix in `**To**` field and send via grammers.

## Config

```toml
[accounts.tg-personal]
provider = "telegram"
api_id = 12345678
api_hash_cmd = "pass telegram/api-hash"
phone = "+1234567890"
labels = ["telegram"]
```

## Conversation Mapping

| Telegram Concept | Corky Mapping |
|---|---|
| 1:1 private chat | Thread per chat. Subject = contact name. ID = `tg:{chat_id}` |
| Group chat (flat) | Thread per group. Subject = group name. ID = `tg:{chat_id}` |
| Group with topics | Thread per topic. Subject = `group / topic`. ID = `tg:{chat_id}:{topic_id}` |
| Channel | Thread per channel. Subject = channel name. ID = `tg:{channel_id}` |
