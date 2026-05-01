# Mobile Form Cleanup Implementation Plan

> **给执行 Agent:** 按任务顺序推进。实现时使用 `superpowers:subagent-driven-development`，或用 `superpowers:executing-plans` 逐项执行。每个步骤都用 `- [ ]` 勾选跟踪。

**目标:** 让 `/entry/fill` 这条移动填报主链路能稳定提交，扫码/机台账号不再被同班次其他账号误锁，字段口径回到文档定义，再清掉移动表单里的占位和样式残留。

**架构:** `/entry/fill` 的 `UnifiedEntryForm.vue` 是 Phase 1 的主填报面，`DynamicEntryForm.vue` 和 `ShiftReportForm.vue` 保留为兼容路由。按数据粒度拆提交：按卷录入写 `WorkOrderEntry`，班次汇总和 owner 补录写 `MobileShiftReport`。`tracking_card_no` 是扫码/工单身份，`batch_no` 是业务批号，不能互相兜底。

**技术栈:** Vue 3、Element Plus、Vite、FastAPI、Pydantic、SQLAlchemy、pytest、Playwright。

---

## 这次要解决的问题

- `UnifiedEntryForm.vue` 现在把表单放进 `{ data: { ...form } }` 后提交到 `/mobile/report/save` 和 `/mobile/report/submit`。后端的 `MobileReportPayload` 读的是顶层 `input_weight`、`output_weight`、`scrap_weight` 等字段，嵌套的 `data` 被忽略，于是 `_required_submit_fields()` 判断成缺必填项。
- 一些扫码账号登录后看到类似“当前班次已由其他负责人处理”的提示。根因在 `get_current_shift()` 用 `MobileShiftReport.owner_user_id` 锁整班。这个规则适合单个班次报告负责人，不适合按卷扫码录入。一个班次里可以有多个机台账号录不同卷。
- 字段口径混在一起了。文档里已经分清：`tracking_card_no` 属于扫码/工单身份，`batch_no` 属于业务批号；卷级扫码页和班组日报页也不是同一类输入面。
- 原计划只处理 CSS 和死代码。视觉清理继续做，但排在功能契约后面。

## 依据文档

- `docs/SYSTEM_CENTER.md`: `/entry/*` 只承接现场填报、草稿、历史和异常补录，不把生产事实写入口搬到审阅端或管理端。
- `docs/current-route-map.md`: `/entry` 和 `/entry/fill` 是正式入口，`/mobile/*` 只是兼容重定向。
- `docs/ENTRY_FIELD_AUDIT.md`: `tracking_card_no` 和 `batch_no` 分属不同语义；owner-only 字段不能下发给普通主操。
- `docs/mes-field-mapping-table-phase1.md`: 卷级扫码字段落在 `work_orders` / `work_order_entries`，班次汇总字段落在 `mobile_shift_reports`。
- `docs/现场UAT清单.md`: 主操不能进入或不能提交、owner 不能补录、权限串看串改，都属于阻断问题。
- `docs/企业微信生产入口准备清单.md`: 当前正式身份入口优先浏览器和钉钉，企业微信只保留兼容说明。

## 不变量

- 对外名称继续用 `数据中枢`，不要把产品叫成 MES。
- 不新增依赖。
- 不新增数据库表。
- 不新增 schema 或组件 props: `description`、`explanation`、`helperText`、`tooltip`、`note`、`rationale`。现有后端 `MobileReportPayload.note` 可以继续复用，不要再造同义字段。
- 前端只校验当前可见、可编辑、属于当前角色的字段。隐藏、只读、禁用、越权字段不能拦提交。
- 后端报错用现场能看懂的中文字段名，不把内部 key 直接抛给用户。
- 按卷扫码录入不能被另一个用户的 `MobileShiftReport.owner_user_id` 锁住。
- 需要 `tracking_card_no` 时，由 `/mobile/entry-fields` 明确返回这个字段，不用 `batch_no` 顶替。

## 文件边界

- `frontend/src/views/mobile/UnifiedEntryForm.vue`: `/entry/fill` 主填报页，负责字段渲染、可见必填校验、payload 构造和提交状态。
- `frontend/src/views/mobile/MobileEntry.vue`: 入口页，负责开始填报按钮和无法填报状态。
- `frontend/src/api/mobile.js`: 保持薄封装，只在 payload 调用需要命名封装时调整。
- `backend/app/schemas/mobile.py`: 保持顶层字段契约，必要时兼容旧的 `data` 嵌套。
- `backend/app/services/mobile_report_service.py`: 负责当前班次、归属判断、payload 归一化、必填校验、按卷聚合、历史数据。
- `backend/app/routers/mobile.py`: 负责 `/mobile/entry-fields` 的角色字段、协议字段和提交目标元信息。
- `backend/tests/test_mobile_report_service.py`: 测 payload 归一化和必填判断。
- `backend/tests/test_mobile_bootstrap.py`: 测当前班次、扫码账号、机台账号的可填状态。
- `backend/tests/test_mobile_entry_copy_consistency.py`: 静态检查前端契约和清理项。
- `backend/tests/test_qr_login.py`: 保留二维码登录测试，只有 QR 角色或机台上下文需要断言时才补。
- `frontend/e2e/mobile-entry-smoke.spec.js`: 覆盖 `/entry/fill` 浏览器提交，不再误报必填，不再出现已删除占位内容。
- `docs/superpowers/specs/2026-05-01-mobile-form-cleanup-design.md`: 只有实现改变了已接受行为时才同步更新。

---

### Task 1: 用测试复现提交契约错位

**Files:**
- Modify: `backend/tests/test_mobile_report_service.py`
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: 给嵌套 payload 补红灯测试**

在 `backend/tests/test_mobile_report_service.py` 里补 import:

```python
from app.services.mobile_report_service import _normalize_mobile_report_payload
```

新增测试：

```python
def test_normalize_mobile_report_payload_flattens_unified_entry_data() -> None:
    payload = _normalize_mobile_report_payload(
        {
            'business_date': date(2026, 5, 1),
            'shift_id': 1,
            'data': {
                'attendance_count': 8,
                'input_weight': 120.5,
                'output_weight': 118.0,
                'scrap_weight': 2.5,
                'operator_notes': '本班正常',
            },
        }
    )

    assert payload['input_weight'] == 120.5
    assert payload['output_weight'] == 118.0
    assert payload['scrap_weight'] == 2.5
    assert payload['attendance_count'] == 8
    assert payload['note'] == '本班正常'
```

- [ ] **Step 2: 给必填判断补红灯测试**

```python
def test_required_submit_fields_reads_normalized_payload() -> None:
    payload = _normalize_mobile_report_payload(
        {
            'business_date': date(2026, 5, 1),
            'shift_id': 1,
            'data': {
                'input_weight': 100,
                'output_weight': 96,
            },
        }
    )

    assert _required_submit_fields(payload) == []
```

- [ ] **Step 3: 给前端 payload builder 补静态测试**

在 `backend/tests/test_mobile_entry_copy_consistency.py` 新增：

```python
def test_unified_entry_form_builds_endpoint_specific_payloads() -> None:
    source = _read_repo_file('frontend/src/views/mobile/UnifiedEntryForm.vue')

    assert 'function buildCoilEntryPayload' in source
    assert 'function buildMobileReportPayload' in source
    assert "data: { ...form }" not in source
    assert 'await createCoilEntry(buildCoilEntryPayload(sc))' in source
    assert 'await submitMobileReport(buildMobileReportPayload(sc))' in source
```

- [ ] **Step 4: 跑红灯**

```bash
cd backend
python -m pytest tests/test_mobile_report_service.py::test_normalize_mobile_report_payload_flattens_unified_entry_data tests/test_mobile_report_service.py::test_required_submit_fields_reads_normalized_payload tests/test_mobile_entry_copy_consistency.py::test_unified_entry_form_builds_endpoint_specific_payloads -q
```

Expected: FAIL，原因是 `_normalize_mobile_report_payload`、`buildCoilEntryPayload`、`buildMobileReportPayload` 还不存在。

- [ ] **Step 5: 提交红灯测试**

```bash
git add backend/tests/test_mobile_report_service.py backend/tests/test_mobile_entry_copy_consistency.py
git commit -m "test: reproduce mobile entry submit contract failure"
```

---

### Task 2: 修后端移动日报 payload 归一化

**Files:**
- Modify: `backend/app/schemas/mobile.py`
- Modify: `backend/app/services/mobile_report_service.py`
- Modify: `backend/tests/test_mobile_report_service.py`

- [ ] **Step 1: 让 `MobileReportPayload` 兼容旧嵌套结构**

在 `backend/app/schemas/mobile.py` 的 `MobileReportPayload` 中加入：

```python
    data: dict[str, object] = Field(default_factory=dict)
```

保留已有顶层字段，不要删。

- [ ] **Step 2: 增加 payload 归一化函数**

在 `backend/app/services/mobile_report_service.py`，放到 `_required_submit_fields()` 附近：

```python
MOBILE_REPORT_DATA_KEY_MAP = {
    'operator_notes': 'note',
}

MOBILE_REPORT_ALLOWED_DATA_KEYS = {
    'attendance_count',
    'input_weight',
    'output_weight',
    'scrap_weight',
    'storage_prepared',
    'storage_finished',
    'shipment_weight',
    'contract_received',
    'electricity_daily',
    'gas_daily',
    'has_exception',
    'exception_type',
    'operator_notes',
    'note',
    'optional_photo_url',
}


def _normalize_mobile_report_payload(payload: dict) -> dict:
    normalized = dict(payload)
    nested = normalized.pop('data', None) or {}
    if not isinstance(nested, dict):
        nested = {}

    for source_key, value in nested.items():
        if source_key not in MOBILE_REPORT_ALLOWED_DATA_KEYS:
            continue
        target_key = MOBILE_REPORT_DATA_KEY_MAP.get(source_key, source_key)
        if normalized.get(target_key) is None:
            normalized[target_key] = value

    return normalized
```

- [ ] **Step 3: 在保存和提交入口统一归一化**

`save_or_submit_report()` 里，`assert_mobile_user_access(current_user)` 之后加入：

```python
    payload = _normalize_mobile_report_payload(payload)
```

- [ ] **Step 4: 先不放宽班次汇总必填规则**

`_required_submit_fields()` 保持当前规则。这个任务只解决“值传到了但后端没读到”。

- [ ] **Step 5: 跑目标测试**

```bash
cd backend
python -m pytest tests/test_mobile_report_service.py::test_normalize_mobile_report_payload_flattens_unified_entry_data tests/test_mobile_report_service.py::test_required_submit_fields_reads_normalized_payload -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/schemas/mobile.py backend/app/services/mobile_report_service.py backend/tests/test_mobile_report_service.py
git commit -m "fix: normalize mobile report payload from unified entry"
```

---

### Task 3: 修 `UnifiedEntryForm` 的 payload builder 和可见必填校验

**Files:**
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue`
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: 字段 label 显示必填标记**

把字段 label 改成：

```vue
<label class="ue-field__label">
  <span v-if="field.required" class="mobile-required">*</span>
  {{ field.label }}
  <span v-if="field.unit" class="ue-field__unit">{{ field.unit }}</span>
</label>
```

- [ ] **Step 2: 加值处理工具函数**

在 `<script setup>` 中，放到 `syncSpec()` 附近：

```javascript
function isEmptyValue(value) {
  return value === null || value === undefined || String(value).trim() === ''
}

function normalizeNumberValue(value) {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizedFormValues() {
  const values = {}
  for (const group of groups.value) {
    for (const field of group.fields) {
      const value = form[field.name]
      values[field.name] = field.type === 'number' ? normalizeNumberValue(value) : value
    }
  }
  return values
}
```

- [ ] **Step 3: 只校验可见字段**

```javascript
function validateVisibleRequiredFields() {
  for (const group of groups.value) {
    for (const field of group.fields) {
      if (field.required && isEmptyValue(form[field.name])) {
        ElMessage.warning(`请先填写：${field.label}`)
        return false
      }
    }
  }
  return true
}
```

- [ ] **Step 4: 明确构造按卷 payload**

```javascript
function buildCoilEntryPayload(sc) {
  const values = normalizedFormValues()
  const trackingCardNo = String(values.tracking_card_no || '').trim()
  return {
    tracking_card_no: trackingCardNo,
    alloy_grade: values.alloy_grade || null,
    input_spec: values.input_spec || null,
    output_spec: values.output_spec || null,
    on_machine_time: values.on_machine_time || null,
    off_machine_time: values.off_machine_time || null,
    input_weight: values.input_weight,
    output_weight: values.output_weight,
    scrap_weight: values.scrap_weight,
    operator_name: values.operator_name || auth.displayName || '',
    operator_notes: values.operator_notes || '',
    business_date: sc.business_date,
    shift_id: sc.shift_id,
  }
}
```

不要用 `batch_no` 兜底 `tracking_card_no`。Task 5 会让后端明确下发 `tracking_card_no`。

- [ ] **Step 5: 明确构造班次报告 payload**

```javascript
function buildMobileReportPayload(sc) {
  const values = normalizedFormValues()
  return {
    business_date: sc.business_date,
    shift_id: sc.shift_id,
    attendance_count: normalizeNumberValue(values.attendance_count),
    input_weight: normalizeNumberValue(values.input_weight),
    output_weight: normalizeNumberValue(values.output_weight),
    scrap_weight: normalizeNumberValue(values.scrap_weight),
    storage_prepared: normalizeNumberValue(values.storage_prepared),
    storage_finished: normalizeNumberValue(values.storage_finished),
    shipment_weight: normalizeNumberValue(values.shipment_weight),
    contract_received: normalizeNumberValue(values.contract_received),
    electricity_daily: normalizeNumberValue(values.electricity_daily),
    gas_daily: normalizeNumberValue(values.gas_daily),
    has_exception: Boolean(values.has_exception),
    exception_type: values.exception_type || null,
    note: values.operator_notes || values.note || null,
  }
}
```

这里复用现有后端 `note` 字段，不新增同义字段。

- [ ] **Step 6: 在 `handleSubmit()` 中使用 builder**

按卷分支替换为：

```javascript
      const saved = await createCoilEntry(buildCoilEntryPayload(sc))
```

班次分支替换为：

```javascript
      const payload = buildMobileReportPayload(sc)
      await saveMobileReport(payload)
      await submitMobileReport(payload)
```

进入分支前先加：

```javascript
    if (!validateVisibleRequiredFields()) return
```

- [ ] **Step 7: 跑静态测试**

```bash
cd backend
python -m pytest tests/test_mobile_entry_copy_consistency.py::test_unified_entry_form_builds_endpoint_specific_payloads -q
```

Expected: PASS。

- [ ] **Step 8: 跑前端构建**

```bash
cd frontend
npm run build
```

Expected: 构建成功。

- [ ] **Step 9: 提交**

```bash
git add frontend/src/views/mobile/UnifiedEntryForm.vue backend/tests/test_mobile_entry_copy_consistency.py
git commit -m "fix: align unified mobile entry payloads with API contracts"
```

---

### Task 4: 取消按卷扫码账号的班次报告归属误锁

**Files:**
- Modify: `backend/app/services/mobile_report_service.py`
- Modify: `backend/tests/test_mobile_bootstrap.py`

- [ ] **Step 1: 增加按卷账号不被其他报告 owner 锁住的测试**

新增或复用现有 fixture，覆盖这个场景：同一车间、同一班次已有另一个用户的 `MobileShiftReport`，当前用户是扫码/机台按卷录入账号。

期望：

```python
assert payload['can_submit'] is True
assert payload['report_status'] != 'locked'
assert payload['ownership_note'] is None
```

如果完整路由测试铺设太重，就先单测 Step 2 的 helper，但要保证这个场景被写进测试名。

- [ ] **Step 2: 增加是否使用班次报告归属的 helper**

在 `backend/app/services/mobile_report_service.py` 增加：

```python
def _uses_shift_report_ownership(current_user: User) -> bool:
    return _resolve_entry_mode(current_user.role or '') != 'coil_entry'
```

- [ ] **Step 3: 在 `get_current_shift()` 中使用 helper**

调整查找 `report` 和计算 `ownership_note` 的代码。按卷用户不读 `MobileShiftReport.owner_user_id` 作为当前任务锁：

```python
    uses_report_ownership = _uses_shift_report_ownership(current_user)
    report = None
    if context.shift is not None and uses_report_ownership:
        report = _find_mobile_report(...)

    ownership_note = _ownership_note(report=report, current_user=current_user) if uses_report_ownership else None
```

考勤快照逻辑不改。

- [ ] **Step 4: 给按卷用户返回可识别状态**

按卷用户没有班次报告时返回：

```python
    report_id = None
    report_status = 'coil_entry'
```

只有真正使用班次报告归属时，才允许 `report_status = 'locked'`。

- [ ] **Step 5: 跑目标测试**

```bash
cd backend
python -m pytest tests/test_mobile_bootstrap.py tests/test_mobile_scope_isolation.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/mobile_report_service.py backend/tests/test_mobile_bootstrap.py
git commit -m "fix: allow QR machine users to submit per-coil entries independently"
```

---

### Task 5: 按文档修正移动字段分类

**Files:**
- Modify: `backend/app/routers/mobile.py`
- Modify: `backend/app/schemas/mobile.py`
- Modify: `backend/tests/test_mobile_bootstrap.py`
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue`

- [ ] **Step 1: 给机台/主操字段下发补测试**

新增或扩展 `/api/v1/mobile/entry-fields` 测试。`machine_operator` 或机台绑定账号应返回 `tracking_card_no` 作为按卷身份字段：

```python
assert payload['mode'] == 'per_coil'
first_fields = payload['groups'][0]['fields']
assert first_fields[0]['name'] == 'tracking_card_no'
assert first_fields[0]['label'] == '随行卡号'
assert first_fields[0]['required'] is True
assert all(field['name'] != 'batch_no' or field['label'] == '批号' for field in first_fields)
```

- [ ] **Step 2: 增加协议字段 helper**

在 `backend/app/routers/mobile.py` 中增加：

```python
def _tracking_card_field() -> dict:
    return {
        'name': 'tracking_card_no',
        'label': '随行卡号',
        'type': 'text',
        'required': True,
        'role_write': ['machine_operator', 'shift_leader', 'mobile_user', 'team_leader'],
    }
```

- [ ] **Step 3: 按卷模式前置 `tracking_card_no`**

`is_per_coil` 为 true 时，把 `_tracking_card_field()` 放到 entry fields 第一位。已有同名字段时不要重复插入。

不要重命名现有 `batch_no`，模板里有就继续显示为 `批号`。

- [ ] **Step 4: `/mobile/entry-fields` 返回提交目标元信息**

返回值里增加：

```python
'submit_target': 'coil_entry' if is_per_coil else 'shift_report',
'identity_field': 'tracking_card_no' if is_per_coil else None,
```

不需要数据库迁移。

- [ ] **Step 5: `UnifiedEntryForm.vue` 使用后端元信息**

新增状态：

```javascript
const submitTarget = ref('shift_report')
const identityField = ref(null)
```

加载字段后设置：

```javascript
submitTarget.value = fields.submit_target || (fields.mode === 'per_coil' ? 'coil_entry' : 'shift_report')
identityField.value = fields.identity_field || null
```

`handleSubmit()` 中用 `submitTarget.value === 'coil_entry'` 判断按卷提交，不再只看 `mode.value === 'per_coil'`。

- [ ] **Step 6: 跑目标测试**

```bash
cd backend
python -m pytest tests/test_mobile_bootstrap.py tests/test_mobile_entry_copy_consistency.py -q
```

Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add backend/app/routers/mobile.py backend/app/schemas/mobile.py backend/tests/test_mobile_bootstrap.py frontend/src/views/mobile/UnifiedEntryForm.vue backend/tests/test_mobile_entry_copy_consistency.py
git commit -m "fix: align mobile entry fields with scan and shift data boundaries"
```

---

### Task 6: 用 E2E 覆盖真实提交路径

**Files:**
- Modify: `frontend/e2e/mobile-entry-smoke.spec.js`

- [ ] **Step 1: mock `/mobile/entry-fields`**

给 `/entry/fill` 的按卷填报补 mock：

```javascript
await page.route('**/api/v1/mobile/entry-fields', async (route) => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      mode: 'per_coil',
      submit_target: 'coil_entry',
      identity_field: 'tracking_card_no',
      role: 'machine_operator',
      role_label: '产量数据',
      groups: [{
        label: '产量数据',
        fields: [
          { name: 'tracking_card_no', label: '随行卡号', type: 'text', required: true },
          { name: 'alloy_grade', label: '合金', type: 'text', required: true },
          { name: 'input_weight', label: '投入重量', type: 'number', unit: 'kg', required: true },
          { name: 'output_weight', label: '产出重量', type: 'number', unit: 'kg', required: true },
        ],
      }],
      readonly_fields: [],
    }),
  })
})
```

- [ ] **Step 2: mock `/mobile/coil-entry` 成功提交**

```javascript
await page.route('**/api/v1/mobile/coil-entry', async (route) => {
  const body = route.request().postDataJSON()
  expect(body.tracking_card_no).toBe('TC-001')
  expect(body.input_weight).toBe(100)
  expect(body.output_weight).toBe(96)
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      id: 1,
      tracking_card_no: body.tracking_card_no,
      alloy_grade: body.alloy_grade,
      input_weight: body.input_weight,
      output_weight: body.output_weight,
      scrap_weight: body.scrap_weight || 0,
      business_date: body.business_date,
    }),
  })
})
```

- [ ] **Step 3: 新增不误报必填的浏览器测试**

```javascript
test('unified per-coil entry submits top-level payload without false required failure', async ({ page }) => {
  await page.goto('/entry/fill')
  await page.getByLabel('随行卡号').fill('TC-001')
  await page.getByLabel('合金').fill('5052')
  await page.getByLabel(/投入重量/).fill('100')
  await page.getByLabel(/产出重量/).fill('96')
  await page.getByRole('button', { name: '录入本卷' }).click()
  await expect(page.getByText('第1卷 录入成功')).toBeVisible()
  await expect(page.getByText(/required|必填项未填写/i)).toHaveCount(0)
})
```

如果 `getByLabel()` 找不到当前自定义结构，就在 `UnifiedEntryForm.vue` 的字段容器上加稳定 `data-testid`，测试改用 test id。

- [ ] **Step 4: 更新旧占位断言**

现有 smoke 里还期待 `entry-mes-trace-card`、`外部系统线索`、`不补后续码`。Task 7 删除占位卡后，这些断言改成 zero matches。

- [ ] **Step 5: 跑移动端 smoke**

```bash
cd frontend
npx playwright test e2e/mobile-entry-smoke.spec.js
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add frontend/e2e/mobile-entry-smoke.spec.js frontend/src/views/mobile/UnifiedEntryForm.vue
git commit -m "test: cover unified mobile entry submit flow"
```

---

### Task 7: 清理 `DynamicEntryForm` 和 `ShiftReportForm` 的占位与样式残留

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Modify: `frontend/src/views/mobile/ShiftReportForm.vue`
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: 删除外部系统线索占位卡**

从 `DynamicEntryForm.vue` 删除：

```html
        <el-card v-if="!isOwnerOnlyMode" class="panel mobile-card entry-external-trace-card" data-testid="entry-mes-trace-card">
          <template #header>外部系统线索</template>
          <div class="entry-external-trace">
            <span>前工序事实</span>
            <span>后工序同步</span>
            <span>不补后续码</span>
          </div>
        </el-card>
```

一起删除 `.entry-external-trace` 相关 CSS。

- [ ] **Step 2: 删除语音录入 stub**

删除：

```javascript
const voiceListeningField = ref('')

function isVoiceFieldSupported(_field) {
  return false
}

function toggleVoicePrefill(_field) {
  voiceListeningField.value = ''
}
```

模板中所有 `v-if="isVoiceFieldSupported(field)"` 的按钮也一起删。

- [ ] **Step 3: 收敛 `DynamicEntryForm` CSS token**

按以下替换：

```text
var(--font-display, 'SF Pro Display', system-ui) -> var(--xt-font-display)
var(--font-number, 'SF Pro Display', 'DIN Alternate', system-ui) -> var(--xt-font-number)
var(--shadow-card) -> var(--xt-shadow-sm)
border-radius: 16px -> border-radius: var(--xt-radius-2xl)
border-radius: 14px -> border-radius: var(--xt-radius-xl)
border-radius: 12px -> border-radius: var(--xt-radius-lg)
```

- [ ] **Step 4: 收敛 `ShiftReportForm` 数字样式**

替换：

```text
font-family: var(--font-number); -> font-family: var(--xt-font-number);
font-size: 24px; -> font-size: var(--xt-text-2xl);
```

- [ ] **Step 5: 补静态清理测试**

```python
def test_dynamic_entry_form_removes_placeholder_trace_and_voice_stubs() -> None:
    source = _read_repo_file('frontend/src/views/mobile/DynamicEntryForm.vue')

    assert 'entry-external-trace' not in source
    assert 'entry-mes-trace-card' not in source
    assert 'isVoiceFieldSupported' not in source
    assert 'toggleVoicePrefill' not in source
    assert 'voiceListeningField' not in source
```

- [ ] **Step 6: 跑测试和构建**

```bash
cd backend
python -m pytest tests/test_mobile_entry_copy_consistency.py -q
cd ../frontend
npm run build
```

Expected: PASS，前端构建成功。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue frontend/src/views/mobile/ShiftReportForm.vue backend/tests/test_mobile_entry_copy_consistency.py
git commit -m "style: clean mobile dynamic form placeholders and tokens"
```

---

### Task 8: 全量验证和 required checks

**Files:**
- 没有源码修改，除非验证发现问题。

- [ ] **Step 1: 跑移动填报相关后端测试**

```bash
cd backend
python -m pytest tests/test_mobile_report_service.py tests/test_mobile_bootstrap.py tests/test_mobile_scope_isolation.py tests/test_qr_login.py tests/test_mobile_entry_copy_consistency.py -q
```

Expected: PASS。

- [ ] **Step 2: 跑完整后端测试**

```bash
cd backend
python -m pytest
```

Expected: PASS。

- [ ] **Step 3: 跑前端构建**

```bash
cd frontend
npm run build
```

Expected: 构建成功。

- [ ] **Step 4: 跑移动端 E2E smoke**

```bash
cd frontend
npx playwright test e2e/mobile-entry-smoke.spec.js
```

Expected: PASS。

- [ ] **Step 5: 查残留字符串**

PowerShell 环境用：

```powershell
Select-String -Path frontend/src/views/mobile/DynamicEntryForm.vue -Pattern 'entry-external-trace|entry-mes-trace-card|isVoiceFieldSupported|toggleVoicePrefill|voiceListeningField'
```

Expected: zero matches。

```powershell
Select-String -Path frontend/src/views/mobile/UnifiedEntryForm.vue -Pattern 'data: \{ \.\.\.form \}|batch_no.*tracking_card_no|tracking_card_no.*batch_no'
```

Expected: zero matches。

- [ ] **Step 6: 如果验证产生补丁，再单独提交**

```bash
git status --short
git add <only files changed by this plan>
git commit -m "test: verify mobile entry submit and field contracts"
```

没有新改动就跳过。

- [ ] **Step 7: 推送并确认 GitHub required checks**

```bash
git push origin HEAD
```

GitHub Actions 最新 SHA 需要看到：

```text
frontend-build: success
backend-tests: success
compose-smoke: success
```

如果页面还显示 required failed，先看最新 run 的具体失败 job，再决定改哪里。不要把它和移动端提交失败混成同一个问题。

---

## 执行顺序

1. Task 1 写红灯测试，锁定真实提交失败。
2. Task 2 修后端兼容，避免嵌套 payload 被静默丢掉。
3. Task 3 修前端 payload builder 和可见必填校验。
4. Task 4 取消扫码/机台按卷录入的班次报告误锁。
5. Task 5 修字段分类，让扫码身份和业务批号分开。
6. Task 6 用浏览器测试覆盖真实提交路径。
7. Task 7 完成原计划里的视觉和死代码清理。
8. Task 8 做全量验证，确认 required checks 变绿。

## 回滚

每个任务独立提交。后续任务出问题时只 revert 对应提交：

```bash
git revert <commit_sha>
```

不要回滚前面的红灯测试，除非决定放弃对应修复方向。
