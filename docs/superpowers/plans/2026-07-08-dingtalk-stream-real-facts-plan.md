# DingTalk Stream Real Facts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let real DingTalk acceptance group chat and file content enter production `MultimodalEvidence` through the existing `hermes-gateway`, then rerun the pure real-source, compare-only daily report alignment gate so the last 3 completed business days improve without using `D:\输出skill` as a fact source.

**Architecture:** Keep software smaller and Hermes stronger. Do not create a new long-running service, table, dashboard, or report system. Add DingTalk Stream/file handling inside the existing Hermes gateway path, reuse `/api/v1/dingtalk/agent-inbound`, reuse `record_day1_dingtalk_evidence`, reuse `DailyFactBundle`, and keep `D:\输出skill` comparison-only.

**Tech Stack:** Python FastAPI backend, SQLAlchemy, existing `MultimodalEvidence` model, existing DingTalk service/token code, `dingtalk-stream==0.24.3`, `httpx`, `openpyxl`, existing pytest suite, existing GitHub Actions production workflows.

---

## Plain-Language Summary

这轮只补一条链路：

```text
真实钉钉群消息/文件
  -> hermes-gateway
  -> 识别群、发送人、消息、文件
  -> 下载文件并提取文字
  -> 写入 MultimodalEvidence 的 message_text / file_text / attachment_text
  -> DailyFactBundle 按真实证据生成日报事实
  -> 用 D:\输出skill 做 compare-only 对齐检查
```

`D:\输出skill` 仍然只是答案钥匙，不能拿来填数。对齐率提高必须来自真实钉钉、MES、数据中枢、扫码补录等事实源。

## Current Facts

- Design is approved in `docs/superpowers/specs/2026-07-08-dingtalk-stream-real-facts-design.md`.
- Production/local/origin previously matched at `615282a1`; local now has one doc-only commit ahead: `4e642464 Design DingTalk Stream facts via Hermes gateway`.
- Production services were checked by `production-sync-status.yml`: `aluminum-bypass`, `hermes-gateway`, and `nginx` were active; `/readyz` was ready.
- Latest compare-only gate improved slightly but still failed because production had no real DingTalk file evidence: `allFile=0`, `confirmedFile=0`, `machineFile=0`.
- Existing `/api/v1/dingtalk/agent-inbound` can already write DingTalk evidence.
- Existing `record_day1_dingtalk_evidence` already stores `message_text` for chat and `file_text` for attachment-like payloads.
- Existing `DailyFactBundle` applies DingTalk supplements before output-skill comparison.

## External DingTalk Facts Checked

- DingTalk robot receiving supports Stream and Webhook modes; Stream is the recommended mode for receiving robot messages.
- DingTalk message files expose `downloadCode`; that code is used to obtain the actual file content.
- The official `open-dingtalk/dingtalk-stream-sdk-python` SDK shows the Python pattern: create `Credential`, create `DingTalkStreamClient`, register `ChatbotMessage.TOPIC`, then `start_forever()` or `start()` inside an existing loop.
- The official SDK latest visible release is `v0.24.3` as of 2025-10-24, so pin `dingtalk-stream==0.24.3`.

Important caution: group robot file delivery can be limited by DingTalk scene and permission. Therefore this implementation must support both live Stream events and an approved relay/backfill path through the same Hermes gateway evidence writer. That is still not a new product service; it is one ingestion path with two real inputs.

## Success Criteria

- Production `MultimodalEvidence` contains real DingTalk `message_text` from the acceptance group.
- Production `MultimodalEvidence` contains real DingTalk `file_text` or `attachment_text` from the acceptance group or an approved DingTalk relay/backfill source.
- Unauthorized group events are rejected before content is stored.
- Duplicate DingTalk messages/files do not create duplicate evidence.
- File download failure records metadata and `parse_status=download_failed`; it does not invent facts.
- File parse failure records metadata and `parse_status=parse_failed`; it does not invent facts.
- `DailyFactBundle` can consume parseable DingTalk file text as `dingtalk_supplement`.
- Recent 3 completed business days run through `daily-report-alignment-prod.yml` with `reference_mode=compare`.
- Field differences above the owner's tolerance stay visible; no model-generated fake numbers are used to hide gaps.
- Hermes business-facing behavior remains Chinese-only as `鑫泰铝业智能大脑`.

## Files To Touch

- `backend/requirements.txt`
- `backend/app/config.py`
- `backend/app/services/dingtalk_service.py`
- `backend/app/services/dingtalk_stream_event_service.py`
- `backend/app/services/dingtalk_file_text_extractor.py`
- `backend/app/services/dingtalk_stream_gateway_service.py`
- `backend/scripts/hermes_dingtalk_stream_gateway.py`
- `backend/scripts/dingtalk_real_fact_backfill.py`
- `backend/tests/test_dingtalk_stream_event_service.py`
- `backend/tests/test_dingtalk_file_text_extractor.py`
- `backend/tests/test_dingtalk_stream_gateway_service.py`
- `backend/tests/test_hermes_dingtalk_stream_gateway_script.py`
- `backend/tests/test_dingtalk_real_fact_backfill_script.py`
- `docs/superpowers/reports/dingtalk-stream-real-facts-2026-07-08.md`

No database migration is planned. Use existing `MultimodalEvidence.payload`.

## Configuration Contract

Add these settings in `backend/app/config.py`:

```python
DINGTALK_STREAM_ENABLED: bool = False
DINGTALK_AUTHORIZED_GROUP_IDS: str = ''
DINGTALK_STREAM_EVENT_TYPES: str = 'chatbot_message'
DINGTALK_ROBOT_CODE: str = ''
DINGTALK_FILE_TEXT_MAX_BYTES: int = 2_000_000
DINGTALK_BACKFILL_DAYS: int = 3
```

Add properties:

```python
@property
def dingtalk_authorized_group_ids(self) -> set[str]:
    return {item.strip() for item in self.DINGTALK_AUTHORIZED_GROUP_IDS.split(',') if item.strip()}

@property
def dingtalk_robot_code(self) -> str:
    return self.DINGTALK_ROBOT_CODE or self.DINGTALK_APP_KEY
```

Runtime validation:

- If `DINGTALK_STREAM_ENABLED=true`, require `DINGTALK_APP_KEY`, `DINGTALK_APP_SECRET`, and at least one authorized group id.
- If `DINGTALK_FILE_TEXT_MAX_BYTES < 1024`, raise a config error.
- If `DINGTALK_BACKFILL_DAYS` is outside `1..7`, raise a config error.
- Secret values must never be printed in validation output.

## Task 1: Add Config And Dependency Guard

- [ ] Add `dingtalk-stream==0.24.3` to `backend/requirements.txt`.
- [ ] Add the config fields and validation rules above to `backend/app/config.py`.
- [ ] Add tests in `backend/tests/test_hermes_dingtalk_stream_gateway_script.py` that prove the script exits cleanly with `--health` when Stream is disabled.
- [ ] Add config validation tests for missing app credentials and missing group allowlist when Stream is enabled.

Verification:

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_hermes_dingtalk_stream_gateway_script.py -q
```

Expected result:

```text
passed
```

Commit:

```powershell
git add backend/requirements.txt backend/app/config.py backend/tests/test_hermes_dingtalk_stream_gateway_script.py
git commit -m "Add DingTalk Stream configuration"
```

## Task 2: Normalize DingTalk Events Without Hard Keywords

- [ ] Create `backend/app/services/dingtalk_stream_event_service.py`.
- [ ] Implement `NormalizedDingTalkEvent` as a dataclass with:
  `source`, `channel`, `group_id`, `trace_id`, `message_id`, `sender_staff_id`, `sender_union_id`, `message_type`, `message_text`, `file_name`, `download_code`, `file_id`, `event_time`, `raw_payload`.
- [ ] Implement `normalize_dingtalk_stream_event(payload: Mapping[str, Any]) -> NormalizedDingTalkEvent`.
- [ ] Extract group id flexibly from `conversationId`, `openConversationId`, `chatId`, `sessionWebhookExpiredTime.openConversationId`, or nested `conversation.id`.
- [ ] Extract message text flexibly from `text.content`, `content.text`, `content.content`, `text`, `msgParam.content`, and `body.content`.
- [ ] Extract file metadata flexibly from `content.downloadCode`, `downloadCode`, `content.fileName`, `fileName`, `fileId`, `mediaId`, and nested `file`.
- [ ] Implement `is_authorized_group(group_id: str, allowed_group_ids: set[str]) -> bool`.
- [ ] Implement `build_stable_trace_id(event)` using message id first, then file id, then a SHA-256 hash of group id + sender + event time + text/file name.

Tests in `backend/tests/test_dingtalk_stream_event_service.py`:

- Text event normalizes from DingTalk SDK `callback.data` shape.
- File event normalizes `downloadCode` and `fileName`.
- Unknown wording is still captured as raw evidence text when source scope is authorized.
- Missing group id is rejected by the gateway layer.
- Unauthorized group id is rejected before persistence.
- Stable trace id is identical for the same event.

Verification:

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_dingtalk_stream_event_service.py -q
```

Expected result:

```text
passed
```

Commit:

```powershell
git add backend/app/services/dingtalk_stream_event_service.py backend/tests/test_dingtalk_stream_event_service.py
git commit -m "Normalize DingTalk Stream events"
```

## Task 3: Download Robot Message Files Through Existing DingTalk Service

- [ ] Extend `backend/app/services/dingtalk_service.py` with:

```python
@dataclass(frozen=True)
class DingTalkDownloadedFile:
    download_url_host: str
    content: bytes
    content_type: str | None
    size: int

def download_robot_message_file(self, *, download_code: str, robot_code: str | None = None) -> DingTalkDownloadedFile:
    ...
```

- [ ] Use the existing access-token cache.
- [ ] POST to `https://api.dingtalk.com/v1.0/robot/messageFiles/download`.
- [ ] Send header `x-acs-dingtalk-access-token: <token>`.
- [ ] Send body `{"downloadCode": download_code, "robotCode": robot_code or settings.dingtalk_robot_code}`.
- [ ] Read `downloadUrl` from the response.
- [ ] GET `downloadUrl` with a bounded timeout and return bytes.
- [ ] Log only the download URL host, not the full signed URL.
- [ ] If any request fails, raise a typed `DingTalkFileDownloadError` with a redacted message.

Tests in `backend/tests/test_dingtalk_service.py`:

- Access token is reused.
- Download URL request sends `downloadCode` and `robotCode`.
- File bytes are fetched from the returned URL.
- Signed URL is redacted from errors/log detail.
- Missing `downloadUrl` raises `DingTalkFileDownloadError`.

Verification:

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_dingtalk_service.py -q
```

Expected result:

```text
passed
```

Commit:

```powershell
git add backend/app/services/dingtalk_service.py backend/tests/test_dingtalk_service.py
git commit -m "Add DingTalk robot file download"
```

## Task 4: Extract Text From DingTalk Files Without Inventing Content

- [ ] Create `backend/app/services/dingtalk_file_text_extractor.py`.
- [ ] Implement dataclass:

```python
@dataclass(frozen=True)
class DingTalkFileText:
    status: Literal['text_captured', 'unsupported_file_type', 'parse_failed', 'too_large']
    text: str
    detail: str
    content_hash: str
```

- [ ] Implement `extract_dingtalk_file_text(file_name: str, content: bytes, max_bytes: int) -> DingTalkFileText`.
- [ ] Support `.txt`, `.csv`, `.tsv`, `.md` with UTF-8/GB18030 fallback.
- [ ] Support `.xlsx` and `.xlsm` with `openpyxl.load_workbook(read_only=True, data_only=True)`.
- [ ] Support `.xls` with existing `xlrd` dependency.
- [ ] For `.pdf`, `.docx`, and images in this pass, return `unsupported_file_type` unless the event already contains OCR/text in the payload; do not add new heavy parsing dependencies in this task.
- [ ] Normalize whitespace but keep numbers, dates, machine names, workshop names, and Chinese punctuation.
- [ ] If the file exceeds `DINGTALK_FILE_TEXT_MAX_BYTES`, return `too_large` and do not store file bytes.

Tests in `backend/tests/test_dingtalk_file_text_extractor.py`:

- Text file extracts Chinese content.
- CSV extracts rows.
- XLSX extracts sheet names and cell text.
- XLS extracts rows if `xlrd` is available in the test environment.
- Unsupported PDF returns no fake text.
- Oversized file returns `too_large`.
- Hash is stable.

Verification:

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_dingtalk_file_text_extractor.py -q
```

Expected result:

```text
passed
```

Commit:

```powershell
git add backend/app/services/dingtalk_file_text_extractor.py backend/tests/test_dingtalk_file_text_extractor.py
git commit -m "Extract DingTalk file text safely"
```

## Task 5: Write Stream Evidence Through Existing MultimodalEvidence Path

- [ ] Create `backend/app/services/dingtalk_stream_gateway_service.py`.
- [ ] Implement `ingest_dingtalk_stream_event(db: Session, payload: Mapping[str, Any]) -> dict[str, Any]`.
- [ ] Normalize the event.
- [ ] Check `settings.dingtalk_authorized_group_ids` before storing content.
- [ ] Deduplicate by `channel=dingtalk_group`, `group_id`, `trace_id`, and `file_hash` when present.
- [ ] For text events, call `record_day1_dingtalk_evidence` with `recognized_text=event.message_text`.
- [ ] For file events:
  - download by `download_code` when present;
  - extract text;
  - call `record_day1_dingtalk_evidence` with `recognized_text=file_text.text`;
  - include `fileName`, `file_name`, `downloadCode_present`, `file_hash`, `parse_status`, and redacted download status in payload.
- [ ] If download fails, store metadata only with `parse_status=download_failed`.
- [ ] If parse fails, store metadata only with `parse_status=parse_failed`.
- [ ] After storing file evidence, call existing `ingest_dingtalk_energy_file` with the extracted payload only when text or inline Excel content is available.
- [ ] Return a compact result:

```python
{
    'accepted': True,
    'duplicate': False,
    'trace_id': '...',
    'message_text': True,
    'file_text': True,
    'parse_status': 'text_captured',
}
```

Tests in `backend/tests/test_dingtalk_stream_gateway_service.py`:

- Authorized text event writes `payload.message_text`.
- Authorized file event writes `payload.file_text`.
- Unauthorized event writes nothing.
- Duplicate event writes once.
- Download failure writes metadata only and no fake text.
- Unsupported file type writes parse status and no fake text.
- Business date is resolved from event payload if present, otherwise from production business time helper.

Verification:

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_dingtalk_stream_gateway_service.py tests/test_hermes_day1_evidence_service.py tests/test_daily_fact_bundle_service.py -q
```

Expected result:

```text
passed
```

Commit:

```powershell
git add backend/app/services/dingtalk_stream_gateway_service.py backend/tests/test_dingtalk_stream_gateway_service.py
git commit -m "Ingest DingTalk Stream evidence"
```

## Task 6: Add Hermes Gateway Stream Runner

- [ ] Create `backend/scripts/hermes_dingtalk_stream_gateway.py`.
- [ ] Import `dingtalk_stream` only inside the enabled runtime path so disabled health checks do not fail before dependency installation.
- [ ] Add CLI flags:
  - `--health`: print JSON health and exit.
  - `--once-json PATH`: read one saved callback payload and ingest it, for production debugging.
  - `--dry-run`: normalize and authorize, but do not write evidence.
- [ ] When `DINGTALK_STREAM_ENABLED=false`, `--health` returns:

```json
{"ok": true, "enabled": false, "mode": "disabled"}
```

- [ ] When enabled, create `dingtalk_stream.Credential(settings.DINGTALK_APP_KEY, settings.DINGTALK_APP_SECRET)`.
- [ ] Create `DingTalkStreamClient`.
- [ ] Register one handler for `dingtalk_stream.chatbot.ChatbotMessage.TOPIC`.
- [ ] Handler calls `ingest_dingtalk_stream_event`.
- [ ] Return `AckMessage.STATUS_OK` for accepted, duplicate, unauthorized, and parse-failed events so DingTalk does not retry forever.
- [ ] Return a non-ok status only when the database is unavailable or config is invalid.
- [ ] Add bounded reconnect around `client.start_forever()` using the SDK's documented connection handling.

Tests in `backend/tests/test_hermes_dingtalk_stream_gateway_script.py`:

- `--health` disabled returns ok JSON.
- `--once-json` ingests a sample text callback.
- `--once-json --dry-run` does not write evidence.
- Missing dependency while enabled exits with a clear Chinese operator message.
- Secrets do not appear in stdout/stderr.

Verification:

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_hermes_dingtalk_stream_gateway_script.py -q
```

Expected result:

```text
passed
```

Commit:

```powershell
git add backend/scripts/hermes_dingtalk_stream_gateway.py backend/tests/test_hermes_dingtalk_stream_gateway_script.py
git commit -m "Run DingTalk Stream inside Hermes gateway"
```

## Task 7: Add Approved Backfill/Relay Path Without A New Product Service

- [ ] Create `backend/scripts/dingtalk_real_fact_backfill.py`.
- [ ] The script reads real authorized DingTalk exports or relay JSONL files and writes through `ingest_dingtalk_stream_event`.
- [ ] Accepted input:

```powershell
python scripts/dingtalk_real_fact_backfill.py --input-jsonl D:\钉钉验收群\messages.jsonl --files-root D:\钉钉验收群\files --days 3
```

- [ ] Each JSONL row must include at least one of:
  - `text`
  - `message_text`
  - `fileName` plus `localFilePath`
  - `file_name` plus `local_file_path`
- [ ] The script maps each row into the same normalized event shape and uses the same group allowlist.
- [ ] If `localFilePath` is present, read bytes from `--files-root` only; reject path traversal and absolute paths outside the root.
- [ ] If no text and no file path exist, skip row with `parse_status=text_unavailable`.
- [ ] Print a summary:

```json
{"accepted": 12, "duplicates": 3, "rejected": 1, "file_text": 5, "message_text": 7}
```

Tests in `backend/tests/test_dingtalk_real_fact_backfill_script.py`:

- JSONL text row writes `message_text`.
- JSONL file row writes `file_text`.
- Path traversal is rejected.
- Unauthorized group is rejected.
- Duplicate file is counted as duplicate.

Verification:

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_dingtalk_real_fact_backfill_script.py -q
```

Expected result:

```text
passed
```

Commit:

```powershell
git add backend/scripts/dingtalk_real_fact_backfill.py backend/tests/test_dingtalk_real_fact_backfill_script.py
git commit -m "Backfill real DingTalk facts through Hermes gateway"
```

## Task 8: Full Local Regression Gate

- [ ] Run the focused backend gate:

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest `
  tests/test_dingtalk_stream_event_service.py `
  tests/test_dingtalk_file_text_extractor.py `
  tests/test_dingtalk_stream_gateway_service.py `
  tests/test_hermes_dingtalk_stream_gateway_script.py `
  tests/test_dingtalk_real_fact_backfill_script.py `
  tests/test_dingtalk_agent_inbound_route.py `
  tests/test_hermes_day1_evidence_service.py `
  tests/test_daily_fact_bundle_service.py `
  tests/test_check_daily_report_output_skill_alignment_script.py `
  -q
```

Expected result:

```text
passed
```

- [ ] Run config health:

```powershell
cd backend
$env:PYTHONPATH='.'
python scripts/hermes_dingtalk_stream_gateway.py --health
```

Expected disabled local result unless local env enables Stream:

```json
{"ok": true, "enabled": false, "mode": "disabled"}
```

- [ ] Commit any test fixes:

```powershell
git status --short
git add backend/requirements.txt `
  backend/app/config.py `
  backend/app/services/dingtalk_service.py `
  backend/app/services/dingtalk_stream_event_service.py `
  backend/app/services/dingtalk_file_text_extractor.py `
  backend/app/services/dingtalk_stream_gateway_service.py `
  backend/scripts/hermes_dingtalk_stream_gateway.py `
  backend/scripts/dingtalk_real_fact_backfill.py `
  backend/tests/test_dingtalk_service.py `
  backend/tests/test_dingtalk_stream_event_service.py `
  backend/tests/test_dingtalk_file_text_extractor.py `
  backend/tests/test_dingtalk_stream_gateway_service.py `
  backend/tests/test_hermes_dingtalk_stream_gateway_script.py `
  backend/tests/test_dingtalk_real_fact_backfill_script.py
git commit -m "Verify DingTalk Stream fact ingestion"
```

## Task 9: Merge, Push, Deploy, And Verify Production

- [ ] Confirm clean local history:

```powershell
git status --short --branch
git log --oneline -5
```

- [ ] Push to GitHub:

```powershell
git push origin main
```

- [ ] Sync production:

```powershell
gh workflow run production-sync-status.yml -f confirm=prod-sync -f mode=sync
```

- [ ] Wait for the workflow to finish and confirm it reports:

```text
Repository: clean on main
Services: aluminum-bypass active, hermes-gateway active, nginx active
/readyz: status=ready
```

- [ ] Configure production env values on the production machine, without printing secrets.

Required secret values already come from the approved internal DingTalk app and the real acceptance group. Edit them directly on the production machine; do not echo them in CI logs, docs, or screenshots.

```text
DINGTALK_STREAM_ENABLED=true
DINGTALK_FILE_TEXT_MAX_BYTES=2000000
DINGTALK_BACKFILL_DAYS=3
HERMES_DINGTALK_MODE=stream
```

Also set or confirm these production-only secret fields in `.env`:

```text
DINGTALK_APP_KEY
DINGTALK_APP_SECRET
DINGTALK_AUTHORIZED_GROUP_IDS
DINGTALK_ROBOT_CODE
```

- [ ] Restart only the existing services:

```bash
sudo systemctl restart hermes-gateway aluminum-bypass
sudo systemctl is-active hermes-gateway aluminum-bypass nginx
```

- [ ] Run production Stream health:

```bash
cd /srv/aluminum-bypass/backend
PYTHONPATH=. .venv/bin/python scripts/hermes_dingtalk_stream_gateway.py --health
```

Expected enabled result:

```json
{"ok": true, "enabled": true, "mode": "stream"}
```

Commit is already pushed before production env edits. Do not commit production `.env`.

## Task 10: Real DingTalk Smoke

- [ ] In the authorized acceptance group, send one Chinese text message with a small daily fact, for example:

```text
验收：2026-07-07 包装入库 123.45 吨
```

- [ ] Upload one real `.txt`, `.csv`, or `.xlsx` file containing daily report-like facts.
- [ ] If group file Stream does not deliver because of DingTalk permissions, run the approved relay/backfill script against the same real exported group file and chat source:

```bash
cd /srv/aluminum-bypass/backend
PYTHONPATH=. .venv/bin/python scripts/dingtalk_real_fact_backfill.py \
  --input-jsonl /srv/aluminum-bypass/private/dingtalk-acceptance/messages.jsonl \
  --files-root /srv/aluminum-bypass/private/dingtalk-acceptance/files \
  --days 3
```

- [ ] Query production evidence counts without printing raw private chat content:

```bash
cd /srv/aluminum-bypass/backend
PYTHONPATH=. .venv/bin/python - <<'PY'
from app.database import SessionLocal
from app.models.agent_communication import MultimodalEvidence
db = SessionLocal()
try:
    q = db.query(MultimodalEvidence).filter(MultimodalEvidence.source == 'dingtalk')
    rows = q.order_by(MultimodalEvidence.id.desc()).limit(20).all()
    print({
        "recent": len(rows),
        "message_text": sum(1 for r in rows if (r.payload or {}).get("message_text")),
        "file_text": sum(1 for r in rows if (r.payload or {}).get("file_text")),
        "attachment_text": sum(1 for r in rows if (r.payload or {}).get("attachment_text")),
    })
finally:
    db.close()
PY
```

Expected result after real smoke:

```text
message_text >= 1
file_text + attachment_text >= 1
```

## Task 11: Rerun Pure Real-Source Daily Report Alignment Gate

- [ ] Run compare-only production alignment:

```powershell
gh workflow run daily-report-alignment-prod.yml -f confirm=daily-align -f days=3 -f reference_mode=compare
```

- [ ] Download or read the workflow artifact.
- [ ] Confirm the report says `reference_mode=compare`.
- [ ] Confirm no `OUTPUT_SKILL_REFERENCE_MODE=adopt` is used.
- [ ] Confirm DingTalk diagnostics show real file evidence:

```text
source_diagnostics.dingtalk.allFile > 0
source_diagnostics.dingtalk.parseable_file_payload_rows > 0
```

- [ ] Confirm recent 3 business days have field-level differences visible.
- [ ] Compare numeric fields with the owner's tolerance rule: if the fact-source value differs from `D:\输出skill` by more than 20, the row must stay failed or marked as a business口径 conflict. Do not round it away.

## Task 12: Final Production Acceptance Report

- [ ] Create `docs/superpowers/reports/dingtalk-stream-real-facts-2026-07-08.md`.
- [ ] Include:
  - local commit range
  - production HEAD
  - production `/readyz` result
  - Stream health result
  - DingTalk evidence counts
  - recent 3-day alignment rates
  - fields still over tolerance
  - whether each remaining issue is `missing_source`, `business_definition_conflict`, or `parse_gap`
  - rollback command
- [ ] Do not include secrets, raw webhook tokens, raw private chat dumps, or signed download URLs.

Commit:

```powershell
git add docs/superpowers/reports/dingtalk-stream-real-facts-2026-07-08.md
git commit -m "Report DingTalk real fact production acceptance"
git push origin main
```

## Rollback

Rollback does not delete evidence. It only stops new Stream intake:

```bash
cd /srv/aluminum-bypass/backend
sudo sed -i 's/^DINGTALK_STREAM_ENABLED=.*/DINGTALK_STREAM_ENABLED=false/' .env
sudo systemctl restart hermes-gateway aluminum-bypass
sudo systemctl is-active hermes-gateway aluminum-bypass nginx
```

Then rerun:

```powershell
gh workflow run production-sync-status.yml -f confirm=prod-sync -f mode=status
gh workflow run daily-report-alignment-prod.yml -f confirm=daily-align -f days=3 -f reference_mode=compare
```

## Plan Self-Review

- Scope is narrow: one evidence chain, no new product surface.
- No new database table or migration.
- No hard keyword-only DingTalk recognition.
- DingTalk group/file limitations are acknowledged and covered by the approved relay/backfill path.
- `D:\输出skill` remains compare-only.
- The plan has exact files, tests, production commands, and rollback.
- No unfinished marker or fake value is required for implementation.
