# Backend Service Split — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split 4 oversized backend service files (6,855 total lines) into focused sub-modules using a thin proxy re-export pattern. All 502 existing tests continue to pass with zero import changes.

**Architecture:** Each service file becomes a package directory with sub-modules. The original module path stays importable via a thin proxy file that re-exports all public names from sub-modules. Internal helpers move to `_utils.py` or domain-specific sub-modules.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, pytest

**Invariants:**
- Zero import changes in test files or other services
- All public functions remain importable from original module path
- `cd backend && python -m pytest -q` passes after each task
- No new dependencies introduced
- Every sub-module has `from __future__ import annotations` at the top

---

### Task 1: Split `report_service.py` (2433 lines) into `backend/app/services/report/`

**Files:**
- Create: `backend/app/services/report/__init__.py` (thin proxy)
- Create: `backend/app/services/report/_utils.py`
- Create: `backend/app/services/report/report_generation.py`
- Create: `backend/app/services/report/dashboard_builder.py`
- Create: `backend/app/services/report/lane_builders.py`
- Remove: `backend/app/services/report_service.py` (after proxy is verified)

#### Sub-module: `_utils.py` — Shared constants and helpers

Move module-level constants (lines 43-55) and these functions:
- `_to_float` (line 548)
- `_workshop_name_map` (line 554)
- `_shift_code_map` (line 558)
- `_normalize_scope` (line 562)
- `_mobile_report_decision_status` (line 568)
- `_is_leadership_ready_shift` (line 580)
- `_query_shift_items` (line 586)
- `_safe_latest_mes_sync_status` (line 57)
- `_safe_energy_summary_for_date` (line 77)
- `_safe_recent_import_batches` (line 89)
- `_safe_recent_reports` (line 96)
- `_safe_latest_published_report_time` (line 103)
- `_safe_pending_shift_items` (line 110)
- `_normalize_blocker_summary` (line 123)

Also move constants: `VALID_REPORT_TYPES`, `CANONICAL_REPORT_SCOPE`, `VALID_SCOPES`, `VALID_OUTPUT_MODES`, `REQUIRED_IMPORT_TYPES`, `READY_REPORT_STATUSES`.

#### Sub-module: `report_generation.py` — Report lifecycle

Move these functions:
- `_build_analysis_handoff` (line 138)
- `resolve_report_delivery_payload` (line 448)
- `_build_report_event_payload` (line 490)
- `_generate_production_report` (line 609)
- `_generate_attendance_report` (line 686)
- `_generate_exception_report` (line 708)
- `_format_workshop_output_top` (line 739)
- `_build_production_text_summary` (line 746)
- `_build_attendance_text_summary` (line 762)
- `_format_exception_counter` (line 773)
- `_build_exception_text_summary` (line 780)
- `_build_boss_text_summary` (line 790)
- `_build_canonical_workshop_output_summary` (line 856)
- `_generate_report_payload` (line 876)
- `_apply_output_mode` (line 897)
- `generate_daily_reports` (line 910)
- `review_report` (line 999)
- `run_daily_pipeline` (line 1046)
- `finalize_report` (line 1117)
- `publish_report` (line 1171)
- `list_reports` (line 1235)
- `get_report` (line 1255)
- `_count_reports_by_status` (line 1259)

#### Sub-module: `dashboard_builder.py` — Dashboard composition

Move these functions:
- `build_delivery_status` (line 1271)
- `_month_to_date_output` (line 1338)
- `_output_totals_by_date` (line 1350)
- `_active_output_dates` (line 1371)
- `_build_history_digest` (line 1392)
- `_build_factory_boss_summary` (line 1455)
- `_build_factory_leader_metrics` (line 1487)
- `_build_dashboard_leader_summary` (line 1523)
- `build_factory_dashboard` (line 1978)
- `build_workshop_dashboard` (line 2140)
- `build_statistics_dashboard` (line 2281)

#### Sub-module: `lane_builders.py` — Data lane construction

Move these functions:
- `_build_production_lane` (line 1572)
- `_build_energy_lane` (line 1598)
- `_lane_source_meta` (line 1610)
- `_build_exception_lane` (line 1631)
- `_build_runtime_source_lanes` (line 1673)
- `_build_runtime_trace` (line 1784)
- `_workshop_reporting_meta` (line 1900)
- `_build_workshop_reporting_status` (line 1917)

#### Proxy: `__init__.py`

```python
from app.services.report.report_generation import (
    generate_daily_reports,
    review_report,
    publish_report,
    finalize_report,
    run_daily_pipeline,
    resolve_report_delivery_payload,
    list_reports,
    get_report,
)
from app.services.report.dashboard_builder import (
    build_factory_dashboard,
    build_workshop_dashboard,
    build_statistics_dashboard,
    build_delivery_status,
)

__all__ = [
    "generate_daily_reports",
    "review_report",
    "publish_report",
    "finalize_report",
    "run_daily_pipeline",
    "resolve_report_delivery_payload",
    "list_reports",
    "get_report",
    "build_factory_dashboard",
    "build_workshop_dashboard",
    "build_statistics_dashboard",
    "build_delivery_status",
]
```

- [ ] **Step 1:** Create `backend/app/services/report/` directory with `_utils.py` containing shared constants and helpers
- [ ] **Step 2:** Create `report_generation.py` with report lifecycle functions, importing from `_utils`
- [ ] **Step 3:** Create `lane_builders.py` with data lane construction functions, importing from `_utils`
- [ ] **Step 4:** Create `dashboard_builder.py` with dashboard functions, importing from `_utils` and `lane_builders`
- [ ] **Step 5:** Create `__init__.py` proxy that re-exports all public names
- [ ] **Step 6:** Delete original `backend/app/services/report_service.py`
- [ ] **Step 7:** Verify: `cd backend && python -m pytest -q` — all tests pass
- [ ] **Step 8:** Commit: `refactor: split report_service.py into report/ package`

---

### Task 2: Split `mobile_report_service.py` (1755 lines) into `backend/app/services/mobile_report/`

**Files:**
- Create: `backend/app/services/mobile_report/__init__.py` (thin proxy)
- Create: `backend/app/services/mobile_report/_utils.py`
- Create: `backend/app/services/mobile_report/lifecycle.py`
- Create: `backend/app/services/mobile_report/shift_context.py`
- Create: `backend/app/services/mobile_report/summary.py`
- Remove: `backend/app/services/mobile_report_service.py`

#### Sub-module: `_utils.py` — Shared constants and helpers

Move module-level constants (lines 36-41): `AUTO_CONFIRMED_REPORT_STATUS`, `APPROVED_REPORT_STATUSES`, `SUBMITTED_STATUSES`, `LOCAL_TZ`, `PHOTO_ALLOWED_EXTENSIONS`, `PHOTO_MAX_BYTES`.

Move the `ShiftContext` dataclass (line 44).

Move these functions:
- `_to_float` (line 53)
- `_json_ready` (line 59)
- `_model_to_dict` (line 71)
- `_normalize_override_reason` (line 75)
- `_mobile_report_decision_status` (line 80)
- `_is_mobile_report_auto_confirmed` (line 93)
- `_build_agent_decision_snapshot` (line 97)
- `_ensure_mobile_write_scope` (line 156)
- `_ensure_mobile_override_for_locked_report` (line 166)
- `_round_value` (line 179)
- `_public_upload_url` (line 185)
- `_normalize_filename` (line 190)
- `_local_now` (line 201)
- `_month_range` (line 209)
- `_serialize_active_reminders` (line 352)
- `_active_reminders_for_context` (line 367)
- `_ownership_note` (line 392)
- `_same_month` (line 401)

#### Sub-module: `lifecycle.py` — Report CRUD

Move these functions:
- `_serialize_mobile_report` (line 518)
- `_sync_to_shift_production` (line 617)
- `_required_submit_fields` (line 676)
- `_normalize_mobile_report_payload` (line 712)
- `_find_mobile_report` (line 332)
- `calculate_mobile_report_metrics` (line 405)
- `_aggregate_monthly_totals` (line 437)
- `_target_and_compare_values` (line 476)
- `store_report_photo` (line 814)
- `upload_report_photo` (line 850)
- `get_report_detail` (line 1057)
- `save_or_submit_report` (line 1095)
- `list_report_history` (line 1246)
- `sync_mobile_status_from_review` (line 1293)

#### Sub-module: `shift_context.py` — Shift inference

Move these functions:
- `_shift_window_for_date` (line 218)
- `_resolve_workshop_team` (line 229)
- `_shift_candidates` (line 255)
- `_machine_shift_candidates` (line 267)
- `_pick_shift_by_time` (line 280)
- `_infer_current_shift` (line 288)
- `_build_current_shift_fallback` (line 728)
- `_resolve_entry_mode` (line 770)
- `_uses_shift_report_ownership` (line 780)
- `get_mobile_bootstrap` (line 784)
- `get_current_shift` (line 947)

#### Sub-module: `summary.py` — Aggregation

Move these functions:
- `_report_key` (line 1315)
- `_build_inventory_summary_bucket` (line 1319)
- `summarize_mobile_reporting` (line 1346)
- `summarize_mobile_inventory` (line 1426)
- `recent_mobile_exceptions` (line 1530)
- `count_linked_open_production_exceptions` (line 1570)
- `list_coil_entries` (line 1589)
- `_aggregate_coil_to_shift` (line 1631)
- `create_coil_entry` (line 1678)

#### Proxy: `__init__.py`

```python
from app.services.mobile_report.lifecycle import (
    save_or_submit_report,
    upload_report_photo,
    store_report_photo,
    get_report_detail,
    list_report_history,
    sync_mobile_status_from_review,
    calculate_mobile_report_metrics,
)
from app.services.mobile_report.shift_context import (
    get_current_shift,
    get_mobile_bootstrap,
)
from app.services.mobile_report.summary import (
    summarize_mobile_reporting,
    summarize_mobile_inventory,
    recent_mobile_exceptions,
    count_linked_open_production_exceptions,
    list_coil_entries,
    create_coil_entry,
)

__all__ = [
    "save_or_submit_report",
    "upload_report_photo",
    "store_report_photo",
    "get_report_detail",
    "list_report_history",
    "sync_mobile_status_from_review",
    "calculate_mobile_report_metrics",
    "get_current_shift",
    "get_mobile_bootstrap",
    "summarize_mobile_reporting",
    "summarize_mobile_inventory",
    "recent_mobile_exceptions",
    "count_linked_open_production_exceptions",
    "list_coil_entries",
    "create_coil_entry",
]
```

- [ ] **Step 1:** Create `backend/app/services/mobile_report/` directory with `_utils.py`
- [ ] **Step 2:** Create `shift_context.py` with shift inference functions
- [ ] **Step 3:** Create `lifecycle.py` with report CRUD functions
- [ ] **Step 4:** Create `summary.py` with aggregation functions
- [ ] **Step 5:** Create `__init__.py` proxy
- [ ] **Step 6:** Delete original `backend/app/services/mobile_report_service.py`
- [ ] **Step 7:** Verify: `cd backend && python -m pytest -q` — all tests pass
- [ ] **Step 8:** Commit: `refactor: split mobile_report_service.py into mobile_report/ package`

---

### Task 3: Split `work_order_service.py` (1451 lines) into `backend/app/services/work_order/`

**Files:**
- Create: `backend/app/services/work_order/__init__.py` (thin proxy)
- Create: `backend/app/services/work_order/_utils.py`
- Create: `backend/app/services/work_order/_access.py`
- Create: `backend/app/services/work_order/crud.py`
- Create: `backend/app/services/work_order/entry.py`
- Create: `backend/app/services/work_order/amendment.py`
- Remove: `backend/app/services/work_order_service.py`

#### Sub-module: `_utils.py` — Shared constants and helpers

Move module-level constants (lines 45-51): `TRACKING_CARD_PREFIX_RE`, `ENTRY_METADATA_FIELDS`, `JSON_PAYLOAD_FIELDS`, `ENTRY_LOCKED_STATUSES`, `ENTRY_METADATA_ROLE_ALLOWLIST`, `OWNER_ONLY_ENTRY_ROLES`, `logger`.

Move these functions:
- `_http_error` (line 54)
- `_to_float` (line 58)
- `_utcnow` (line 64)
- `_model_to_dict` (line 68)
- `_json_ready` (line 76)
- `_normalize_override_reason` (line 88)
- `_normalize_tracking_card_no` (line 93)
- `_entry_create_idempotency_scope` (line 100)
- `_entry_create_idempotency_fingerprint` (line 104)
- `parse_process_route_code` (line 109)
- `_lookup_mes_card_info` (line 117)
- `_apply_mes_card_info` (line 125)
- `_push_mes_completion_if_needed` (line 135)
- `_calculate_yield_rate` (line 154)
- `_coerce_column_value` (line 382)
- `_entry_creator_user_id` (line 339)

#### Sub-module: `_access.py` — Access control

Move these functions:
- `_ensure_workshop` (line 226)
- `_ensure_machine` (line 233)
- `_ensure_shift` (line 244)
- `_ensure_work_order` (line 253)
- `_ensure_entry` (line 260)
- `_ensure_amendment` (line 267)
- `_ensure_header_access` (line 274)
- `_ensure_entry_access` (line 294)
- `_ensure_write_target_scope` (line 304)
- `_ensure_machine_scope` (line 320)
- `_ensure_entry_write_access` (line 343)

#### Sub-module: `crud.py` — Work order lifecycle

Move these functions:
- `_apply_work_order_fields` (line 411)
- `_recompute_work_order_rollups` (line 481)
- `_serialize_work_order` (line 770)
- `create_work_order` (line 897)
- `update_work_order` (line 937)
- `list_work_orders` (line 970)
- `get_work_order_by_tracking_card` (line 1014)
- `list_entries_for_work_order` (line 1023)

#### Sub-module: `entry.py` — Entry management

Move these functions:
- `_apply_entry_fields` (line 422)
- `_entry_sort_key` (line 452)
- `_find_owner_only_entry` (line 460)
- `_resolve_entry_workshop_type` (line 523)
- `_resolve_entry_template_key` (line 533)
- `_filter_template_payload_values` (line 550)
- `_normalize_template_section_payload` (line 573)
- `_readonly_fields_by_target` (line 600)
- `_strip_readonly_payload_fields` (line 623)
- `_recalculate_readonly_derived_fields` (line 655)
- `_safe_decimal_compute` (line 710)
- `_serialize_entry` (line 736)
- `_build_entry_event_payload` (line 784)
- `_build_entry_saved_event_payload` (line 851)
- `build_previous_stage_output` (line 162)
- `split_entry_form_payload` (line 182)
- `mask_table_payload` (line 208)
- `filter_entry_payloads_for_scope` (line 216)
- `add_entry` (line 1037)
- `update_entry` (line 1207)
- `submit_entry` (line 1295)

#### Sub-module: `amendment.py` — Amendment workflow

Move these functions:
- `_ensure_amendment_approval_access` (line 375)
- `request_amendment` (line 1352)
- `approve_amendment` (line 1399)

#### Proxy: `__init__.py`

```python
from app.services.work_order.crud import (
    create_work_order,
    update_work_order,
    list_work_orders,
    get_work_order_by_tracking_card,
    list_entries_for_work_order,
)
from app.services.work_order.entry import (
    add_entry,
    update_entry,
    submit_entry,
    build_previous_stage_output,
    split_entry_form_payload,
    mask_table_payload,
    filter_entry_payloads_for_scope,
)
from app.services.work_order.amendment import (
    request_amendment,
    approve_amendment,
)
from app.services.work_order._utils import (
    parse_process_route_code,
)

__all__ = [
    "create_work_order",
    "update_work_order",
    "list_work_orders",
    "get_work_order_by_tracking_card",
    "list_entries_for_work_order",
    "add_entry",
    "update_entry",
    "submit_entry",
    "build_previous_stage_output",
    "split_entry_form_payload",
    "mask_table_payload",
    "filter_entry_payloads_for_scope",
    "request_amendment",
    "approve_amendment",
    "parse_process_route_code",
]
```

- [ ] **Step 1:** Create `backend/app/services/work_order/` directory with `_utils.py`
- [ ] **Step 2:** Create `_access.py` with access control functions
- [ ] **Step 3:** Create `entry.py` with entry management functions
- [ ] **Step 4:** Create `crud.py` with work order lifecycle functions
- [ ] **Step 5:** Create `amendment.py` with amendment workflow functions
- [ ] **Step 6:** Create `__init__.py` proxy
- [ ] **Step 7:** Delete original `backend/app/services/work_order_service.py`
- [ ] **Step 8:** Verify: `cd backend && python -m pytest -q` — all tests pass
- [ ] **Step 9:** Commit: `refactor: split work_order_service.py into work_order/ package`

---

### Task 4: Split `workshop_templates.py` (1216 lines) into `backend/app/core/templates/`

**Files:**
- Create: `backend/app/core/templates/__init__.py` (thin proxy)
- Create: `backend/app/core/templates/resolver.py`
- Create: `backend/app/core/templates/loader.py`
- Create: `backend/app/core/templates/permissions.py`
- Remove: `backend/app/core/workshop_templates.py`

Note: All module-level constants (`WORK_ORDER_FIELD_NAMES`, `WORK_ORDER_ENTRY_FIELD_NAMES`, `NUMERIC_FIELD_NAMES`, `TIME_FIELD_NAMES`, `WORKSHOP_TYPE_BY_WORKSHOP_CODE`, `WORKSHOP_TYPE_ALIASES`, `ENERGY_OWNER_FIELDS`, `DEFAULT_WORKSHOP_TEMPLATES`, `WORKSHOP_TEMPLATES`) stay in `__init__.py` since they are imported directly by other modules (e.g., `from app.core.workshop_templates import WORK_ORDER_ENTRY_FIELD_NAMES`).

#### Sub-module: `resolver.py` — Key/type resolution

Move these functions:
- `normalize_workshop_type` (line 939)
- `normalize_template_key` (line 946)
- `resolve_template_key` (line 962)
- `resolve_workshop_type` (line 1122)

These depend on constants `WORKSHOP_TYPE_BY_WORKSHOP_CODE` and `WORKSHOP_TYPE_ALIASES` — import them from the parent `__init__`.

#### Sub-module: `loader.py` — Loading and retrieval

Move these functions:
- `_load_template_definition_from_config` (line 1037)
- `_load_default_template_definition` (line 1051)
- `get_workshop_template_definition` (line 1065)
- `normalize_template_definition_payload` (line 1101)
- `_normalize_definition_field` (line 990)
- `_normalize_definition_section` (line 1004)
- `_split_supplemental_sections` (line 1012)
- `_merge_supplemental_sections` (line 1026)

These depend on `DEFAULT_WORKSHOP_TEMPLATES` — import from parent `__init__`.

#### Sub-module: `permissions.py` — Field permissions and template rendering

Move these functions:
- `_listify` (line 833)
- `_field_type` (line 841)
- `_field_target` (line 851)
- `_default_write_roles` (line 861)
- `_default_read_roles` (line 873)
- `_is_readable` (line 883)
- `_is_writable` (line 895)
- `_normalize_field` (line 907)
- `get_workshop_template` (line 1172) — the main template rendering function that uses all permission helpers

These depend on constants `WORK_ORDER_FIELD_NAMES`, `WORK_ORDER_ENTRY_FIELD_NAMES`, `NUMERIC_FIELD_NAMES`, `TIME_FIELD_NAMES` — import from parent `__init__`.

#### Proxy: `__init__.py`

```python
# Constants stay here (imported directly by other modules)
WORK_ORDER_FIELD_NAMES = { ... }
WORK_ORDER_ENTRY_FIELD_NAMES = { ... }
NUMERIC_FIELD_NAMES = { ... }
TIME_FIELD_NAMES = { ... }
WORKSHOP_TYPE_BY_WORKSHOP_CODE = { ... }
WORKSHOP_TYPE_ALIASES = { ... }
ENERGY_OWNER_FIELDS = [ ... ]
DEFAULT_WORKSHOP_TEMPLATES = { ... }
WORKSHOP_TEMPLATES = DEFAULT_WORKSHOP_TEMPLATES

# Re-export functions
from app.core.templates.resolver import (
    resolve_template_key,
    resolve_workshop_type,
    normalize_workshop_type,
    normalize_template_key,
)
from app.core.templates.loader import (
    get_workshop_template_definition,
    normalize_template_definition_payload,
)
from app.core.templates.permissions import (
    get_workshop_template,
)

__all__ = [
    "WORK_ORDER_FIELD_NAMES",
    "WORK_ORDER_ENTRY_FIELD_NAMES",
    "NUMERIC_FIELD_NAMES",
    "TIME_FIELD_NAMES",
    "WORKSHOP_TYPE_BY_WORKSHOP_CODE",
    "WORKSHOP_TYPE_ALIASES",
    "ENERGY_OWNER_FIELDS",
    "DEFAULT_WORKSHOP_TEMPLATES",
    "WORKSHOP_TEMPLATES",
    "resolve_template_key",
    "resolve_workshop_type",
    "normalize_workshop_type",
    "normalize_template_key",
    "get_workshop_template_definition",
    "normalize_template_definition_payload",
    "get_workshop_template",
]
```

**Important:** The proxy `__init__.py` must live at `backend/app/core/templates/__init__.py`, but existing code imports from `app.core.workshop_templates`. To preserve the import path, add a compatibility shim at `backend/app/core/workshop_templates.py` that re-exports everything from `app.core.templates`:

```python
from app.core.templates import *  # noqa: F401,F403
from app.core.templates import __all__  # noqa: F401
```

- [ ] **Step 1:** Create `backend/app/core/templates/` directory with `__init__.py` containing all constants and re-exports
- [ ] **Step 2:** Create `resolver.py` with key/type resolution functions
- [ ] **Step 3:** Create `loader.py` with template loading functions
- [ ] **Step 4:** Create `permissions.py` with field permission functions and `get_workshop_template`
- [ ] **Step 5:** Replace `backend/app/core/workshop_templates.py` with thin compatibility shim
- [ ] **Step 6:** Verify: `cd backend && python -m pytest -q` — all tests pass
- [ ] **Step 7:** Commit: `refactor: split workshop_templates.py into core/templates/ package`

---

### Task 5: Final verification

- [ ] **Step 1:** Run full test suite: `cd backend && python -m pytest -q` — confirm all 502 tests pass
- [ ] **Step 2:** Verify no imports changed in test files: `git diff --name-only | grep test` should show zero test files
- [ ] **Step 3:** Count lines in new sub-modules vs originals — confirm total is comparable (no code lost, no code duplicated)
- [ ] **Step 4:** Verify each original import path still works:
  - `from app.services import report_service` → works
  - `from app.services import mobile_report_service` → works
  - `from app.services import work_order_service` → works
  - `from app.core.workshop_templates import resolve_workshop_type` → works
  - `from app.core.workshop_templates import WORK_ORDER_ENTRY_FIELD_NAMES` → works
