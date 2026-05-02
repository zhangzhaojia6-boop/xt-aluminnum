# 填报端 UX 精简 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 主操按卷录入时只看到必须手动填的字段——合金牌号下拉选择、规格三框输入、废料/成品率完全隐藏。

**Architecture:** 后端新增全局配置接口 + 模板字段属性扩展；前端 EntryFieldInput 组件新增 select 和 spec 渲染分支。

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3, Element Plus

---

### Task 1: 后端——全局配置接口（Codex）

**Files:**
- Create: `backend/app/routers/config.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Create config router**

```python
"""Global configuration endpoints."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/config", tags=["config"])

ALLOY_GRADES = [
    "1060", "1100", "3003", "3A21", "5052", "5083", "5754",
    "6061", "6063", "6082", "8011", "8079",
]

MATERIAL_STATES = [
    "O", "H12", "H14", "H16", "H18", "H22", "H24", "H26", "H32", "T4", "T6",
]


@router.get("/alloy-grades")
def get_alloy_grades():
    return ALLOY_GRADES


@router.get("/material-states")
def get_material_states():
    return MATERIAL_STATES
```

- [ ] **Step 2: Register router in main.py**

Add `from app.routers.config import router as config_router` and `app.include_router(config_router)`.

- [ ] **Step 3: Write test**

```python
# backend/tests/test_config_routes.py
def test_alloy_grades_returns_list(client):
    resp = client.get("/api/config/alloy-grades")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "5052" in data
    assert "3003" in data

def test_material_states_returns_list(client):
    resp = client.get("/api/config/material-states")
    assert resp.status_code == 200
    data = resp.json()
    assert "O" in data
    assert "H14" in data
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest backend/tests/test_config_routes.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/config.py backend/app/main.py backend/tests/test_config_routes.py
git commit -m "feat: add global config endpoints for alloy grades and material states"
```

---

### Task 2: 后端——模板字段类型更新（Codex）

**Files:**
- Modify: `backend/app/core/templates/__init__.py`

- [ ] **Step 1: Update alloy_grade fields across all workshops**

Change every `alloy_grade` field from `'type': 'text'` to `'type': 'select'` and add `'options_source': 'alloy_grades'`:

```python
# cold_roll (line ~588)
{'name': 'alloy_grade', 'label': '合金成分', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
# hot_roll (line ~625)
{'name': 'alloy_grade', 'label': '合金牌号', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
# finishing (line ~664)
{'name': 'alloy_grade', 'label': '合金', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
# shearing (line ~701)
{'name': 'alloy_grade', 'label': '成分', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
# casting (line ~738)
{'name': 'alloy_grade', 'label': '合金', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
# straightening (line ~776)
{'name': 'alloy_grade', 'label': '合金', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
# annealing (line ~836)
{'name': 'alloy_grade', 'label': '合金', 'type': 'select', 'required': True, 'options_source': 'alloy_grades'},
```

- [ ] **Step 2: Update material_state fields**

Change `material_state` from `'type': 'text'` to `'type': 'select'` with `'options_source': 'material_states'` in cold_roll, finishing, shearing, straightening templates.

- [ ] **Step 3: Add hidden flag to readonly_fields**

Add `'hidden': True` to all `scrap_weight` and `yield_rate` entries in `readonly_fields` across all workshops:

```python
# Example for cold_roll readonly_fields:
'readonly_fields': [
    {
        'name': 'scrap_weight',
        'label': '废料重量',
        'type': 'number',
        'unit': 'kg',
        'compute': 'input_weight - output_weight - spool_weight',
        'hidden': True,
    },
    {
        'name': 'yield_rate',
        'label': '成品率',
        'type': 'number',
        'unit': '%',
        'compute': 'output_weight / input_weight * 100',
        'hidden': True,
    },
],
```

Apply to: cold_roll, hot_roll, finishing, shearing, straightening, annealing, casting (yield_rate only).

Do NOT add `hidden: True` to `inventory` template's `actual_inventory_weight` — that one should remain visible.

- [ ] **Step 4: Run existing tests, verify no breakage**

Run: `pytest backend/tests/ -v --tb=short`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/templates/__init__.py
git commit -m "feat: alloy_grade/material_state → select type, readonly fields hidden"
```

---

### Task 3: 后端——coil entry 自动计算 scrap_weight（Codex）

**Files:**
- Modify: `backend/app/services/mobile_report/summary.py`

- [ ] **Step 1: Add auto-calculation in create_coil_entry**

In `create_coil_entry()` (line ~391), after building the `WorkOrderEntry`, add scrap_weight calculation before `db.add(entry)`:

```python
# Auto-calculate scrap_weight if not provided
if entry.scrap_weight is None and entry.input_weight and entry.output_weight:
    inp = float(entry.input_weight)
    out = float(entry.output_weight)
    spool = float(payload.get('spool_weight') or 0)
    trim = float(payload.get('trim_weight') or 0)
    tray = float(payload.get('tray_weight') or 0)
    entry.scrap_weight = round(inp - out - spool - trim - tray, 2)
```

Note: yield_rate is already calculated at lines 435-439.

- [ ] **Step 2: Write test**

```python
# backend/tests/test_coil_entry_auto_calc.py
def test_coil_entry_auto_calculates_scrap_weight(db, mobile_user):
    """scrap_weight should be auto-calculated when not provided."""
    from app.services.mobile_report.summary import create_coil_entry
    payload = {
        'tracking_card_no': 'TEST-AUTO-001',
        'business_date': '2026-05-02',
        'shift_id': 1,
        'input_weight': 1000,
        'output_weight': 950,
        'spool_weight': 10,
    }
    result = create_coil_entry(db, payload=payload, current_user=mobile_user)
    entry = db.query(WorkOrderEntry).get(result['id'])
    assert entry.scrap_weight == 40.0  # 1000 - 950 - 10
    assert entry.yield_rate == round(950 / 1000, 4)
```

- [ ] **Step 3: Run test, verify pass**

Run: `pytest backend/tests/test_coil_entry_auto_calc.py -v`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/mobile_report/summary.py backend/tests/test_coil_entry_auto_calc.py
git commit -m "feat: auto-calculate scrap_weight in coil entry when not provided"
```

---

### Task 4: 前端——EntryFieldInput 新增 select 渲染（Claude Code）

**Files:**
- Modify: `frontend/src/components/mobile/EntryFieldInput.vue`
- Modify: `frontend/src/api/mobile.js` (add config fetch)

- [ ] **Step 1: Add config API function**

In `frontend/src/api/mobile.js`, add:

```javascript
export function fetchFieldOptions(source) {
  return request.get(`/api/config/${source}`).then(r => r.data)
}
```

- [ ] **Step 2: Update EntryFieldInput to handle select and spec types**

Replace the current template with three branches: `time`, `select`, `spec`, and default `el-input`.

Add `select` branch with `el-select` + `filterable` + `allow-create`.
Add `spec` branch with three `el-input` boxes + "×" separators.

- [ ] **Step 3: Add options loading for select fields with options_source**

Use `onMounted` to fetch options from API when `field.options_source` is set. Cache in a module-level Map to avoid duplicate requests.

- [ ] **Step 4: Verify in browser**

Open DynamicEntryForm for a cold_roll workshop. Confirm:
- alloy_grade renders as searchable dropdown with 12 options
- material_state renders as searchable dropdown with 11 options
- input_spec renders as three-box input (厚×宽×长)
- Typing in dropdown filters options
- Can create new option not in list

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/mobile/EntryFieldInput.vue frontend/src/api/mobile.js
git commit -m "feat: EntryFieldInput supports select (filterable) and spec (three-box) types"
```

---

### Task 5: 前端——DynamicEntryForm 隐藏 readonly 字段（Claude Code）

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

- [ ] **Step 1: Filter hidden readonly fields**

In `readonlyDisplayItems` computed (line ~806), add filter:

```javascript
const readonlyDisplayItems = computed(() =>
  readonlyFields.value
    .filter((field) => !field.hidden)
    .map((field) => {
      const value = resolveReadonlyFieldValue(field)
      if (isEmptyValue(value)) return null
      return {
        name: field.name,
        label: displayFieldLabel(field),
        value: formatFieldValueForDisplay(field, value)
      }
    })
    .filter(Boolean)
)
```

- [ ] **Step 2: Keep yield display in core card header (optional)**

The `yieldRate` / `yieldDisplay` computed at line ~779 is used in the core card header independently of `readonlyDisplayItems`. This can stay as-is since it's a prominent UX element, OR be removed per spec. Remove it — spec says completely hidden.

Remove the yield display from the core card footer (lines ~280-285).

- [ ] **Step 3: Verify in browser**

Open DynamicEntryForm. Confirm:
- No "自动计算" section visible
- No yield rate display
- scrap_weight and yield_rate still calculated and saved on submit (backend handles it)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "feat: hide readonly fields marked hidden from mobile entry UI"
```

---

### Task 6: 前端——UnifiedEntryForm 隐藏 readonly 字段（Claude Code）

**Files:**
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue`

- [ ] **Step 1: Filter hidden readonly fields**

In the template section (line ~106), add filter:

```html
<section v-if="visibleReadonlyFields.length" class="ue-group ue-group--readonly">
```

Add computed:

```javascript
const visibleReadonlyFields = computed(() =>
  readonlyFields.value.filter(rf => !rf.hidden)
)
```

Update the `v-for` to use `visibleReadonlyFields` instead of `readonlyFields`.

- [ ] **Step 2: Verify in browser**

Open UnifiedEntryForm. Confirm "自动计算" section is gone.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/mobile/UnifiedEntryForm.vue
git commit -m "feat: hide readonly fields marked hidden in UnifiedEntryForm"
```

---

### Task 7: 后端——更新 copy-consistency tests（Codex）

**Files:**
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: Update tests that check alloy_grade field type**

Any test asserting `'type': 'text'` for alloy_grade should be updated to `'type': 'select'`.

- [ ] **Step 2: Run full test suite**

Run: `pytest backend/tests/ -v --tb=short`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_mobile_entry_copy_consistency.py
git commit -m "test: update copy-consistency tests for select field types"
```
