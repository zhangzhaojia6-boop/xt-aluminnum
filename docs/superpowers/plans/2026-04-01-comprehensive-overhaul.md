# Comprehensive Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 areas of bugs and UX deficiencies to bring the aluminum bypass system to a production-deployable state.

**Architecture:** Backend fixes (Python/FastAPI) are independent of frontend fixes (Vue 3). Tasks are ordered by dependency: backend permission fix first (unblocks admin testing), then mobile form, then dashboards, then cleanup.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (backend), Vue 3 + Element Plus + Pinia (frontend), node:test (unit tests), Playwright (e2e tests)

---

## File Map

| File | Change |
|------|--------|
| `backend/app/core/workshop_templates.py` | Add `_POWER_ROLES` bypass in `get_workshop_template()` |
| `frontend/src/views/mobile/DynamicEntryForm.vue` | Fix 2 mojibake strings + add `loadPage` error handling |
| `frontend/src/composables/useLocalDraft.js` | Fix `findRestorableDraftKey` prefix (add `machineId: ''`) |
| `frontend/tests/offlineResilience.test.js` | Add `machineId` to all test scope objects, update expected keys |
| `backend/app/services/report_service.py` | Add `_build_workshop_reporting_status()`, include in `build_factory_dashboard()` |
| `frontend/src/views/dashboard/FactoryDirector.vue` | Rename title, add workshop status grid panel, add catch to `load()` |
| `frontend/src/views/dashboard/WorkshopDirector.vue` | Replace input-number with workshop select, add loading, catch, watchers |
| `frontend/src/views/shift/ShiftCenter.vue` | Add try/catch/finally to `load()` and `loadWorkshops()` |
| `frontend/src/views/master/UserManagement.vue` | Add try/catch/finally to `onMounted` initializer |
| `frontend/src/views/master/Equipment.vue` | Add try/catch/finally to `loadMasterData()` + `load()` |
| `frontend/src/views/master/WorkshopTemplateConfig.vue` | Add role visibility hint beneath section headers |

---

## Task 1: Backend — Power-user permission bypass

**Files:**
- Modify: `backend/app/core/workshop_templates.py:541-576`

- [ ] **Step 1: Write the failing test**

Create file `backend/tests/test_workshop_template_power_roles.py`:

```python
import pytest
from app.core.workshop_templates import get_workshop_template


def test_admin_gets_all_entry_fields_editable():
    result = get_workshop_template('casting', user_role='admin')
    assert result['entry_fields'], "admin should receive at least one entry field"
    for field in result['entry_fields']:
        assert field['editable'] is True, f"field {field['name']} should be editable for admin"


def test_manager_gets_all_entry_fields_editable():
    result = get_workshop_template('casting', user_role='manager')
    assert result['entry_fields'], "manager should receive at least one entry field"
    for field in result['entry_fields']:
        assert field['editable'] is True, f"field {field['name']} should be editable for manager"


def test_shift_leader_gets_entry_fields_editable():
    result = get_workshop_template('casting', user_role='shift_leader')
    assert result['entry_fields'], "shift_leader should receive entry fields"


def test_viewer_gets_no_editable_entry_fields():
    result = get_workshop_template('casting', user_role='viewer')
    editable = [f for f in result['entry_fields'] if f.get('editable')]
    assert not editable, "viewer should have no editable entry fields"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec -T backend bash -c "cd /app && python -m pytest tests/test_workshop_template_power_roles.py -v"
```

Expected: `test_admin_gets_all_entry_fields_editable` FAIL (admin gets 0 entry fields)

- [ ] **Step 3: Add `_POWER_ROLES` constant and bypass in `get_workshop_template()`**

In `backend/app/core/workshop_templates.py`, find the line `_POWER_ROLES` doesn't exist yet. Add it above `get_workshop_template()` (around line 540), then modify the function body:

Replace the existing `get_workshop_template` function (lines 541–576):

```python
_POWER_ROLES = frozenset({'admin', 'manager', 'factory_director'})


def get_workshop_template(workshop_type: str, *, user_role: str, db: Session | None = None) -> dict[str, Any]:
    template = get_workshop_template_definition(workshop_type, db=db)

    effective_role = normalize_role(user_role) or user_role
    is_power_user = effective_role in _POWER_ROLES or user_role in _POWER_ROLES

    readonly_fields: list[dict[str, Any]] = []
    result = {
        'template_key': template['template_key'],
        'workshop_type': template['workshop_type'],
        'display_name': template['display_name'],
        'tempo': template['tempo'],
        'supports_ocr': bool(template.get('supports_ocr', False)),
        'entry_fields': [],
        'extra_fields': [],
        'qc_fields': [],
        'readonly_fields': readonly_fields,
    }

    for section_name in ['entry_fields', 'extra_fields', 'qc_fields']:
        for field in template.get(section_name, []):
            if not field.get('enabled', True):
                continue
            normalized, writable, readable = _normalize_field(section_name, field, user_role)
            normalized['enabled'] = True
            if is_power_user:
                normalized['editable'] = True
                normalized['readonly'] = False
                result[section_name].append(normalized)
            elif writable:
                result[section_name].append(normalized)
            elif readable:
                readonly_fields.append(normalized)

    for field in template.get('readonly_fields', []):
        if not field.get('enabled', True):
            continue
        normalized, _writable, readable = _normalize_field('readonly_fields', field, user_role, force_readonly=True)
        normalized['enabled'] = True
        if readable:
            readonly_fields.append(normalized)

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec -T backend bash -c "cd /app && python -m pytest tests/test_workshop_template_power_roles.py -v"
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/workshop_templates.py backend/tests/test_workshop_template_power_roles.py
git commit -m "fix: admin and manager roles now receive all entry fields as editable in mobile form"
```

---

## Task 2: Mobile form — Fix mojibake strings

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue:553,589`

- [ ] **Step 1: Fix the two garbled UTF-8 strings**

In `DynamicEntryForm.vue` line 553, find:
```javascript
    label: field.name === 'operator_notes' ? '澶囨敞' : (field.label || field.name),
```
Replace with:
```javascript
    label: field.name === 'operator_notes' ? '备注' : (field.label || field.name),
```

In `DynamicEntryForm.vue` line 589, find:
```javascript
  const creatorName = currentEntry.value?.created_by_user_name || '鍏朵粬鐢ㄦ埛'
  return `姝ゆ潯鐩敱 ${creatorName} 鍒涘缓锛屾偍浠呭彲鏌ョ湅`
```
Replace with:
```javascript
  const creatorName = currentEntry.value?.created_by_user_name || '其他用户'
  return `此条目由 ${creatorName} 创建，您仅可查看`
```

- [ ] **Step 2: Verify the strings render correctly**

Open browser at `https://localhost/mobile`, log in as ZD-1 / 104833, navigate to the report form. Confirm no garbled characters appear in the operator notes label or in the read-only creator banner.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "fix: replace mojibake strings with correct UTF-8 Chinese in DynamicEntryForm"
```

---

## Task 3: Mobile form — Add error handling to `loadPage()`

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

- [ ] **Step 1: Add `loadError` ref and error UI to the template**

At the top of the `<template>` section in `DynamicEntryForm.vue`, after the opening `<div class="mobile-shell" ...>` tag (line 2), add an error state block that renders when `loadError` is set. Add it before the `<div class="mobile-top">` block:

```html
    <el-result
      v-if="loadError"
      icon="error"
      :title="loadError"
      sub-title="请检查网络连接后重试，或联系管理员。"
    >
      <template #extra>
        <el-button type="primary" @click="goEntry">返回入口</el-button>
      </template>
    </el-result>

    <template v-else>
```

Then close the `<template v-else>` at the end of the template, just before `</div>` (the last closing tag before `</template>`).

- [ ] **Step 2: Add `loadError` ref in the script section**

Find the block of `ref()` declarations near the top of `<script setup>` and add:
```javascript
const loadError = ref(null)
```

- [ ] **Step 3: Add catch to `loadPage()`**

Find the existing `loadPage()` function (line ~1534). The current structure is:
```javascript
async function loadPage() {
  loading.value = true
  try {
    // ...
  } finally {
    loading.value = false
  }
}
```

Replace with:
```javascript
async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    const shiftPayload = await fetchCurrentShift()
    Object.assign(currentShift, shiftPayload)
    formState.business_date = String(route.params.businessDate || shiftPayload.business_date || '')
    formState.shift_id = Number(route.params.shiftId || shiftPayload.shift_id || 0) || null
    formState.machine_id = shiftPayload.machine_id || null

    const templateKey = shiftPayload.workshop_code || shiftPayload.workshop_type
    if (!templateKey) {
      loadError.value = '未找到工序模板，请联系管理员配置车间模板。'
      return
    }

    const [templatePayload, equipmentPayload] = await Promise.all([
      fetchWorkshopTemplate(templateKey),
      fetchEquipment({ workshop_id: shiftPayload.workshop_id })
    ])
    template.value = templatePayload
    const activeEquipment = (equipmentPayload || []).filter((item) => item.is_active !== false)
    equipmentOptions.value = shiftPayload.is_machine_bound && shiftPayload.machine_id
      ? activeEquipment.filter((item) => Number(item.id) === Number(shiftPayload.machine_id))
      : activeEquipment
    initializeTemplateForm()
    loadOcrFromStorage()
    checkForRestorableDraft()
  } catch (err) {
    const status = err?.response?.status
    if (status === 404) {
      loadError.value = '未找到对应的工序模板，请联系管理员配置车间模板。'
    } else {
      loadError.value = '加载填报页面失败，请刷新重试。'
    }
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 4: Verify error state renders**

Navigate to `https://localhost/mobile/report/2026-04-01/1` as a user with no workshop_type configured. Expect to see the `el-result` error card with a "返回入口" button instead of a blank loading spinner.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "fix: add error state to DynamicEntryForm loadPage so template 404 shows user-friendly message"
```

---

## Task 4: Fix draft key test failures

**Files:**
- Modify: `frontend/tests/offlineResilience.test.js`
- Modify: `frontend/src/composables/useLocalDraft.js`

**Context:** `buildDynamicDraftKey` now generates 6-segment keys:
`draft:{workshopId}:{shiftId}:{businessDate}:{machineId}:{trackingCardNo}`

The tests still use old 5-segment keys and scope objects without `machineId`. Also, `findRestorableDraftKey` builds prefix with `machineId` missing when passed `trackingCardNo: ''`, resulting in double-colon mismatch.

- [ ] **Step 1: Run the existing tests to confirm they fail**

```bash
cd frontend && node --test tests/offlineResilience.test.js
```

Expected: 2 test failures related to key format mismatch.

- [ ] **Step 2: Fix `findRestorableDraftKey` prefix in `useLocalDraft.js`**

In `frontend/src/composables/useLocalDraft.js`, find line 56:
```javascript
  const prefix = buildDynamicDraftKey({ ...scope, trackingCardNo: '' })
```
Replace with:
```javascript
  const prefix = buildDynamicDraftKey({ ...scope, trackingCardNo: '', machineId: scope.machineId ?? '' })
```

- [ ] **Step 3: Update `offlineResilience.test.js` with 6-segment keys**

Replace the entire contents of `frontend/tests/offlineResilience.test.js`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDynamicDraftKey,
  findRestorableDraftKey
} from '../src/composables/useLocalDraft.js'
import { isRetryableNetworkError } from '../src/composables/useRetryQueue.js'

test('buildDynamicDraftKey includes workshop shift date machineId and tracking card', () => {
  assert.equal(
    buildDynamicDraftKey({
      workshopId: 2,
      shiftId: 3,
      businessDate: '2026-03-28',
      machineId: 37,
      trackingCardNo: 'ra260001'
    }),
    'draft:2:3:2026-03-28:37:RA260001'
  )
})

test('findRestorableDraftKey prefers exact match then latest prefix match', () => {
  const exact = findRestorableDraftKey(
    [
      { key: 'draft:2:3:2026-03-28:37:RA260001', savedAt: '2026-03-28T08:00:00.000Z' },
      { key: 'draft:2:3:2026-03-28:37:RA260002', savedAt: '2026-03-28T08:05:00.000Z' }
    ],
    {
      workshopId: 2,
      shiftId: 3,
      businessDate: '2026-03-28',
      machineId: 37,
      trackingCardNo: 'RA260001'
    }
  )
  const latestPrefix = findRestorableDraftKey(
    [
      { key: 'draft:2:3:2026-03-28:37:RA260001', savedAt: '2026-03-28T08:00:00.000Z' },
      { key: 'draft:2:3:2026-03-28:37:RA260002', savedAt: '2026-03-28T08:05:00.000Z' }
    ],
    {
      workshopId: 2,
      shiftId: 3,
      businessDate: '2026-03-28',
      machineId: 37,
      trackingCardNo: ''
    }
  )

  assert.equal(exact, 'draft:2:3:2026-03-28:37:RA260001')
  assert.equal(latestPrefix, 'draft:2:3:2026-03-28:37:RA260002')
})

test('isRetryableNetworkError only treats transport failures as retryable', () => {
  assert.equal(isRetryableNetworkError({ code: 'ERR_NETWORK' }), true)
  assert.equal(isRetryableNetworkError({ message: 'Network Error' }), true)
  assert.equal(isRetryableNetworkError({ response: { status: 400 } }), false)
  assert.equal(isRetryableNetworkError({ response: { status: 500 } }), false)
})
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd frontend && node --test tests/offlineResilience.test.js
```

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useLocalDraft.js frontend/tests/offlineResilience.test.js
git commit -m "fix: update draft key tests and findRestorableDraftKey prefix to use 6-segment key format with machineId"
```

---

## Task 5: Backend — Add per-workshop reporting status to factory dashboard

**Files:**
- Modify: `backend/app/services/report_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_workshop_reporting_status.py`:

```python
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from app.services.report_service import _build_workshop_reporting_status


def _make_mock_db():
    db = MagicMock()
    return db


def test_build_workshop_reporting_status_returns_list():
    db = _make_mock_db()
    # Mock the query chain to return empty list
    db.query.return_value.join.return_value.filter.return_value.all.return_value = []
    result = _build_workshop_reporting_status(db, date(2026, 4, 1))
    assert isinstance(result, list)


def test_build_workshop_reporting_status_structure():
    db = _make_mock_db()
    mock_row = MagicMock()
    mock_row.workshop_id = 15
    mock_row.workshop_name = '铸锭车间'
    mock_row.workshop_code = 'ZD'
    mock_row.report_status = 'submitted'
    mock_row.output_weight = 1175.0
    db.query.return_value.join.return_value.filter.return_value.all.return_value = [mock_row]
    result = _build_workshop_reporting_status(db, date(2026, 4, 1))
    assert len(result) == 1
    item = result[0]
    assert 'workshop_id' in item
    assert 'workshop_name' in item
    assert 'report_status' in item
    assert 'output_weight' in item
```

- [ ] **Step 2: Run test to see it fail**

```bash
docker compose exec -T backend bash -c "cd /app && python -m pytest tests/test_workshop_reporting_status.py -v"
```

Expected: ImportError — `_build_workshop_reporting_status` doesn't exist yet.

- [ ] **Step 3: Add `MobileShiftReport` import and `_build_workshop_reporting_status()` function**

In `backend/app/services/report_service.py`, add `MobileShiftReport` to the production model imports (line 12):

```python
from app.models.production import MobileShiftReport, ProductionException, ShiftProductionData
```

Then add the following helper function before `build_factory_dashboard()` (around line 852):

```python
def _build_workshop_reporting_status(db: Session, target_date: date) -> list[dict]:
    from app.models.master import Workshop as WorkshopModel
    rows = (
        db.query(
            WorkshopModel.id.label('workshop_id'),
            WorkshopModel.name.label('workshop_name'),
            WorkshopModel.code.label('workshop_code'),
            MobileShiftReport.report_status,
            func.cast(func.sum(MobileShiftReport.output_weight), type_=None).label('output_weight'),
        )
        .outerjoin(
            MobileShiftReport,
            (MobileShiftReport.workshop_id == WorkshopModel.id)
            & (MobileShiftReport.business_date == target_date),
        )
        .filter(WorkshopModel.is_active.is_(True), WorkshopModel.workshop_type.isnot(None))
        .group_by(
            WorkshopModel.id,
            WorkshopModel.name,
            WorkshopModel.code,
            MobileShiftReport.report_status,
        )
        .all()
    )

    result = []
    for row in rows:
        status = row.report_status or 'unreported'
        result.append({
            'workshop_id': row.workshop_id,
            'workshop_name': row.workshop_name,
            'workshop_code': row.workshop_code,
            'report_status': status,
            'output_weight': float(row.output_weight) if row.output_weight is not None else None,
        })
    return result
```

- [ ] **Step 4: Add `workshop_reporting_status` to the `build_factory_dashboard()` return dict**

In `build_factory_dashboard()`, find the `return {` dict (line ~937). Add one entry at the end before the closing `}`:

```python
        'workshop_reporting_status': _build_workshop_reporting_status(db, target_date=target_date),
```

The full return dict should now end with:
```python
        'workshop_output_summary': build_workshop_output_summary(db, target_date=target_date, status_scope='include_reviewed'),
        'workshop_attendance_summary': build_workshop_attendance_summary(db, target_date=target_date),
        'workshop_reporting_status': _build_workshop_reporting_status(db, target_date),
    }
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec -T backend bash -c "cd /app && python -m pytest tests/test_workshop_reporting_status.py -v"
```

Expected: All 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/report_service.py backend/tests/test_workshop_reporting_status.py
git commit -m "feat: add per-workshop reporting status to factory dashboard API"
```

---

## Task 6: Factory dashboard — Title rename + workshop status grid + catch

**Files:**
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`

- [ ] **Step 1: Rename title**

In `FactoryDirector.vue` line 5, find:
```html
        <h1>未来版生产驾驶舱</h1>
```
Replace with:
```html
        <h1>生产驾驶舱</h1>
```

- [ ] **Step 2: Add workshop status grid panel after the stat grid**

After the closing `</div>` of the stat grid (around line 53, after `</div>` that closes `<div class="stat-grid">`), insert the new panel:

```html
    <el-card class="panel" v-loading="loading">
      <template #header>今日上报状态</template>
      <div class="reporting-status-grid">
        <div
          v-for="item in data.workshop_reporting_status || []"
          :key="item.workshop_id"
          class="reporting-status-card"
        >
          <div class="reporting-status-name">{{ item.workshop_name }}</div>
          <el-tag
            :type="reportStatusTagType(item.report_status)"
            effect="plain"
            size="large"
          >
            {{ reportStatusLabel(item.report_status) }}
          </el-tag>
          <div v-if="item.output_weight != null" class="reporting-status-weight">
            {{ formatNumber(item.output_weight) }} 吨
          </div>
        </div>
        <div v-if="!(data.workshop_reporting_status || []).length" class="template-empty">
          暂无车间数据
        </div>
      </div>
    </el-card>
```

- [ ] **Step 3: Add helper functions and catch to `load()` in script section**

In the `<script setup>` section, add the two helper functions and update `load()`:

Add after the existing `formatNumber` import line:
```javascript
function reportStatusLabel(status) {
  const map = {
    submitted: '已上报',
    reviewed: '已审核',
    draft: '填报中',
    unreported: '未上报',
    late: '迟报',
  }
  return map[status] || status || '未上报'
}

function reportStatusTagType(status) {
  const map = {
    submitted: 'success',
    reviewed: 'success',
    draft: 'primary',
    unreported: 'warning',
    late: 'danger',
  }
  return map[status] || 'info'
}
```

Update `load()` to add a `catch` block (currently it has `try/finally` but no catch):

```javascript
async function load() {
  loading.value = true
  try {
    const [dashboardPayload, deliveryPayload] = await Promise.all([
      fetchFactoryDashboard({ target_date: targetDate.value }),
      fetchDeliveryStatus({ target_date: targetDate.value })
    ])
    data.value = dashboardPayload
    delivery.value = deliveryPayload
    lastRefreshAt.value = new Date().toISOString()
  } catch {
    ElMessage.error('数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
```

Also add `ElMessage` to the existing import from `element-plus`. Find the imports and add:
```javascript
import { ElMessage } from 'element-plus'
```

- [ ] **Step 4: Add CSS for the reporting status grid**

At the bottom of the file (or in the existing `<style>` block if present), add:

```css
<style scoped>
.reporting-status-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.reporting-status-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  min-width: 100px;
}

.reporting-status-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.reporting-status-weight {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
```

- [ ] **Step 5: Verify in browser**

Navigate to `https://localhost/dashboard/factory`. Confirm:
1. Title shows "生产驾驶舱" (not "未来版生产驾驶舱")
2. "今日上报状态" panel appears with workshop cards showing status chips
3. Simulating API failure (disconnect network) shows error toast rather than silent failure

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/dashboard/FactoryDirector.vue
git commit -m "feat: factory dashboard — rename title, add per-workshop reporting status grid, add error handling"
```

---

## Task 7: Workshop dashboard — Replace input-number + add loading/catch/watchers

**Files:**
- Modify: `frontend/src/views/dashboard/WorkshopDirector.vue`

- [ ] **Step 1: Rewrite `WorkshopDirector.vue` script section**

Replace the entire `<script setup>` section (lines 114–134):

```javascript
<script setup>
import { onMounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchDeliveryStatus, fetchWorkshopDashboard } from '../../api/dashboard'
import { fetchWorkshops } from '../../api/master'
import { formatDeliveryMissingSteps, formatNumber } from '../../utils/display'

const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const workshopId = ref(null)
const workshops = ref([])
const data = ref({})
const delivery = ref({})
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const params = { target_date: targetDate.value }
    if (workshopId.value) params.workshop_id = workshopId.value
    const [dashboardPayload, deliveryPayload] = await Promise.all([
      fetchWorkshopDashboard(params),
      fetchDeliveryStatus({ target_date: targetDate.value })
    ])
    data.value = dashboardPayload
    delivery.value = deliveryPayload
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

watch([targetDate, workshopId], load)

onMounted(async () => {
  try {
    const items = await fetchWorkshops({ limit: 500, is_active: true })
    workshops.value = items
    if (items.length > 0) workshopId.value = items[0].id
  } catch {
    ElMessage.error('车间列表加载失败')
  }
  await load()
})
</script>
```

- [ ] **Step 2: Update the template header to replace input-number with el-select**

In the `<template>` section, find:
```html
        <el-input-number v-model="workshopId" :min="1" controls-position="right" placeholder="车间编号" />
```
Replace with:
```html
        <el-select v-model="workshopId" placeholder="选择车间" clearable style="width: 160px">
          <el-option
            v-for="w in workshops"
            :key="w.id"
            :label="w.name"
            :value="w.id"
          />
        </el-select>
```

- [ ] **Step 3: Add `v-loading` to stat grid and all panels**

Add `v-loading="loading"` to:
- `<div class="stat-grid">` → `<div class="stat-grid" v-loading="loading">`
- Each `<el-card class="panel">` → `<el-card class="panel" v-loading="loading">`

There are 4 `el-card` panels in WorkshopDirector.vue. Add `v-loading="loading"` to each.

- [ ] **Step 4: Verify in browser**

Navigate to `https://localhost/dashboard/workshop`. Confirm:
1. A dropdown of workshop names appears instead of a numeric input
2. First workshop auto-selects and data loads
3. Changing the date or workshop triggers data refresh
4. Loading spinners appear on cards during fetch

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/dashboard/WorkshopDirector.vue
git commit -m "feat: workshop dashboard — replace numeric ID input with workshop dropdown, add loading states, error handling, and watchers"
```

---

## Task 8: Global error handling — ShiftCenter, UserManagement, Equipment

**Files:**
- Modify: `frontend/src/views/shift/ShiftCenter.vue`
- Modify: `frontend/src/views/master/UserManagement.vue`
- Modify: `frontend/src/views/master/Equipment.vue`

### ShiftCenter.vue

- [ ] **Step 1: Wrap `load()` and `loadWorkshops()` in ShiftCenter.vue**

Find the `onMounted` block (line ~230):
```javascript
onMounted(async () => {
  await loadWorkshops()
  await load()
})
```

Replace with:
```javascript
onMounted(async () => {
  try {
    await loadWorkshops()
    await load()
  } catch {
    ElMessage.error('加载失败')
  }
})
```

`ElMessage` is already imported in ShiftCenter.vue.

### UserManagement.vue

- [ ] **Step 2: Wrap `onMounted` initializer in UserManagement.vue**

Find the `onMounted` block (line ~366):
```javascript
onMounted(async () => {
  const [workshopItems, teamItems] = await Promise.all([
    fetchWorkshops({ limit: 500 }),
    fetchTeams({ limit: 500 })
  ])
  workshops.value = workshopItems
  teams.value = teamItems
  await load()
})
```

Replace with:
```javascript
onMounted(async () => {
  try {
    const [workshopItems, teamItems] = await Promise.all([
      fetchWorkshops({ limit: 500 }),
      fetchTeams({ limit: 500 })
    ])
    workshops.value = workshopItems
    teams.value = teamItems
    await load()
  } catch {
    ElMessage.error('加载失败')
  }
})
```

`ElMessage` is already imported in UserManagement.vue.

### Equipment.vue

- [ ] **Step 3: Wrap `onMounted` initializer in Equipment.vue**

Find the `onMounted` block (line ~475):
```javascript
onMounted(async () => {
  await loadMasterData()
  await load()
})
```

Replace with:
```javascript
onMounted(async () => {
  try {
    await loadMasterData()
    await load()
  } catch {
    ElMessage.error('加载失败')
  }
})
```

Add `ElMessage` import at the top of the script section in Equipment.vue if it's not already there:
```javascript
import { ElMessage } from 'element-plus'
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/shift/ShiftCenter.vue frontend/src/views/master/UserManagement.vue frontend/src/views/master/Equipment.vue
git commit -m "fix: add try/catch error handling to onMounted in ShiftCenter, UserManagement, and Equipment"
```

---

## Task 9: Template editor — Add role visibility hint

**Files:**
- Modify: `frontend/src/views/master/WorkshopTemplateConfig.vue`

- [ ] **Step 1: Add the role visibility hint beneath `entry_fields` section header**

In `WorkshopTemplateConfig.vue`, find the `sections` array (around line 128):
```javascript
const sections = [
  { key: 'entry_fields', label: '核心原始值', hint: '班长/机台最常录入的过程字段，优先结构化。' },
  { key: 'extra_fields', label: '车间补充字段', hint: '只属于当前车间模板的补充项，不做全厂统一。' },
  { key: 'qc_fields', label: '质检补充字段', hint: '需要质检角色补充的字段。' },
  { key: 'readonly_fields', label: '公式与只读字段', hint: '系统自动计算或仅展示字段，不能人工录入。' }
]
```

Replace with:
```javascript
const sections = [
  { key: 'entry_fields', label: '核心原始值', hint: '班长/机台最常录入的过程字段，优先结构化。', roleNote: '权限说明：班长（shift_leader）可填写；管理员可查看所有字段。' },
  { key: 'extra_fields', label: '车间补充字段', hint: '只属于当前车间模板的补充项，不做全厂统一。', roleNote: null },
  { key: 'qc_fields', label: '质检补充字段', hint: '需要质检角色补充的字段。', roleNote: null },
  { key: 'readonly_fields', label: '公式与只读字段', hint: '系统自动计算或仅展示字段，不能人工录入。', roleNote: null }
]
```

- [ ] **Step 2: Render `roleNote` in the section card template**

Find the section card template (around line 65). The section header currently looks like:
```html
              <strong>{{ section.label }}</strong>
              <div class="template-section__hint">{{ section.hint }}</div>
```

Add the role note beneath the hint:
```html
              <strong>{{ section.label }}</strong>
              <div class="template-section__hint">{{ section.hint }}</div>
              <div v-if="section.roleNote" class="template-section__role-note">{{ section.roleNote }}</div>
```

- [ ] **Step 3: Add CSS for the role note**

In the `<style>` block (or add a `<style scoped>` block if absent), add:
```css
.template-section__role-note {
  font-size: 12px;
  color: var(--el-color-info);
  margin-top: 2px;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/master/WorkshopTemplateConfig.vue
git commit -m "feat: add role visibility note to entry_fields section in template editor"
```

---

## Task 10: Run all tests and verify deployability

- [ ] **Step 1: Run backend unit tests**

```bash
docker compose exec -T backend bash -c "cd /app && python -m pytest tests/test_workshop_template_power_roles.py tests/test_workshop_reporting_status.py -v"
```

Expected: All 6 tests PASS

- [ ] **Step 2: Run frontend unit tests**

```bash
cd frontend && node --test tests/offlineResilience.test.js
```

Expected: All 3 tests PASS

- [ ] **Step 3: Run Playwright e2e tests**

```bash
cd frontend && npx playwright test --reporter=list
```

Expected: All 5 existing Playwright tests PASS

- [ ] **Step 4: Manual smoke test — admin mobile form**

1. Log in as admin / Admin@123456
2. Navigate to `/mobile` → tap "去填报"
3. Confirm the report form shows ≥ 1 editable field

- [ ] **Step 5: Manual smoke test — factory dashboard**

1. Log in as admin
2. Navigate to `/dashboard/factory`
3. Confirm title is "生产驾驶舱"
4. Confirm "今日上报状态" panel appears with at least one workshop card

- [ ] **Step 6: Manual smoke test — workshop dashboard**

1. Navigate to `/dashboard/workshop`
2. Confirm workshop dropdown appears (not a number input)
3. Select a workshop, confirm data loads
4. Change the date, confirm data refreshes automatically

---

## Self-Review Against Spec

| Spec requirement | Covered by task |
|-----------------|----------------|
| Admin/manager power-user bypass | Task 1 |
| Mojibake '备注' and '其他用户' | Task 2 |
| loadPage() 404 error state | Task 3 |
| Draft key `machineId` prefix fix | Task 4 |
| `workshop_reporting_status` backend | Task 5 |
| Factory dashboard title rename | Task 6 |
| Factory dashboard workshop grid | Task 6 |
| Factory dashboard error catch | Task 6 |
| Workshop dropdown | Task 7 |
| Workshop loading states | Task 7 |
| Workshop error handling | Task 7 |
| Workshop watchers | Task 7 |
| ShiftCenter error handling | Task 8 |
| UserManagement error handling | Task 8 |
| Equipment error handling | Task 8 |
| Template editor role hint | Task 9 |
