# Phase 1: DingTalk Real Evidence Closure Implementation Plan

> **Goal:** Before any Phase 1 acceptance message is sent, rotate the exposed DingTalk credential and create a readable production backup; then prove that real DingTalk text and files are persisted first, traced end to end, deduplicated, and still recover after a gateway restart.

**Scope:** This phase changes the existing DingTalk ingress and production workflow in the DataHub repository, plus the existing SDK callback/runtime-state path in the Hermes repository. It does not add a second gateway, a new product page, a hard group allowlist, or a keyword-based rejection rule.

**Repository contract:**

- DataHub worktree: `D:\zzj Claude code\aluminum-bypass\.worktrees\phase1-dingtalk-evidence-closure-20260716`; production checkout: `/srv/aluminum-bypass`.
- Hermes repository: `D:\zzj Claude code\hermes-agent`; create a dedicated Phase 1 worktree from `main`; production checkout: `/srv/hermes-cloud/runtime/.hermes/hermes-agent`.
- Merge the Hermes callback-ledger PR first and record its exact SHA. Merge the DataHub PR second and record its exact SHA. Deploy both exact SHAs together through the existing `production-sync-status.yml` workflow before running `configure-dingtalk-stream-prod.yml` verification.
- DataHub reads the callback ledger only from the Hermes runtime-state directory under `HERMES_HOME`; it never writes that ledger.

**Source boundary:** DingTalk enterprise-app events are real business evidence. `D:\输出skill` is not used in this phase.

**Content-retention boundary:** The access-controlled DataHub database may retain the sanitized business message text and extracted file text already required for report parsing, source review, and trace audit, subject to the existing size caps and secret filtering. The Hermes callback ledger, workflow artifacts, gate output, logs, reports, and PR comments retain no raw message text, filename, sender id, conversation id, download code, webhook, signed URL, or attachment bytes. Phase 1 acceptance fixtures contain synthetic labels only, not employee data or production corrections.

## Closed-loop exit gate

Phase 1 is complete only when all of the following are true:

1. The previously exposed DingTalk app secret is reset before the first marked acceptance event; the replacement is stored only in controlled secrets and both production services reconnect with it.
2. Repository history, tracked files, production frontend assets, and ordinary service logs have no untreated DingTalk secret exposure. The scan reports only findings and fingerprints, never secret values.
3. A pre-change PostgreSQL custom-format dump passes `pg_restore -l`; both production env files have readable permission-preserving backups.
4. One unique acceptance marker identifies at least 10 real text events and 5 real file events received through DingTalk Stream. A DataHub HMAC request alone is not real-Stream proof: every accepted trace hash must also exist in the Hermes SDK callback-side runtime ledger.
5. Each marked event has exactly one `dingtalk_inbound_receipts` row, one `chat_inbox` row, and one `multimodal_evidence` row sharing the same trace id.
6. The real files include at least one image, one Excel workbook, and one PDF. Every file has filename, SHA-256, sender, conversation, event time, business-date status, and explicit parse status. At least two files must contain extracted text; unsupported media must say so and must not invent text.
7. Marker suffixes `-U1` and `-U2` identify two deliberately unfamiliar Chinese expressions. The gate requires both traces even when no rigid keyword matches. Reply eligibility may be stricter, but persistence may not be.
8. `DINGTALK_AUTHORIZED_GROUP_IDS=*` remains in production. Marker suffixes `-G1` and `-P1` identify at least one group event and one private-conversation event. The gate requires both channels; if enterprise-app authorization cannot deliver one channel, Phase 1 stays blocked and reports that authorization limitation instead of adding an allowlist.
9. Replaying one marked text callback and one marked file callback creates no extra receipt, inbox, evidence, agent run, file download attempt, or Hermes reply. The production replay uses only a reconstructed minimum payload and never reads or stores raw chat or download codes.
10. Restarting `hermes-gateway` produces a fresh Stream handshake, preserves the marked evidence, and a new post-restart marked message reaches all three persistence surfaces.
11. Focused tests, backend regression, frontend regression/build, independent spec review, independent quality review, PR checks, production verification, rollback rehearsal, and the Phase 1 report all pass.

## Fixed execution loop

Every task below follows the same loop:

```text
current evidence -> failing test/gate -> smallest implementation -> focused tests
-> regression -> production-safe verification -> review -> rollback check -> commit
```

## Task 1: Persist every real Stream event before deciding whether to answer

**Files:**

- Modify `backend/app/routers/dingtalk.py`
- Modify `backend/app/core/redaction.py`
- Modify `backend/app/models/agent_communication.py`
- Modify `backend/app/services/agent_command_service.py`
- Modify `backend/app/services/hermes_factory_brain_orchestrator.py`
- Modify `backend/app/services/hermes_root_owner_production_orchestrator.py`
- Create `backend/alembic/versions/0055_chat_inbox_inbound_dedupe.py`
- Modify `backend/tests/test_dingtalk_agent_inbound_route.py`
- Modify `backend/tests/test_agent_command_rag_route.py`
- Modify `backend/tests/test_migration_chain.py`
- Modify focused orchestrator tests only when the new optional inbox parameter needs coverage

**Failing tests first:**

- An unbound real Stream text event persists receipt, inbox, and evidence but does not run or reply.
- A file-only event persists all three surfaces; its inbox text comes only from extracted text, filename, or message type.
- A Day-1 permission rejection still retains the already persisted inbox and evidence.
- A normal authorized command reuses the ingress inbox instead of creating a second row.
- A duplicate callback leaves all correlated table counts unchanged.
- Two concurrent attempts using the same receipt dedupe key cannot create two inbox rows.
- A reused inbox retains its original source fields, merges later attachment metadata, and drops download codes, session webhooks, signed URLs, tokens, and secrets.

**Implementation:**

- Create one sanitized `ChatInboxMessage` immediately after evidence persistence.
- Commit that inbox before intent, identity, permission, or reply routing.
- Pass the existing inbox to the three current agent execution paths through optional parameters.
- Add a nullable unique `chat_inbox.inbound_dedupe_key` populated from the claimed receipt. Treat its unique violation as a concurrent duplicate and read back the winning row.
- Never synthesize a business fact for a file-only inbox. Use extracted source text when available, otherwise the actual filename, otherwise the actual message type.
- Keep reply and privileged-operation checks unchanged.

**Verification:**

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_dingtalk_agent_inbound_route.py tests/test_agent_command_rag_route.py tests/test_hermes_factory_brain_orchestrator.py tests/test_hermes_root_owner_production_orchestrator.py tests/test_migration_chain.py -q
```

## Task 2: Add a reusable compare-only real evidence gate

**Files:**

- Create `backend/scripts/check_dingtalk_stream_evidence_gate.py`
- Create `backend/tests/test_check_dingtalk_stream_evidence_gate.py`
- Modify `backend/app/services/dingtalk_stream_gateway_service.py`
- Modify `backend/app/services/hermes_day1_evidence_service.py`
- Modify `backend/tests/test_dingtalk_stream_gateway_service.py`
- Modify `backend/tests/test_hermes_day1_evidence_service.py`

**Failing tests first:**

- A complete 10-text/5-file fixture passes.
- Missing receipt, inbox, or evidence fails with the exact missing trace category.
- Duplicate rows fail.
- Missing file hash, sender, conversation, event time, parse status, or business-date status fails.
- Unsupported image/PDF passes only with an explicit non-success parse status and no invented text.
- Business date status is present and consistent: `missing` requires a null date, while each of the other five allowed statuses requires an ISO date.
- Output contains counts and hashed trace references but no raw chat, signed URL, download code, token, or secret.

**Implementation:**

- Accept `--marker`, `--min-text`, `--min-files`, `--since`, `--hermes-ledger`, `--expected-u1-sha256`, `--expected-u2-sha256`, and `--output-json`.
- Persist `business_date_status` inside `MultimodalEvidence.payload` with the finite values `command_explicit`, `payload_explicit`, `filename_explicit`, `text_explicit`, `event_time_window`, or `missing`. The fixed order is command, explicit payload field, filename, absolute date in text, then factory business-clock derivation. Relative words such as today or yesterday never count as `text_explicit`; `event_time_window` requires both a valid event time and an active production workshop. Never ask a model to infer a date.
- Enforce the invariants: `missing` requires a null business date; every other status requires an ISO date; `event_time_window` requires the source workshop and event time; Day-1 command backfill must set `command_explicit`; fact-adoption rules do not become weaker because this status exists.
- Correlate rows by trace id across receipt, inbox, and evidence.
- Hash each trace id and require the same hash in the Hermes SDK callback ledger. Synthetic DataHub POST rows without that independent callback proof fail as `missing_stream_callback_proof`.
- Match text events by message text marker and file events by the actual filename marker. All five acceptance filenames must contain the marker, including image and PDF files whose body may not be extractable.
- Require the `-U1`, `-U2`, `-G1`, and `-P1` marker variants. For U1/U2, read only `ChatInboxMessage.text`, normalize with Unicode NFKC, trim leading/trailing whitespace, collapse every internal whitespace run to one ASCII space, UTF-8 encode, then compare SHA-256 to caller-supplied values without emitting the text. Require G1/P1 to resolve to group/private channels respectively.
- Produce a machine-readable result and exit nonzero on any failed gate.
- Keep verification independent from `D:\输出skill`.

## Task 2A: Add a bounded Hermes callback proof ledger

**Hermes repository files:**

- Create `gateway/xintai_callback_proof_ledger.py`
- Modify `plugins/platforms/dingtalk/adapter.py`
- Create `tests/gateway/test_xintai_callback_proof_ledger.py`
- Modify `tests/gateway/test_dingtalk_single_ingress.py`

**Cross-repository execution:**

- Work only in a dedicated Hermes Phase 1 worktree and PR; do not edit the local Hermes `main` checkout directly.
- The callback proof is written by Hermes only to `HERMES_HOME/gateway/xintai_callback_proof_ledger.json`. The DataHub workflow copies that one file to a mode-`0600` temporary path, passes it to `--hermes-ledger`, then deletes the copy; neither repository stores it as an artifact.
- The production workflow must require the deployed Hermes HEAD to equal the recorded merged Hermes SHA before the ledger can satisfy the gate.

**Implementation:**

- At `_IncomingHandler.process()`, after the DingTalk SDK callback has been parsed and before the background relay task is scheduled, append a bounded entry containing only SHA-256(trace id), message type, channel type, callback receive time, and `source=stream_callback`.
- Never store message text, filename, sender id, conversation id, download code, webhook, or secret in this ledger.
- Persist the bounded ledger beside the existing Hermes runtime state and reuse `atomic_json_write()`; production verification reads it without scraping raw logs.
- A DataHub relay or local replay must not be able to create a callback-ledger entry.
- Keep at most 2,000 callback proofs, deduplicate by trace hash, and retain no callback body or identifying values beyond the trace hash and two bounded categories. A ledger write failure is observable but must never block callback ACK or the evidence relay.

**Gate:** every Phase 1 marker row must correlate to this independent Hermes callback proof before it can count as real Stream evidence.

## Task 3: Strengthen the existing production Stream workflow

**Files:**

- Modify `.github/workflows/configure-dingtalk-stream-prod.yml`
- Modify `backend/tests/test_production_workflow_contracts.py`

**Failing contract tests first:**

- Apply mode must create and list a PostgreSQL custom backup before env changes.
- Verify mode must require a safe acceptance marker and invoke the reusable gate with 10 text and 5 files.
- Production must keep wildcard enterprise-app scope and no `DINGTALK_ALLOWED_CHATS` boundary.
- Secret checks must compare without printing the secret.
- Restart verification must prove a new handshake and retain prior evidence.
- Rollback contract tests must prove that no pre-rotation env backup can restore the exposed app secret; replacement app credentials and relay token are re-applied from controlled secrets.
- Replay contract tests must prove that the minimum in-memory payload excludes raw text, download code, webhook, URL, token, and attachment bytes; umask is `077`; no replay file/artifact is created.
- File replay contract tests must prove the trace-hashed download-attempt counter does not increase.

**Implementation:**

- Reuse the current workflow; do not create a second production operations workflow.
- Add marker and threshold inputs.
- Add DB/env preflight backup verification.
- Add exact-secret-presence checks for built frontend assets and recent service logs, emitting booleans only.
- Invoke the gate before and after controlled `hermes-gateway` restart.
- Reconstruct a minimum replay payload from non-secret columns only: trace id, channel, conversation id, sender id, message type, filename, and file id. Do not read raw payload text, download code, session webhook, signed URL, token, or attachment bytes.
- Keep replay payload in memory, set process umask `077`, do not write it to disk or artifacts, and emit only boolean/count results.
- Add a safe file-download-attempt metric keyed by trace hash. Assert it does not increase during duplicate replay.
- Assert all table counts and Hermes reply counts remain unchanged after replay.
- Rollback may restore non-secret env settings, but it must preserve the replacement DingTalk app key/secret and relay token. It must never copy the exposed credential back from a pre-rotation backup.

## Task 4: Local verification and first delivery PR

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_dingtalk_agent_inbound_route.py tests/test_check_dingtalk_stream_evidence_gate.py tests/test_production_workflow_contracts.py tests/test_dingtalk_stream_gateway_service.py tests/test_dingtalk_stream_event_service.py tests/test_dingtalk_file_text_extractor.py -q
python -m pytest -q
cd ..\frontend
npm ci --no-audit --no-fund
npm test -- --run
npm run build
```

Then run independent spec review and quality review. Fix every blocking finding. Merge the Hermes callback-ledger PR first, then the DataHub PR; wait for every required check and record both exact SHAs. Do not call Phase 1 complete yet.

## Task 5: Security preflight and credential rotation

1. Run repository/history secret scanning and record sanitized results.
2. Run the merged production workflow in preflight/status mode and record backup readability plus current counts.
3. Immediately before resetting the DingTalk app secret, request action-time confirmation because this creates persistent access credentials.
4. Reset the secret in DingTalk Open Platform, update the controlled GitHub Actions secret without exposing it, and run workflow apply mode.
5. Confirm the new Stream handshake and that the replacement secret is absent from frontend assets and ordinary service logs. No marked acceptance event may be sent before this step passes.

Rollback: restore only non-secret settings from the two env backups, re-apply the replacement credentials from controlled secrets, disable Stream intake, restart existing services, and retain already stored evidence. Never restore the exposed secret.

## Task 6: Real DingTalk acceptance set

Prepare one marker such as `XT-P1-YYYYMMDD-HHMMSS` and five harmless fixture files containing the marker. Immediately before sending/uploading, request action-time confirmation for the exact destination and files.

Send from real DingTalk clients:

- 10 Chinese text messages. Two use pre-declared unfamiliar/follow-up sentences containing marker variants `-U1` and `-U2`; record only their normalized SHA-256 values for the gate so recognition is proved without publishing chat text.
- 5 files whose filenames contain the marker and an explicit ISO business date: image, `.xlsx`, `.pdf`, and two text-extractable formats.
- One group message uses `-G1`; one private message uses `-P1`.
- At least one event after a controlled gateway restart.

The fixtures contain synthetic acceptance labels only, not employee personal data or production corrections. They are evidence-path tests, not daily-report facts.

## Task 7: Production verification, rollback rehearsal, and report PR

1. Run workflow verify mode with the marker and the 10/5 thresholds.
2. Confirm Hermes callback-ledger proof, exact one-to-one trace correlation, `-U1/-U2/-G1/-P1`, file metadata, parse honesty, duplicate replay, zero additional file-download attempts, and post-restart intake.
3. Run production status, `/readyz` detail checks, and relevant sanitized logs. `readyz=200` is not sufficient by itself.
4. Rehearse the documented rollback checks without deleting evidence.
5. Create `docs/superpowers/reports/2026-07-16-phase1-dingtalk-evidence-closure.md` with links, SHAs, counts, remaining limitations, and rollback evidence. Include no raw chat or secrets.
6. Run independent spec and quality reviews of the report and production evidence.
7. Commit the report on a fresh branch, push, open a second PR, pass checks, merge, close issue #35, update parent issue #34, and only then start Phase 2.

## Stop conditions

- Do not weaken authentication, audit, HMAC, nonce, or reply permissions to make persistence pass.
- Do not use synthetic POST events as proof of real Stream delivery.
- Do not count bot webhook output as human inbound Stream evidence unless DingTalk actually delivers it through the enterprise app and the trace proves it.
- Do not print or commit the old or replacement secret.
- Do not advance to Phase 2 while any Phase 1 exit gate is red.
