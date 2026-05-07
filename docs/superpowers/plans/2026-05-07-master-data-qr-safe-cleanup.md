# Master Data QR-Safe Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean workshop, equipment, alias, and mobile user master data so MES-projected workshop labels resolve into existing factory structure without breaking any printed QR code or existing QR login path; expose a clear 分厂/车间/机列/工艺业务 matrix for management and later MES field alignment.

**Architecture:** Keep `Equipment.qr_code` as the stable runtime identity. Add MES workshop aliases through `MasterCodeAlias`, preserve existing QR values during real master-data seeding, and resolve MES workshop/machine labels through alias lookup when building live aggregation. Add ZXTF online annealing as a canonical workshop/equipment seed because current MES data and existing QR records already reference it. Keep factory-area/process responsibility as a read-only business dictionary first, avoiding a database migration until 1650/1850, new-plant online, park online, and JZ2 machine duties are confirmed.

**Tech Stack:** Python, SQLAlchemy ORM, pytest, existing FastAPI routers/services.

---

### Task 1: Lock QR Preservation and MES Alias Seeding

**Files:**
- Modify: `backend/tests/test_real_master_data.py`
- Modify: `backend/app/services/real_master_data.py`

- [x] **Step 1: Write failing tests**

Add tests proving:
- `seed_real_master_data()` preserves an existing non-empty `Equipment.qr_code`.
- MES workshop labels such as `2050车间`, `热轧`, `新厂在线车间`, and `园区在线车间` seed into `MasterCodeAlias`.
- ZXTF is present as `online annealing` master data with four running machine lines and existing virtual QR rows still reusable.

- [x] **Step 2: Verify red**

Run:

```powershell
python -m pytest backend/tests/test_real_master_data.py::test_seed_real_master_data_preserves_existing_qr_codes_and_seeds_mes_aliases -q
```

Expected: FAIL because alias rows and QR preservation are not implemented yet.

- [x] **Step 3: Implement minimal master data changes**

Update `backend/app/services/real_master_data.py`:
- import `MasterCodeAlias`;
- add `ZXTF` to `WORKSHOPS`;
- add `ZXTF-1`..`ZXTF-4` physical equipment rows;
- add `MES_WORKSHOP_ALIASES`;
- add idempotent `seed_mes_master_aliases(db)`;
- preserve non-empty `Equipment.qr_code` in seed/update paths.

- [x] **Step 4: Verify green**

Run:

```powershell
python -m pytest backend/tests/test_real_master_data.py -q
```

Expected: PASS.

### Task 2: Make Live MES Projection Use Master Aliases

**Files:**
- Modify: `backend/tests/test_realtime_service.py`
- Modify: `backend/app/services/realtime_service.py`

- [x] **Step 1: Write failing test**

Add a test where `MesCoilSnapshot.workshop_code='2050车间'` and a `MasterCodeAlias` maps it to `LZ2050`. Assert `build_live_aggregation()` places the MES row under the `LZ2050` workshop and reports `data_source='mes_projection'` or `mixed` as appropriate.

- [x] **Step 2: Verify red**

Run:

```powershell
python -m pytest backend/tests/test_realtime_service.py::test_build_live_aggregation_resolves_mes_workshop_aliases -q
```

Expected: FAIL because `_load_mes_snapshot_rows()` currently maps only exact workshop codes.

- [x] **Step 3: Implement alias resolution**

Update `_load_mes_snapshot_rows()` to resolve `workshop_code` and non-empty `machine_code` through `master_service.resolve_canonical_code(..., source_type='mes_mvc')` before looking up IDs.

- [x] **Step 4: Verify green**

Run:

```powershell
python -m pytest backend/tests/test_realtime_service.py::test_build_live_aggregation_resolves_mes_workshop_aliases backend/tests/test_realtime_service.py::test_build_live_aggregation_blends_mes_projection_with_bound_fill_entries -q
```

Expected: PASS.

### Task 3: QR and Scan Regression Gate

**Files:**
- Modify if needed: `backend/tests/test_qr_login.py`
- Modify if needed: `backend/tests/test_scan_lookup_service.py`

- [x] **Step 1: Run QR-focused tests**

Run:

```powershell
python -m pytest backend/tests/test_qr_login.py backend/tests/test_scan_lookup_service.py backend/tests/test_mobile_scan_lookup_route.py -q
```

Expected: PASS; existing QR login and scan lookup are unchanged.

- [x] **Step 2: Run master/realtime focused tests**

Run:

```powershell
python -m pytest backend/tests/test_real_master_data.py backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py -q
```

Expected: PASS.

- [x] **Step 3: Run full backend tests**

Run:

```powershell
python -m pytest backend/tests -q
```

Expected: PASS.

### Task 4: Deployment Evidence

**Files:**
- Modify: `docs/deploy/current-state.md`
- Modify: this plan file

- [x] **Step 1: Update docs with evidence**

Record:
- QR preservation behavior;
- alias rows seeded;
- ZXTF canonical master data;
- production verification commands and key output.

- [x] **Step 2: Commit and deploy**

Commit after tests pass, push `main`, deploy with:

```powershell
ssh -o BatchMode=yes root@8.140.218.13 "cd /srv/aluminum-bypass && ./scripts/deploy_systemd_host.sh --pull http://8.140.218.13"
```

- [x] **Step 3: Production verify**

Verify:
- `/readyz`;
- `seed_real_master_data()` idempotence;
- `virtual_role_qr_active=96` and `bound_role_qr=96` remain unchanged or increase only by intentional ZXTF physical additions;
- `MasterCodeAlias` resolves MES workshop labels.

### Task 5: Factory/Workshop/Machine Process Business Map

**Files:**
- Modify: `backend/tests/test_real_master_data.py`
- Modify: `backend/tests/test_master_pagination.py`
- Modify: `backend/app/services/real_master_data.py`
- Modify: `backend/app/routers/master.py`
- Create: `docs/process-business-map.md`

- [x] **Step 1: Write failing tests**

Add tests for:
- `build_process_business_hierarchy()` returning 分厂/车间/机列/工艺职责;
- no seeded physical machine having an empty `process_business`;
- manager API `GET /api/v1/master/process-business-map`.

- [x] **Step 2: Verify red**

Run:

```powershell
python -m pytest backend/tests/test_real_master_data.py::test_process_business_hierarchy_covers_factory_workshop_machine_roles -q
python -m pytest backend/tests/test_master_pagination.py::test_process_business_map_route_returns_factory_workshop_machine_roles -q
```

Expected and observed before implementation:
- first test failed with `ImportError: cannot import name 'build_process_business_hierarchy'`;
- second test failed with `404 != 200`.

- [x] **Step 3: Implement read-only business map**

Add constants and `build_process_business_hierarchy()` to `backend/app/services/real_master_data.py`; expose the same payload through `backend/app/routers/master.py`.

- [x] **Step 4: Verify green**

Run:

```powershell
python -m pytest backend/tests/test_real_master_data.py::test_process_business_hierarchy_covers_factory_workshop_machine_roles -q
python -m pytest backend/tests/test_master_pagination.py::test_process_business_map_route_returns_factory_workshop_machine_roles -q
```

Observed: both passed.
