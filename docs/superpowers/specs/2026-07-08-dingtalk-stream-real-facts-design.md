# DingTalk Stream Real Facts Design

Date: 2026-07-08

Status: approved design

Project: 鑫泰铝业 数据中枢

## Goal

Connect real DingTalk group chat and group files into the production fact chain without creating a new portal, a new report system, a new table, or a standalone long-running service.

The accepted direction is:

```text
Existing hermes-gateway
  -> DingTalk Stream consumer
  -> authorized group message and file events
  -> message_text / file_text / attachment_text
  -> MultimodalEvidence
  -> DailyFactBundle
  -> compare-only daily report alignment gate
```

`hermes-gateway` has the highest priority for this integration because DingTalk group content is the highest-priority fact source for Hermes. This makes Hermes receive real operating facts first, instead of only reading them after another subsystem has already processed them.

## Non-Goals

- Do not create a new independent `hermes-dingtalk-stream-ingestor` systemd service.
- Do not create a new dashboard, portal, report system, or evidence table.
- Do not treat `D:\输出skill` as a data source. It remains compare-only answer key material.
- Do not use the custom robot webhook as a reader. Robot webhook can send messages, but cannot read group chat or files.
- Do not make message recognition brittle. Unknown wording should still be stored as evidence and only rejected when source scope is unsafe.
- Do not call the product a MES system. MES/WMS stays an external readonly source.

## Current Facts

- Production, local, and `origin/main` are at `615282a1`.
- Production `/readyz` is ready: database ok, uploads ok, MES sync ok.
- `iot_energy_sync` is unconfigured, which is expected for now.
- The existing `/api/v1/dingtalk/agent-inbound` route can write DingTalk evidence.
- The existing evidence writer stores `message_text` for chat text and `file_text` for file/attachment text.
- The daily report fact bundle can consume DingTalk text payloads as `dingtalk_supplement`.
- The latest production compare-only gate showed `allFile=0`, `confirmedFile=0`, `machineFile=0`, so the missing piece is the real DingTalk Stream event and file download path.

## Architecture

### Runtime Placement

The DingTalk Stream client runs inside the existing `hermes-gateway` runtime.

This keeps the software smaller:

```text
No new service
No new route family
No new DB table
No new UI
```

It also keeps the intelligent agent stronger:

```text
DingTalk group fact arrives
  -> Hermes gateway receives it first
  -> Hermes evidence rules classify and trace it
  -> Data hub stores the auditable fact
```

### Components

| Component | Responsibility |
|---|---|
| `hermes-gateway DingTalk Stream consumer` | Maintain DingTalk Stream connection, receive group message and file events, reconnect on failure. |
| `DingTalk event normalizer` | Normalize event payloads into the existing inbound shape: sender, group id, message id, file id, file name, event time, text. |
| `authorized group guard` | Accept only approved group ids / conversation ids. Drop everything outside allowlist. |
| `file downloader` | Use DingTalk internal app credentials to fetch file/media bytes for authorized events. |
| `file text extractor` | Convert supported file content into text: txt, csv, xlsx, docx, pdf, and OCR-ready image text when available. |
| `evidence writer` | Reuse existing DingTalk evidence persistence so records land in `MultimodalEvidence`. |
| `daily report alignment gate` | Keep using production facts plus compare-only `D:\输出skill` references. |
| `history backfill CLI` | One-time command for recent 3 completed business days, reusing the same normalizer/extractor/writer. |

## Data Flow

### Chat Message

```text
DingTalk Stream group message event
  -> group allowlist check
  -> normalize message
  -> write MultimodalEvidence.payload.message_text
  -> status machine_only or specialist_sampled
  -> DailyFactBundle can parse if content contains daily facts
```

### File Message

```text
DingTalk Stream file event
  -> group allowlist check
  -> download file bytes
  -> compute file hash and dedupe key
  -> extract text
  -> write MultimodalEvidence.payload.file_text or attachment_text
  -> DailyFactBundle can parse output-skill-like daily report fields
```

### Historical Backfill

```text
Backfill command
  -> date range: recent 3 completed business days by production business time
  -> list or fetch authorized group files/messages
  -> reuse same download/extract/write path
  -> rerun daily-report-alignment-prod compare-only gate
```

Backfill is a one-time command, not a second product path.

## Source Priority

DingTalk group chat and group files stay above data hub projection and MES/WMS projection when the evidence is authorized and within the business day window.

Priority order for daily report facts:

1. DingTalk authorized group files and chat content.
2. External readonly MES/WMS facts inside their own business domain.
3. Data hub projection / DailyFactBundle / historical reports.
4. Manual mobile or owner fill when required.
5. RAG only for explanation, never as a live numeric source.

If DingTalk conflicts with MES/WMS or data hub facts:

```text
Use DingTalk as the adopted source
Record the conflict
Keep source_ref and trace_id
Do not silently overwrite without trace
```

## Configuration

Expected production secrets or environment values:

| Key | Purpose |
|---|---|
| `DINGTALK_STREAM_ENABLED` | Enable Stream consumer inside `hermes-gateway`. |
| `DINGTALK_APP_KEY` | Internal app key. |
| `DINGTALK_APP_SECRET` | Internal app secret. |
| `DINGTALK_AGENT_ID` | Internal app agent id, if required by the SDK/API. |
| `DINGTALK_AUTHORIZED_GROUP_IDS` | Comma-separated allowlist of group/conversation ids. |
| `DINGTALK_STREAM_EVENT_TYPES` | Message/file event types to subscribe to or accept. |
| `DINGTALK_FILE_TEXT_MAX_BYTES` | Maximum file size for text extraction. |
| `DINGTALK_BACKFILL_DAYS` | Default recent business day count for backfill, initially 3. |

Secret values must stay in production secrets or `.env`; never commit them to Git, docs, frontend bundles, screenshots, or logs.

## Evidence Contract

Every accepted DingTalk fact record must include enough trace data for later audit:

| Field | Requirement |
|---|---|
| `source` | `dingtalk` |
| `channel` | `dingtalk_group` |
| `group_id` | Authorized group id / conversation id |
| `trace_id` | Event id, message id, or generated stable trace |
| `business_date` | Resolved production business date when available |
| `file_name` | Present for file events |
| `file_hash` | Present when file bytes are downloaded |
| `message_text` | Present for chat text events |
| `file_text` / `attachment_text` | Present for parsed file events |
| `parse_status` | `text_captured`, `download_failed`, `parse_failed`, or `text_unavailable` |
| `confirmation_status` | Start as `machine_only`; upgrade to `specialist_sampled` only under approved sampling rules |

## Error Handling

| Failure | Behavior |
|---|---|
| Stream disconnects | Reconnect with bounded backoff and log a health event. |
| Invalid credentials | Stop consumer, keep gateway API alive, expose unhealthy DingTalk Stream status. |
| Event from unauthorized group | Drop and log count only; do not store content. |
| Duplicate message or file | Deduplicate by message id, file id, and file hash. |
| File download fails | Store event metadata with `parse_status=download_failed`; do not invent text. |
| File parse fails | Store metadata with `parse_status=parse_failed`; do not invent facts. |
| Text does not parse as daily facts | Keep evidence for Hermes trace; DailyFactBundle should skip numeric adoption. |
| Conflicting facts | Prefer authorized DingTalk, write conflict trace, keep previous source in conflict payload. |

## Testing

### Unit Tests

- Stream event normalizer accepts flexible DingTalk payload shapes.
- Unauthorized group events are rejected before persistence.
- File event with parsed text writes `file_text`.
- Chat event writes `message_text`.
- Duplicate event does not create duplicate evidence.
- Parse failure stores metadata but no fake fact values.
- DailyFactBundle consumes real `file_text` as `dingtalk_supplement`.

### Production Smoke

1. Confirm production is synced and ready:

```powershell
gh workflow run production-sync-status.yml -f confirm=prod-sync -f mode=status
```

2. Start or restart existing `hermes-gateway` with Stream enabled.

3. Send one real authorized group text message with a daily fact.

4. Upload one real authorized group daily report or energy file.

5. Verify production diagnostics:

```text
MultimodalEvidence contains message_text or file_text
source_diagnostics.dingtalk.allFile > 0
source_diagnostics.dingtalk.parseable_file_payload_rows > 0
```

6. Run compare-only gate:

```powershell
gh workflow run daily-report-alignment-prod.yml -f confirm=daily-align -f days=3 -f reference_mode=compare
```

## Acceptance Criteria

This design is complete only when all of these are true:

1. Existing `hermes-gateway` owns the DingTalk Stream connection.
2. No standalone new long-running service is introduced.
3. Production `MultimodalEvidence` has real DingTalk `message_text` or `file_text`.
4. Recent 3 completed business days show DingTalk diagnostics with real file evidence when files exist.
5. DailyFactBundle adopts parseable authorized DingTalk facts as `dingtalk_supplement`.
6. The compare-only gate still uses `D:\输出skill` only for comparison.
7. Any remaining mismatch is reported as a source gap or business口径 conflict, not hidden by model guesses.
8. Hermes business-facing replies remain Chinese and identify itself as `鑫泰铝业智能大脑`.

## Rollback

Rollback is simple because this design avoids new persistent structures:

1. Set `DINGTALK_STREAM_ENABLED=false`.
2. Restart existing `hermes-gateway`.
3. Keep stored `MultimodalEvidence` as audit evidence; do not delete it.
4. Re-run compare-only gate to confirm the system returns to pre-Stream behavior.

## Spec Self-Review

- Placeholder scan: no TBD or TODO remains.
- Scope check: focused on DingTalk Stream facts through existing `hermes-gateway`.
- Consistency check: no new service, no new table, no new portal.
- Ambiguity check: `D:\输出skill` is compare-only; DingTalk facts must come from authorized group Stream or approved backfill.
