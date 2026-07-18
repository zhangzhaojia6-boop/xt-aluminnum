# Phase 3 MES/WMS Read-Only Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove on the production machine that every registered MES/WMS SQL Server read path is read-only, that the latest three completed business dates can be read and projected with traceable outcomes, and that disconnect, timeout, and schema-change failures alert and recover without inventing data.

**Architecture:** Keep SQL Server as an external read-only fact source and keep all writes inside the Data Hub projection database. Add a closed query registry and permission probe beside the existing SQL Server adapter, a small reliability gate that emits counts and reasons but never raw rows, and a production workflow that runs the gate against the deployed SHA. Reuse `MesSyncRunLog`, the existing retry loop, business-time helpers, and the persistent event bus instead of adding a second monitoring system.

**Tech Stack:** Python 3.11, FastAPI service modules, SQLAlchemy, `pymssql`, pytest, GitHub Actions, systemd production runtime.

---

## Scope And Success Contract

- MES/WMS remains externally read-only. The gate may write audit events and projections only to the Data Hub PostgreSQL database.
- `D:\输出skill` is not used in this phase.
- No new frontend page is added. Existing `/readyz`, `/manage/alerts`, and MES status surfaces receive better evidence through existing contracts.
- A zero-row query is not converted to zero production. It is reported as `query_succeeded_no_rows` with source table, time field, and business window.
- Production passes only when all query templates pass the static SELECT-only guard, the SQL Server login has no dangerous database permissions, three completed business dates have successful sync evidence, latest lag is within the configured threshold, and every required probe either returns rows or an explicit no-data reason.
- Disconnect, timeout, and schema-change drills run with controlled fake failures on the production machine. They must create a classified alert outcome and then recover on retry; the real MES database is never disconnected or altered for the drill.

## File Map

- Modify `backend/app/adapters/mes_adapter.py`: expose a conservative `readonly` capability on the common adapter contract.
- Modify `backend/app/adapters/sqlserver_mes_adapter.py`: closed query registry, static audit, permission probe, metadata-only query probes, failure classification, and hard completion-write rejection.
- Modify `backend/app/services/work_order/_utils.py`: do not call a write method when the selected adapter declares itself read-only.
- Create `backend/app/services/mes_readonly_reliability_service.py`: three-business-date evaluation, projection counts, sync-run continuity, no-data reasons, and fault drills.
- Create `backend/scripts/check_mes_readonly_reliability.py`: sanitized JSON/text CLI and exit code gate.
- Modify `backend/app/tasks/mes_sync.py`: publish classified `mes_sync_failed` and `mes_sync_recovered` events through the existing persistent event bus.
- Create `.github/workflows/mes-readonly-audit-prod.yml`: production-only SSH gate and redacted artifact upload.
- Modify `backend/tests/test_sqlserver_mes_adapter.py`: query registry, permission, write rejection, and failure classification tests.
- Create `backend/tests/test_mes_readonly_reliability_service.py`: three-day gate and no-data behavior tests.
- Create `backend/tests/test_mes_readonly_reliability_script.py`: CLI exit and redaction tests.
- Modify `backend/tests/test_mes_sync_tasks.py`: alert and recovery event tests.
- Modify `backend/tests/test_production_workflow_contracts.py`: production workflow security and artifact tests.
- Create `docs/superpowers/reports/2026-07-18-phase3-mes-readonly-baseline.md`: sanitized production evidence, limitations, rollback, and accepted SHAs.

### Task 1: Close The SQL Server Read-Only Contract

**Files:**
- Modify: `backend/app/adapters/mes_adapter.py`
- Modify: `backend/app/adapters/sqlserver_mes_adapter.py`
- Modify: `backend/app/services/work_order/_utils.py`
- Test: `backend/tests/test_sqlserver_mes_adapter.py`
- Test: `backend/tests/test_work_order_service.py`

- [x] **Step 1: Write failing adapter-contract tests**

Add tests that require these public contracts:

```python
def test_all_registered_sqlserver_queries_are_select_only() -> None:
    audit = audit_sqlserver_readonly_contract()
    assert audit["status"] == "pass"
    assert audit["issues"] == []


def test_sqlserver_adapter_rejects_completion_writes() -> None:
    adapter = SqlServerMesAdapter(query_runner=lambda *_args, **_kwargs: [])
    with pytest.raises(MesReadOnlyViolation, match="mes_sqlserver_read_only"):
        adapter.push_completion("CARD-1", 1.0, 99.0)
```

Also add rejection cases for `SELECT ... INTO`, stacked statements, DML, DDL, and executable procedures. Add a work-order test proving a read-only adapter is not called for completion push.

- [x] **Step 2: Run the focused tests and confirm the new tests fail**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_sqlserver_mes_adapter.py tests/test_work_order_service.py -q
```

Expected: the new symbols and read-only capability are missing while existing tests remain green.

- [x] **Step 3: Implement the closed registry and hard write rejection**

Implement these stable shapes in `sqlserver_mes_adapter.py`:

```python
@dataclass(frozen=True, slots=True)
class SqlServerQuerySpec:
    probe_id: str
    query_key: str
    source_table: str
    mode: str
    event_time_field: str | None
    requires_lookup: bool = False


class MesReadOnlyViolation(RuntimeError):
    pass


def audit_sqlserver_readonly_contract() -> dict[str, Any]:
    ...


def classify_sqlserver_failure(exc: Exception) -> str:
    ...
```

The registry must cover every entry in `_QUERY_BY_KEY` and `_BETWEEN_QUERY_BY_KEY`. Format templates only with bounded numeric values, pass every rendered SQL statement through `_ensure_read_only_query`, and include a SHA-256 contract fingerprint. Add `into` to the rejected write patterns.

Add `readonly = True` to `SqlServerMesAdapter`; its `push_completion` raises `MesReadOnlyViolation('mes_sqlserver_read_only')`. Add `readonly = False` to the base adapter and check it before `_push_mes_completion_if_needed` calls `push_completion`.

- [x] **Step 4: Run focused tests until green**

Run the command from Step 2. Expected: all selected tests pass.

- [x] **Step 5: Commit the read-only boundary**

```powershell
git add backend/app/adapters/mes_adapter.py backend/app/adapters/sqlserver_mes_adapter.py backend/app/services/work_order/_utils.py backend/tests/test_sqlserver_mes_adapter.py backend/tests/test_work_order_service.py
git commit -m "feat(mes): enforce sqlserver read-only boundary"
```

### Task 2: Build The Three-Business-Date Reliability Gate

**Files:**
- Create: `backend/app/services/mes_readonly_reliability_service.py`
- Create: `backend/scripts/check_mes_readonly_reliability.py`
- Create: `backend/tests/test_mes_readonly_reliability_service.py`
- Create: `backend/tests/test_mes_readonly_reliability_script.py`

- [x] **Step 1: Write failing gate tests**

Cover these exact outcomes:

```python
def test_gate_passes_three_dates_with_rows_or_explicit_no_data() -> None:
    result = evaluate_mes_readonly_reliability(...)
    assert result["status"] == "pass"
    assert result["business_date_count"] == 3
    assert all(item["outcome"] in {"rows", "query_succeeded_no_rows"} for item in result["query_results"])


def test_gate_blocks_dangerous_permissions_projection_gap_and_stale_sync() -> None:
    result = evaluate_mes_readonly_reliability(...)
    assert {item["code"] for item in result["blockers"]} == {
        "sqlserver_write_permission",
        "projection_missing_after_source_rows",
        "mes_sync_stale",
    }
```

Add tests for a missing sync day, query failure, secret redaction, and a zero-row source query remaining missing rather than becoming numeric zero.

- [x] **Step 2: Run tests and confirm failure**

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_mes_readonly_reliability_service.py tests/test_mes_readonly_reliability_script.py -q
```

Expected: imports fail because the service and script do not exist.

- [x] **Step 3: Implement the evaluator and CLI**

Use this public service entry point:

```python
def build_mes_readonly_reliability_report(
    db: Session,
    *,
    adapter: SqlServerMesAdapter,
    business_dates: tuple[date, date, date],
    now: datetime,
    run_fault_drills: bool = True,
) -> dict[str, Any]:
    ...
```

For each business date, use `production_business_window` and probe the five dated source paths: workshop process, WMS stock detail, finished inbound header, delivery with WMS fallback, and material production. Query local projection counts by `business_date`; if the source has rows and its projection has none, block. Group recent `coil_snapshots` run logs by production business date and require at least one successful run for each requested date. Evaluate `latest_sync_status` against `stale_threshold_seconds`.

The CLI accepts `--days 3`, optional repeated `--business-date`, `--json`, `--output`, and `--fault-drill`. `--output` must resolve below `/var/lib/aluminum-bypass/acceptance` on Linux or an explicitly supplied test root. JSON contains only counts, statuses, source paths, schema-column names, hashes, and redacted errors.

- [x] **Step 4: Run focused tests until green**

Run the Step 2 command. Expected: all selected tests pass.

- [x] **Step 5: Commit the reliability gate**

```powershell
git add backend/app/services/mes_readonly_reliability_service.py backend/scripts/check_mes_readonly_reliability.py backend/tests/test_mes_readonly_reliability_service.py backend/tests/test_mes_readonly_reliability_script.py
git commit -m "feat(mes): add three-day readonly reliability gate"
```

### Task 3: Persist Failure And Recovery Signals

**Files:**
- Modify: `backend/app/services/mes_sync_service.py`
- Modify: `backend/app/tasks/mes_sync.py`
- Modify: `backend/tests/test_mes_sync_service.py`
- Modify: `backend/tests/test_mes_sync_tasks.py`

- [ ] **Step 1: Write failing retry and event tests**

Require failure kinds `connection_failed`, `query_timeout`, `schema_changed`, and `read_failed`. A first-attempt controlled failure followed by success must report `attempt_count=2` and `recovered=True`. Exhausted retries must publish `mes_sync_failed`; recovered retries must publish `mes_sync_recovered`. Event payloads may contain error class and action but no connection string or credentials.

- [ ] **Step 2: Run focused tests and confirm failure**

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_mes_sync_service.py tests/test_mes_sync_tasks.py -q
```

Expected: the new recovery fields and events are absent.

- [ ] **Step 3: Implement minimal retry metadata and persistent events**

Extend `MesSyncStats` with defaulted fields so existing callers remain compatible:

```python
attempt_count: int = 1
failure_kind: str | None = None
recovered: bool = False
```

Set them in coil and projection paths. In `_run_sync_group`, inspect the sanitized result tree, publish `mes_sync_failed` when any step is failed or raises `MesSyncVendorError`, and publish `mes_sync_recovered` when a step succeeds after retry. Continue using the existing `DatabaseEventBus`; do not create an alert table or external message.

- [ ] **Step 4: Run focused tests until green**

Run the Step 2 command. Expected: all selected tests pass.

- [ ] **Step 5: Commit failure and recovery evidence**

```powershell
git add backend/app/services/mes_sync_service.py backend/app/tasks/mes_sync.py backend/tests/test_mes_sync_service.py backend/tests/test_mes_sync_tasks.py
git commit -m "feat(mes): emit classified sync recovery events"
```

### Task 4: Add The Production Audit Workflow

**Files:**
- Create: `.github/workflows/mes-readonly-audit-prod.yml`
- Modify: `backend/tests/test_production_workflow_contracts.py`

- [ ] **Step 1: Write the failing workflow contract test**

Assert that the workflow:

- requires confirmation text `mes-readonly-audit`;
- uses the `production` environment and pinned SSH host keys;
- verifies full expected Data Hub and Hermes SHAs;
- runs the deployed backend virtualenv script with `--days 3 --fault-drill`;
- stores output under `/var/lib/aluminum-bypass/acceptance`;
- downloads and uploads only the sanitized JSON artifact;
- never echoes database URLs, passwords, SQL rows, or secret values.

- [ ] **Step 2: Run the workflow contract test and confirm failure**

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_production_workflow_contracts.py -q
```

Expected: the new workflow file is missing.

- [ ] **Step 3: Implement the production workflow**

Use `workflow_dispatch`, `concurrency.group: xintai-production-ops`, `cancel-in-progress: false`, and the existing production SSH secret names. Verify clean production worktrees and exact SHAs before running the gate. Always upload the JSON artifact with `if: always()` so a red gate remains diagnosable.

- [ ] **Step 4: Run workflow tests until green**

Run the Step 2 command. Expected: workflow contracts pass.

- [ ] **Step 5: Commit the workflow**

```powershell
git add .github/workflows/mes-readonly-audit-prod.yml backend/tests/test_production_workflow_contracts.py
git commit -m "ci(prod): add mes readonly reliability audit"
```

### Task 5: Full Verification, Review, Merge, And Production Closure

**Files:**
- Create: `docs/superpowers/reports/2026-07-18-phase3-mes-readonly-baseline.md`
- Modify: `docs/superpowers/plans/2026-07-16-production-readiness-master-plan.md`
- Modify: `docs/superpowers/plans/2026-07-18-phase3-mes-readonly-reliability-plan.md`

- [ ] **Step 1: Run all local gates**

```powershell
cd backend
$env:PYTHONPATH='.'
python -m pytest tests/test_sqlserver_mes_adapter.py tests/test_mes_readonly_reliability_service.py tests/test_mes_readonly_reliability_script.py tests/test_mes_sync_service.py tests/test_mes_sync_tasks.py tests/test_production_workflow_contracts.py -q
python -m pytest -q
cd ..\frontend
npm ci --no-audit --no-fund
npm test -- --run
npm run build
```

Expected: focused and full backend suites pass; frontend tests and production build pass. Record exact counts without calling a targeted run “full QA.”

- [ ] **Step 2: Run independent spec and quality reviews**

Review the diff against issue `#37`. Block merge for any path that can issue SQL writes, any gate that treats missing as zero, raw-row leakage, a workflow that can audit a different SHA, or a fault drill that touches the real MES schema.

- [ ] **Step 3: Push, open the PR, and pass required checks**

```powershell
git push -u origin feat/phase3-mes-readonly-reliability-20260718
gh pr create --base main --head feat/phase3-mes-readonly-reliability-20260718 --title "feat: close MES read-only reliability gate" --body-file <reviewed-pr-body-file>
```

Wait for every required check and fix all blocking review findings before merge.

- [ ] **Step 4: Merge and deploy exact SHAs**

Merge the PR, fast-forward local `main`, then run `production-sync-status.yml` in exact-SHA deploy mode with the merged Data Hub SHA and accepted Hermes SHA. Require clean worktrees, three active services, `readyz.status=ready`, MES sync `fresh/success`, and Stream `connected/fresh`.

- [ ] **Step 5: Run the real production audit**

Dispatch `mes-readonly-audit-prod.yml` for the exact deployed SHAs. The JSON artifact must show three business dates, no dangerous SQL Server permissions, every registered query statically read-only, dated probes returning rows or explicit no-data reasons, lag within threshold, and all three controlled fault drills recovered.

- [ ] **Step 6: Rehearse real rollback and redeploy**

Use `production-sync-status.yml` rollback mode to return to the previously accepted merged Data Hub SHA while keeping Hermes unchanged. Verify health, then redeploy the Phase 3 SHA and rerun the read-only audit. Do not alter or write the MES/WMS database during either operation.

- [ ] **Step 7: Archive and close Phase 3**

Write the report with workflow links, exact SHAs, three-date query counts, no-data reasons, permission result, fault-drill result, rollback evidence, and remaining limitations. Do not include credentials, raw rows, personal data, chat text, or `D:\输出skill` contents. Merge the report PR, close issue `#37`, update parent issue `#34`, and only then advance the master plan to Phase 4.

## Self-Review Result

- Every issue `#37` acceptance item maps to Tasks 1-5.
- The plan does not add a second dashboard, database, scheduler, alert table, or MES write path.
- Real-source zero rows stay missing with a reason; no step converts them to zero production.
- Fault drills execute on production code but use controlled fake failures, preserving the real SQL Server schema and connection.
- Rollback remains an actual production rollback followed by health verification and redeploy.
