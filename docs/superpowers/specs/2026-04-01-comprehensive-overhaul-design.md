# Aluminum Bypass — Comprehensive Overhaul Design

**Date:** 2026-04-01
**Scope:** Bug fixes + UX overhaul to bring to production-deployable state
**Authority:** Full — user-delegated, no further approval gates required

---

## Out of Scope (Preserved As-Is)

- One-code-per-device machine login flow (QR + PIN)
- MES adapter endpoints (`/api/v1/mes/*`)
- DingTalk bootstrap and identity hooks
- Data import flow (ShiftCenter import accepted as reasonable)
- Database schema (no migrations)

---

## User Groups & Their Primary Pain Points

| Group | Role | Primary Flow | Pain Point |
|-------|------|--------------|------------|
| Machine operator | `shift_leader` | Mobile → fill form → submit | Working for ZD-1 but draft key prefix broken |
| Admin / tester | `admin` | Everything | **0 editable fields on mobile form** |
| Factory director | `manager` / `admin` | Factory dashboard | Can't tell at a glance who reported and who didn't |
| Workshop director | `manager` | Workshop dashboard | Zero error handling, raw numeric workshop ID input |
| Reviewer | `reviewer` | ShiftCenter | Error on load is silent |

---

## Change Set — Grouped by Area

---

### Area 1 — Backend: Permission Model Fix

**File:** `backend/app/core/workshop_templates.py`
**Function:** `get_workshop_template()`

**Problem:** `admin`, `manager`, and `factory_director` roles receive 0 writable entry fields because
`_is_writable()` maps these roles against field-level write lists that only contain `shift_leader`.
The mobile form renders empty for any power user.

**Fix:** At the top of `get_workshop_template()`, if `user_role` normalizes to `admin` or `manager`,
bypass per-field write filtering — treat all enabled template fields as writable.
This is correct: power users need full form access for testing and override scenarios.

```
POWER_ROLES = {'admin', 'manager', 'factory_director'}
if normalize_role(user_role) in POWER_ROLES or user_role in POWER_ROLES:
    # all enabled fields → writable, skip role gate
```

---

### Area 2 — Frontend: Mobile Form Fixes (DynamicEntryForm.vue)

#### 2a. Mojibake strings (lines 553, 589)
Two Chinese strings were saved with wrong encoding and became garbled:
- `'澶囨敞'` → `'备注'`  (operator notes label fallback)
- `'鍏朵粬鐢ㄦ埛'` → `'其他用户'`  (read-only banner creator name fallback)

Fix: replace with correct UTF-8 strings.

#### 2b. Silent failure on template 404 (loadPage, line 1534)
`loadPage()` has no `catch`. If `fetchWorkshopTemplate()` returns 404 (e.g., unconfigured workshop),
the try-block exits silently, `template.value` stays null, and all `v-if="template"` cards collapse.
User sees a blank shell with a loading spinner that never resolves.

Fix: add `catch` that sets an `error` ref and renders an `el-result` error state with a "返回入口" button.

#### 2c. Draft key prefix matching (useLocalDraft.js)
`buildDynamicDraftKey` was extended to include `machineId` (6th segment):
`draft:{workshopId}:{shiftId}:{businessDate}:{machineId}:{trackingCardNo}`

But `findRestorableDraftKey` builds the prefix by passing `trackingCardNo: ''` and no `machineId`,
which generates `draft:{workshopId}:{shiftId}:{businessDate}::` (double colon) — matching nothing.

Fix: update `findRestorableDraftKey` to also set `machineId: ''` when building the "any tracking card" prefix,
generating `draft:{workshopId}:{shiftId}:{businessDate}::` consistently.
Update `offlineResilience.test.js` to pass `machineId` in all test scope objects.

---

### Area 3 — Factory Dashboard (FactoryDirector.vue + backend)

#### 3a. Rename title
"未来版生产驾驶舱" → "生产驾驶舱" (remove the "future version" qualifier — it's deployed now)

#### 3b. Per-workshop reporting status grid
The single biggest UX gap: the factory director cannot see at a glance who has and hasn't submitted.

**New panel: "今日上报状态"** — placed immediately after the stat grid, before the production lane tables.

Visually: a responsive card grid, one card per active workshop, showing:
- Workshop name
- Current shift (A/B/C)
- Status chip: `已上报` (green) / `填报中` (blue, has draft) / `未上报` (yellow) / `迟报` (red)
- Output weight if submitted

**Backend change:** extend `build_factory_dashboard()` in `report_service.py` to include
`workshop_reporting_status: list` — a per-workshop breakdown derived from the mobile reports
table joined with shift configs and workshops. Each item:
```json
{
  "workshop_id": 15,
  "workshop_name": "铸锭车间",
  "workshop_code": "ZD",
  "shift_code": "A",
  "shift_name": "白班",
  "report_status": "submitted",   // unreported | draft | submitted | reviewed | late
  "output_weight": 1175.0
}
```
Query: for `target_date`, join `mobile_reports` → `workshops` → active `shift_configs`.
Mark `late` if `report_status == 'unreported'` and current time is past the shift's end time.

#### 3c. Error handling
Add `try/catch/finally` to `load()` with `ElMessage.error('数据加载失败，请稍后重试')`.

#### 3d. Production lane table: add 上报状态 column
In the existing production lane table, add a `上报状态` column sourced from
`workshop_reporting_status` matched by `workshop_id`. This removes the need for users
to cross-reference two sections.

---

### Area 4 — Workshop Dashboard (WorkshopDirector.vue)

#### 4a. Replace raw ID input with workshop dropdown
The current `<el-input-number v-model="workshopId">` requires the director to know their
workshop's database ID. Replace with `<el-select>` populated from `fetchWorkshops()`.
Auto-select the first workshop on mount. The workshop director always works within one workshop.

#### 4b. Add loading states
All stat cards and table panels currently render with no loading indicator.
Add a single `loading` ref and `v-loading="loading"` on each panel.

#### 4c. Add error handling
Wrap `load()` in `try/catch/finally`. On error: `ElMessage.error('加载失败')`.

#### 4d. Add watchers
Add `watch([targetDate, workshopId], load)` so the dashboard refreshes automatically
when the director changes the date or switches workshops.

---

### Area 5 — Global Error Handling Standardisation

Each of these components has async `load()` / `onMounted()` with no `catch`.
The fix is the same pattern in each: `try { … } catch { ElMessage.error('加载失败') } finally { loading.value = false }`.

| File | Function | Fix |
|------|----------|-----|
| `ShiftCenter.vue` | `load()` + import handler | try/catch/finally + file size guard |
| `UserManagement.vue` | `onMounted` initializer | try/catch/finally |
| `Equipment.vue` | QR watch, file download | try/catch in watch + download |
| `MobileEntry.vue` | template fetch inner block | surface error to user |

---

### Area 6 — WorkshopTemplateConfig.vue: Role Visibility Hint

After the Area 1 backend fix, admin can test the mobile form. But the admin template editor
shows all fields without indicating which roles will see them in the mobile form.

Add a small info note beneath the section headers:
> 核心原始值：班长（shift_leader）可填写；管理员可查看所有字段。

This is a static hint, not dynamic — one line of text per section, no API call needed.

---

## Testing Requirements

After implementation, these must all pass before the system is considered deployable:

1. **Admin mobile form** — admin logs into `/mobile`, goes to report form, sees all entry fields editable (≥ 1 field).
2. **Draft key restore** — ZD-1 saves a draft, navigates away, returns — draft is offered for restore.
3. **Template 404 error state** — navigate to `/mobile/report/2026-04-01/1` as a user with no workshop_type — see an error card, not a blank page.
4. **Factory dashboard workshop grid** — shows at least one workshop card with a status chip.
5. **Workshop dashboard** — select a workshop from dropdown, data loads; change date, data refreshes.
6. **WorkshopDirector error** — simulate API failure; expect error toast, not silent "-" values.
7. **Existing e2e suite** — all 5 Playwright tests continue to pass.
8. **Unit tests** — all 8 node:test tests pass (including fixed offlineResilience tests).

---

## Implementation Order

1. Backend permission fix (Area 1) — unblocks all admin testing
2. Mobile form fixes (Area 2) — fixes the primary user flow
3. Factory dashboard (Area 3) — most visible UX improvement
4. Workshop dashboard (Area 4) — straightforward
5. Global error handling (Area 5) — systematic, low risk
6. Template editor hint (Area 6) — cosmetic, last

---

## What Does NOT Change

- Auth flow, token storage, QR login
- All MES and DingTalk routes and service stubs
- Mobile data isolation (workshop + team + owner_user_id)
- Shift engine, reconciliation, quality gate flows
- Report publish/export flows
- Data import
