# 多角色一线采集端 — 全覆盖落地计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 spec 中所有未实现的功能，让各车间各角色 owner 今天可以完整测试全流程。

**Architecture:** 已有骨架（路由、角色别名、种子脚本、CoilEntryWorkbench、DynamicEntryForm owner-only 模式）。本计划只补缺口：CoilEntryWorkbench 缺失字段与汇总预览、consumable_stat 按车间类型动态字段、QC/称重员按卷选择 UI、车间 QR 码生成与登录流程、按卷提交后实时汇总。

**Tech Stack:** Vue 3 + Element Plus 2.8.4 + plain CSS (xt-tokens) / FastAPI + SQLAlchemy / 遵循 `frontend/DESIGN-MOBILE.md`

**前端规则：** 所有新增/修改的移动端组件必须遵循 `frontend/DESIGN-MOBILE.md` 的 9 条设计规则。关键约束：深色身份栏 + 角色色条、Bahnschrift 等宽数字、48px 触摸目标、一屏一任务、不用 el-form-item label 布局。

---

## Gap 审计摘要

| 缺口 | 严重度 | Task |
|------|--------|------|
| CoilEntryWorkbench 缺 on_machine_time / off_machine_time | 中 | 1 |
| 合金牌号应为下拉选择而非自由文本 | 低 | 1 |
| 班次汇总预览功能缺失 | 高 | 2 |
| consumable_stat 前端 coreSections 为空，无法按车间类型渲染字段 | 高 | 3 |
| QC/称重员无按卷选择 UI（当前走 owner-only 模式但需要选卷） | 高 | 4 |
| 车间 QR 码生成（XT-{workshop}-WS）缺失 | 高 | 5 |
| Login.vue 不处理 workshop 参数 | 高 | 5 |
| QR 码展示/打印页缺失 | 中 | 6 |
| 按卷提交后无实时汇总到 ShiftProductionData | 中 | 7 |
| 种子脚本未执行（需要实际跑一次） | 高 | 8 |

---

### Task 0: 前端 UX 全局优化 — 一目了然

**目标：** 让 15 岁青年也能一眼看懂每个模块是干什么的。优化页面标题、字段标签、按钮文案、模块分组。

**Files:**
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/views/mobile/CoilEntryWorkbench.vue`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Modify: `frontend/src/utils/mobileTransition.js`

**原则：**
- 页面标题用动词开头，说清"我要做什么"（录产量、填能耗、报耗材）
- 字段标签用最短的日常用语，不用专业缩写
- 按钮文案说清点了会发生什么
- 汇总数字用大号 + 单位，一眼看到结果

---

### Task 1: CoilEntryWorkbench 补齐缺失字段

**Files:**
- Modify: `frontend/src/views/mobile/CoilEntryWorkbench.vue`
- Modify: `backend/app/schemas/mobile.py` (MobileCoilEntryPayload)

- [ ] **Step 1: 表单增加 on_machine_time / off_machine_time 字段**

在 `CoilEntryWorkbench.vue` 的 `emptyForm()` 中增加两个时间字段，dialog 表单中增加两个 `el-time-picker`：

```javascript
const emptyForm = () => ({
  tracking_card_no: '',
  alloy_grade: '',
  input_spec: '',
  output_spec: '',
  on_machine_time: null,
  off_machine_time: null,
  input_weight: null,
  output_weight: null,
  operator_notes: '',
})
```

在 dialog 的 `mobile-form-grid` 中，在"输入规格"之前插入两个时间字段：

```html
<div class="mobile-field">
  <label>上机时间</label>
  <el-time-picker v-model="form.on_machine_time" format="HH:mm" value-format="HH:mm" placeholder="默认当前" />
</div>
<div class="mobile-field">
  <label>下机时间</label>
  <el-time-picker v-model="form.off_machine_time" format="HH:mm" value-format="HH:mm" placeholder="可不填" />
</div>
```

- [ ] **Step 2: 合金牌号改为下拉选择**

将合金牌号的 `el-input` 改为 `el-select` 并允许自定义输入：

```html
<div class="mobile-field">
  <label><span class="mobile-required">*</span> 合金牌号</label>
  <el-select v-model="form.alloy_grade" filterable allow-create placeholder="选择或输入">
    <el-option v-for="g in alloyGrades" :key="g" :label="g" :value="g" />
  </el-select>
</div>
```

在 script 中增加常用合金列表：

```javascript
const alloyGrades = ['1060', '1100', '3003', '3004', '3105', '5052', '5083', '5754', '6061', '8011', '8079']
```

- [ ] **Step 3: 后端 schema 增加时间字段**

在 `backend/app/schemas/mobile.py` 的 `MobileCoilEntryPayload` 中增加：

```python
from datetime import date, datetime, time
# ...
class MobileCoilEntryPayload(BaseModel):
    # ... existing fields ...
    on_machine_time: time | None = None
    off_machine_time: time | None = None
```

在 `backend/app/services/mobile_report_service.py` 的 `create_coil_entry` 函数中，WorkOrderEntry 构造增加：

```python
on_machine_time=payload.get('on_machine_time'),
off_machine_time=payload.get('off_machine_time'),
```

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npx vite build`
Expected: 构建成功，无错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/mobile/CoilEntryWorkbench.vue backend/app/schemas/mobile.py backend/app/services/mobile_report_service.py
git commit -m "feat(coil): 补齐上下机时间和合金下拉"
```

---

### Task 2: 班次汇总预览

**Files:**
- Modify: `frontend/src/views/mobile/CoilEntryWorkbench.vue`

- [ ] **Step 1: 增加汇总预览 dialog**

在 CoilEntryWorkbench.vue 的 template 中，在 `coil-actions` div 内增加"班次汇总"按钮，并新增一个 dialog：

```html
<div class="coil-actions">
  <el-button type="primary" size="large" class="xt-pressable" @click="showEntryDialog = true">
    录入新卷
  </el-button>
  <el-button size="large" plain class="xt-pressable" @click="showSummaryDialog = true">
    班次汇总预览
  </el-button>
</div>

<el-dialog
  v-model="showSummaryDialog"
  title="班次汇总预览"
  width="92%"
  class="coil-dialog"
>
  <div class="coil-summary-detail">
    <article class="coil-summary-detail__row">
      <span>总卷数</span><strong>{{ coilList.length }}</strong>
    </article>
    <article class="coil-summary-detail__row">
      <span>总投入</span><strong>{{ totalInput }} kg</strong>
    </article>
    <article class="coil-summary-detail__row">
      <span>总产出</span><strong>{{ totalOutput }} kg</strong>
    </article>
    <article class="coil-summary-detail__row">
      <span>总废料</span><strong>{{ totalScrap }} kg</strong>
    </article>
    <article class="coil-summary-detail__row">
      <span>成品率</span><strong>{{ yieldRate }}%</strong>
    </article>
  </div>
  <template #footer>
    <el-button @click="showSummaryDialog = false">关闭</el-button>
  </template>
</el-dialog>
```

- [ ] **Step 2: 增加 script 变量**

```javascript
const showSummaryDialog = ref(false)
const totalScrap = computed(() => coilList.value.reduce((sum, c) => sum + (Number(c.scrap_weight) || 0), 0))
```

- [ ] **Step 3: 增加汇总详情样式**

```css
.coil-summary-detail {
  display: grid;
  gap: 1px;
  background: var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  overflow: hidden;
}

.coil-summary-detail__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--xt-space-3) var(--xt-space-4);
  background: var(--xt-bg-panel);
}

.coil-summary-detail__row span {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-lg);
}

.coil-summary-detail__row strong {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.012em;
}

.coil-actions {
  position: sticky;
  bottom: calc(var(--xt-tabbar-height) + env(safe-area-inset-bottom, 0px) + 8px);
  z-index: 10;
  display: grid;
  gap: 8px;
}
```

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npx vite build`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/mobile/CoilEntryWorkbench.vue
git commit -m "feat(coil): 班次汇总预览 dialog"
```

---

### Task 3: consumable_stat 按车间类型动态渲染字段

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Modify: `backend/app/core/workshop_templates.py` (读取，不修改)

consumable_stat 的 OWNER_MODE_CONFIG 当前 coreSections 为空。需要根据 bootstrap 返回的 workshop_type 动态构建 coreSections。

- [ ] **Step 1: 将 consumable_stat 的 OWNER_MODE_CONFIG 改为动态计算**

在 DynamicEntryForm.vue 中，将 `ownerModeConfig` computed 改为对 consumable_stat 做特殊处理：

```javascript
const CONSUMABLE_SECTIONS_BY_WORKSHOP = {
  casting: [
    { title: '铸轧辅材', fieldNames: ['liquefied_gas_per_ton', 'titanium_wire_per_ton', 'steel_strip_per_ton', 'magnesium_per_ton', 'manganese_per_ton', 'iron_per_ton', 'copper_per_ton'] },
  ],
  hot_roll: [
    { title: '热轧辅材', fieldNames: ['hot_roll_emulsion_per_ton'] },
  ],
  cold_roll: [
    { title: '冷轧辅材', fieldNames: ['rolling_oil_per_ton', 'filter_agent_per_ton', 'diatomite_per_ton', 'white_earth_per_ton', 'filter_cloth_daily', 'high_temp_tape_daily', 'regen_oil_out', 'regen_oil_in'] },
  ],
  finishing: [
    { title: '精整辅材', fieldNames: ['rolling_oil_per_ton', 'd40_per_ton', 'steel_plate_per_ton', 'steel_strip_per_ton', 'steel_buckle_per_ton', 'high_temp_tape_daily'] },
  ],
}

const ownerModeConfig = computed(() => {
  const bucket = transitionMapping.value.role_bucket
  if (bucket === 'consumable_stat') {
    const workshopType = currentShift.workshop_type || bootstrap.value?.workshop_type || 'casting'
    const base = OWNER_MODE_CONFIG[bucket]
    return {
      ...base,
      coreSections: CONSUMABLE_SECTIONS_BY_WORKSHOP[workshopType] || CONSUMABLE_SECTIONS_BY_WORKSHOP.casting,
    }
  }
  return OWNER_MODE_CONFIG[bucket] || defaultOwnerModeConfig
})
```

- [ ] **Step 2: 确保 bootstrap 和 currentShift 传递 workshop_type**

检查 `currentShift` 对象是否包含 `workshop_type`。在 DynamicEntryForm 的 `loadShiftContext` 中，`fetchCurrentShift()` 返回的数据已包含 `workshop_type` 字段（MobileCurrentShiftOut schema 有此字段）。

如果 `currentShift` 中没有 `workshop_type`，则从 `bootstrap` 中取。在 `loadShiftContext` 中确认 `fetchMobileBootstrap()` 也被调用。

- [ ] **Step 3: 构建验证**

Run: `cd frontend && npx vite build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "feat(consumable): 按车间类型动态渲染耗材字段"
```

---

### Task 4: QC 和称重员按卷选择 UI

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

当前 QC 和称重员走 owner-only 模式，跳过了 work_order 步骤（卷号选择）。但 spec 要求它们按卷录入。需要让这两个角色保留 work_order 步骤。

- [ ] **Step 1: 将 qc 和 weigher 从 ownerOnlyRoleBuckets 中移除**

```javascript
const ownerOnlyRoleBuckets = ['contracts', 'inventory_keeper', 'utility_manager', 'energy_stat', 'maintenance_lead', 'hydraulic_lead', 'consumable_stat']
```

移除 `'qc'` 和 `'weigher'`。这样它们会走标准的 work_order → core → supplemental → review 流程，第一步选卷号，第二步填 qc_grade/qc_notes 或 verified_input_weight/verified_output_weight。

- [ ] **Step 2: 为 qc 和 weigher 配置 coreSections 到非 owner 模式**

在 DynamicEntryForm 中，qc 和 weigher 不再走 owner-only 模式后，它们的字段会通过 `qcFields` 和 `entryFields` computed 自动渲染（因为 workshop_templates 的 role_write 已经配置了这些字段的写权限）。

验证：`qcFields` computed 应该包含 `qc_grade` 和 `qc_notes`（来自 WORK_ORDER_ENTRY_FIELD_NAMES 中 role_write 包含 'qc' 的字段）。

- [ ] **Step 3: 调整 visibleStepItems 中 qc/weigher 的步骤标题**

在 `visibleStepItems` computed 中，非 owner-only 模式下 core 步骤标题是"本卷"，这对 qc/weigher 也合适。无需额外修改。

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npx vite build`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "feat(qc-weigher): 恢复按卷选择流程"
```

---

### Task 5: 车间 QR 码生成 + Login.vue workshop 参数

**Files:**
- Create: `backend/scripts/seed_workshop_qr_codes.py`
- Modify: `frontend/src/views/Login.vue`

- [ ] **Step 1: 创建车间 QR 码种子脚本**

新建 `backend/scripts/seed_workshop_qr_codes.py`：

```python
"""为每个车间生成虚拟设备记录，qr_code 格式 XT-{workshop_code}-WS"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.master import Equipment, Workshop

def main():
    db = SessionLocal()
    try:
        workshops = db.query(Workshop).all()
        created = 0
        for ws in workshops:
            qr_code = f'XT-{ws.code}-WS'
            exists = db.query(Equipment).filter(Equipment.qr_code == qr_code).first()
            if exists:
                print(f'  skip {qr_code} (exists)')
                continue
            eq = Equipment(
                code=f'{ws.code}-WS',
                name=f'{ws.name} 车间入口',
                workshop_id=ws.id,
                equipment_type='virtual_workshop_qr',
                operational_status='running',
                qr_code=qr_code,
                sort_order=9999,
            )
            db.add(eq)
            created += 1
            print(f'  created {qr_code}')
        db.commit()
        print(f'Done. Created {created} workshop QR codes.')
    finally:
        db.close()

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Login.vue 增加 workshop 参数处理**

在 Login.vue 的 `tryQrLogin` 函数之后，增加车间 QR 码处理。车间 QR 码不自动登录，而是预填车间信息并提示输入账号密码：

```javascript
const workshopHint = ref('')

function applyWorkshopContext() {
  const wsCode = resolveQueryValue('workshop')
  if (!wsCode) return
  workshopHint.value = `车间：${wsCode}（请输入该车间角色账号登录）`
}
```

在 `onMounted` 中调用：

```javascript
onMounted(async () => {
  const dingtalkLoggedIn = await tryDingtalkLogin()
  if (dingtalkLoggedIn) return
  await tryQrLogin()
  applyWorkshopContext()
})
```

在 template 中，登录表单上方显示车间提示：

```html
<el-alert v-if="workshopHint" :title="workshopHint" type="info" show-icon :closable="false" style="margin-bottom: 12px" />
```

- [ ] **Step 3: 后端 qr_login 支持车间 QR 码**

在 `backend/app/routers/auth.py` 的 `qr_login` 端点中，当 qr_code 匹配 `XT-*-WS` 格式时，返回车间信息而非直接登录：

检查现有 qr_login 逻辑。如果 equipment.equipment_type == 'virtual_workshop_qr'，返回 `{ "type": "workshop", "workshop_code": ws.code, "workshop_name": ws.name }` 而非 token。

前端 `auth.qrLogin` 需要处理这个分支：如果返回 type=workshop，不设置 session，而是跳转到 `/login?workshop={code}`。

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npx vite build`
Run: `cd backend && python -c "from app.routers.auth import router; print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_workshop_qr_codes.py frontend/src/views/Login.vue backend/app/routers/auth.py
git commit -m "feat(qr): 车间 QR 码生成与登录流程"
```

---

### Task 6: QR 码展示/打印页

**Files:**
- Create: `frontend/src/views/master/QRCodePrint.vue`
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: 创建 QR 码打印页**

新建 `frontend/src/views/master/QRCodePrint.vue`，使用 `qrcode` npm 包（如果没有则用 canvas 手绘或 SVG 方案）。

先检查项目是否已有 qrcode 依赖：`grep qrcode frontend/package.json`

如果没有，使用纯 URL 方案：每个 QR 码的内容是 `{baseUrl}/login?machine={qr_code}`（机台）或 `{baseUrl}/login?workshop={workshop_code}`（车间），页面只展示文本和说明，用户用微信/钉钉扫码工具扫描。

页面结构：
- 从后端 `/equipment` API 获取所有设备列表
- 按车间分组
- 每个设备显示：设备名、QR 码值、对应的登录 URL
- 车间级 QR 码单独一组
- 打印按钮 `window.print()`

```html
<template>
  <div class="qr-print-page">
    <div class="qr-print-header">
      <h1>机台与车间 QR 码</h1>
      <el-button type="primary" @click="handlePrint">打印</el-button>
    </div>
    <div v-for="group in groupedEquipment" :key="group.workshopName" class="qr-print-group">
      <h2>{{ group.workshopName }}</h2>
      <div class="qr-print-grid">
        <div v-for="eq in group.items" :key="eq.id" class="qr-print-card">
          <strong>{{ eq.name }}</strong>
          <code>{{ eq.qr_code }}</code>
          <span class="qr-print-url">{{ buildLoginUrl(eq) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 注册路由**

在 `frontend/src/router/index.js` 中增加：

```javascript
const QRCodePrint = () => import('../views/master/QRCodePrint.vue')
// 在 manage children 中增加：
{ path: 'qr-codes', name: 'admin-qr-codes', component: QRCodePrint, meta: { ...adminMeta, title: 'QR 码管理' } },
```

- [ ] **Step 3: 构建验证**

Run: `cd frontend && npx vite build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/master/QRCodePrint.vue frontend/src/router/index.js
git commit -m "feat(qr): QR 码展示与打印页"
```

---

### Task 7: 按卷提交后实时汇总到 ShiftProductionData

**Files:**
- Modify: `backend/app/services/mobile_report_service.py`

- [ ] **Step 1: 在 create_coil_entry 末尾增加汇总触发**

在 `create_coil_entry` 函数的 `db.commit()` 之后，调用汇总函数：

```python
def _aggregate_coil_to_shift(db: Session, *, business_date: date, shift_id: int, workshop_id: int):
    """将该班次所有 WorkOrderEntry 汇总到 ShiftProductionData"""
    from sqlalchemy import func as sqla_func
    agg = (
        db.query(
            sqla_func.sum(WorkOrderEntry.input_weight).label('total_input'),
            sqla_func.sum(WorkOrderEntry.output_weight).label('total_output'),
            sqla_func.sum(WorkOrderEntry.scrap_weight).label('total_scrap'),
            sqla_func.count(WorkOrderEntry.id).label('coil_count'),
        )
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.shift_id == shift_id,
            WorkOrderEntry.workshop_id == workshop_id,
        )
        .first()
    )
    if not agg or not agg.coil_count:
        return

    spd = (
        db.query(ShiftProductionData)
        .filter(
            ShiftProductionData.business_date == business_date,
            ShiftProductionData.shift_config_id == shift_id,
            ShiftProductionData.workshop_id == workshop_id,
            ShiftProductionData.data_status != 'voided',
        )
        .first()
    )
    if spd:
        spd.input_weight = float(agg.total_input or 0)
        spd.output_weight = float(agg.total_output or 0)
        spd.scrap_weight = float(agg.total_scrap or 0)
        spd.data_source = 'mobile_coil_agg'
    else:
        spd = ShiftProductionData(
            business_date=business_date,
            shift_config_id=shift_id,
            workshop_id=workshop_id,
            input_weight=float(agg.total_input or 0),
            output_weight=float(agg.total_output or 0),
            scrap_weight=float(agg.total_scrap or 0),
            data_source='mobile_coil_agg',
            data_status='pending',
        )
        db.add(spd)
    db.commit()
```

在 `create_coil_entry` 的 `db.commit()` 后调用：

```python
_aggregate_coil_to_shift(
    db,
    business_date=payload['business_date'],
    shift_id=payload['shift_id'],
    workshop_id=entry.workshop_id,
)
```

- [ ] **Step 2: 验证后端导入**

Run: `cd backend && python -c "from app.services.mobile_report_service import create_coil_entry; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/mobile_report_service.py
git commit -m "feat(agg): 按卷提交后实时汇总到 ShiftProductionData"
```

---

### Task 8: 执行种子脚本 + 端到端验证

**Files:**
- Run: `backend/scripts/seed_multi_role_accounts.py`
- Run: `backend/scripts/seed_workshop_qr_codes.py`

- [ ] **Step 1: 执行账号种子脚本**

```bash
cd backend && python scripts/seed_multi_role_accounts.py
```

Expected: 每个车间创建 6 个角色账号 + 3 个全厂账号

- [ ] **Step 2: 执行车间 QR 码种子脚本**

```bash
cd backend && python scripts/seed_workshop_qr_codes.py
```

Expected: 每个车间创建一条 `XT-{code}-WS` 虚拟设备记录

- [ ] **Step 3: 前端完整构建**

```bash
cd frontend && npx vite build
```

Expected: 构建成功

- [ ] **Step 4: 启动后端验证 API**

```bash
cd backend && uvicorn app.main:app --reload
```

验证端点：
- `GET /api/mobile/bootstrap` — 返回 entry_mode 和 user_role
- `GET /api/mobile/current-shift` — 返回班次信息
- `POST /api/mobile/coil-entry` — 创建卷记录
- `GET /api/mobile/coil-list/{date}/{shift_id}` — 返回卷列表

- [ ] **Step 5: 浏览器端到端测试**

用以下账号分别登录测试：
1. 机台账号 → 应进入 CoilEntryWorkbench → 录入一卷 → 查看汇总
2. `{workshop}-EN` → 应进入 DynamicEntryForm 能耗模式
3. `{workshop}-CS` → 应进入 DynamicEntryForm 耗材模式，字段按车间类型渲染
4. `{workshop}-QC` → 应进入 DynamicEntryForm 按卷模式，先选卷号再填质检
5. `FACTORY-UM` → 应进入 DynamicEntryForm 水电气模式
6. `FACTORY-IK` → 应进入 DynamicEntryForm 成品库模式
7. `FACTORY-CT` → 应进入 DynamicEntryForm 计划科模式

- [ ] **Step 6: 最终 Commit**

```bash
git add -A
git commit -m "feat: 多角色一线采集端全覆盖落地"
```
