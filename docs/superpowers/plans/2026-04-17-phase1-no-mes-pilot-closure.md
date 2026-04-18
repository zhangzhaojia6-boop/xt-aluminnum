# Phase 1 无 MES 试点闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有系统收束为“主操手工直录 -> 系统自动校验/汇总/催报 -> 领导驾驶舱”的可上线试点版本，当前前端不显式暴露 MES、扫码补数或 reviewer/statistics 旧流程语义，同时保留后端扩展缝以便后续接入扫码和 MES 自动补数。

**Architecture:** 保留现有 `mobile_report_service`、提醒任务、汇总/报告 Agent 与驾驶舱链路，不删除 `rest_api_mes_adapter`、`mes_sync_service` 或 `work_orders` 后端资产，只通过移动端 bootstrap contract、路由与导航收口把 Phase 1 默认体验锁定为“人工直录优先”。未来扫码/MES 阶段复用保留下来的适配层和高级录入组件，但不进入当前用户主路径。

**Tech Stack:** FastAPI, SQLAlchemy, APScheduler, PostgreSQL, Vue 3, Pinia, Element Plus, pytest, Vite, Docker Compose

## Latest Confirmed Decisions

- 主提报人固定为 `主操 / 机台账号直接报`，不再走调度班长汇总后报。
- 首批一起纳入的专项 owner 包括：电耗、质检、合同、机修、液压，以及成品库/水电气等条线。
- 现有统计岗位完全退出主流程，只保留历史兼容，不再作为系统主叙事。
- 前端必须同时满足两件事：
  1. 清楚展示 `采集清洗小队 -> 分析决策小队` 的智能体联动。
  2. 文案减字、去 AI 套话、视觉更克制更精致，参考 Stripe 的节奏和动效语言，但不做站点克隆。

## Execution Update (2026-04-17)

- 已完成：
  1. `workshop_templates` 为热轧/精整/剪切/铸造等模板拆出 `energy_stat / qc / contracts / maintenance_lead / hydraulic_lead` 的字段责任边界。
  2. 管理端导航已收口到 Phase 1 最小配置集，只保留驾驶舱、车间管理、机台管理、班次配置、车间模板和用户管理。
  3. 移动端入口已改成“岗位直录 + 智能体接力”的表达，并显式展示 `采集清洗小队` 与 `分析决策小队`。
  4. 厂长驾驶舱前台去 MES 化，改为强调 `智能体联动 / 月累计产量 / 数据留存`。
  5. `scope.py` 已补齐专项 owner 作为移动端字段责任人的访问身份，避免出现“角色建好了但 H5 进不去”的断档。
  6. `pilot_schedule_seed.py` 已从“每车间一个白班占位账号”升级为按 `A/B/C × 责任角色` 生成试点应报骨架，开始贴近现场真实排班结构。
  7. `config_readiness_service.py` 已把 `maintenance_lead / hydraulic_lead / contracts / inventory_keeper / utility_manager` 纳入移动端角色识别范围。
  8. `CPK` 已正式切到 `inventory` 模板类型，成品库/计划/公辅字段责任已经拆到对应 owner，不再依赖“统计补总表”。
  9. `real_master_data.py` 现在会直接生成专项 owner 登录账号骨架，现场试点不再需要先手工拼一轮角色账号。
  10. 厂长驾驶舱已开始返回真实的近 7 日趋势和月度/年度归档摘要，不再只写“数据留存”说明文案。
- 仍待继续：
  1. 成品库、水电气等专项 owner 的独立录入口径还需要继续打磨到更细的岗位表单上，目前先完成了模板分流和角色骨架。
  2. 月结/年结的自动文字总结、异常原因归纳和经营建议仍是下一段实施任务，当前已完成趋势与归档基础层。
  3. 仍需做一轮现场试点参数复核，确认各车间具体账号、班次和负责人名单与真实组织完全对齐。

---

## Scope Boundary

- 本计划只覆盖 Phase 1 “先人工直录、再自动汇总、最后领导直达”的试点闭环。
- 本计划不包含对外营销网站、全仓库冗余文件清理、也不在这一轮直接删除后端 reviewer 兼容逻辑。
- `frontend/src/views/mobile/DynamicEntryForm.vue` 与 `backend/app/routers/work_orders.py` 作为 Phase 2 资产暂时保留，但必须退出当前默认操作路径。
- 当前 Codex 工作区被识别为非 git 工作区；下面仍保留标准提交命令，供真实仓库执行时直接使用。

## Current Rollout Diagnosis

- 运行状态已经具备试点基础：容器、健康检查、后端测试、前端构建都已经可通过，阻塞点不是“跑不起来”，而是“产品口径还没收口”。
- Phase 1 的主链路已经在后端存在：`mobile_report_service`、提醒、自动汇总、驾驶舱都能复用。
- 当前最大偏差有两个：
  1. 移动端默认路由落到了工单/随行卡导向的 `DynamicEntryForm.vue`，这和“主操先手工直录”的试点目标不一致。
  2. 桌面端仍然大量暴露 `statistics`、`review`、`处置中心` 等旧流程语义，容易让领导误以为系统仍然依赖中间人工环节。
- MES 不再是 Phase 1 的上线前提。正确做法是“保留接口缝，不把 MES 作为当前前端体验的中心”。
- 结合 `C:\Users\xt\Desktop\统计.md` 的现场现状，当前仓库里最失真的地方不是页面，而是“试点人员/班次/车间配置模型”：
  1. `backend/app/services/pilot_schedule_seed.py` 仍然是“每车间生成一个试点白班账号”的演示逻辑，不符合现场 A/B/C 三班和多责任人结构。
  2. `backend/app/services/real_master_data.py` 已经有较真实的生产车间和设备骨架，但仍然把班组理解成统一的 `白班组 / 小夜班组 / 大夜班组`，没有表达“主操、调度班长、电工班长、质检、成品库、计划科”等责任差异。
  3. `backend/app/services/config_readiness_service.py` 当前只能检查“有没有车间/班次/移动账号/排班”，还不能检查“是否已经按 Phase 1 的直接责任链配置到位”。

## 现场 Pilot 现实口径复盘

### 旧现场链条（来自 `统计.md`）

- 第一层是原始值来源：主操、机修、液压工、电工。
- 第二层是班次协调层：调度班长、电工班长、机修班长、液压班长。
- 第三层是专项汇总层：车间统计、成品库负责人、质检内勤、计划科、水电气负责人、回收车间负责人。
- 第四层是总统计/规划：汇总五张报表和文字日报给领导。

### Phase 1 不应该做的事

- 不要把上面四层人工接力原样搬进系统，否则只是“数字化总统计”，不是“去统计”。
- 不要让第三层、第四层继续承担“人工汇总后再发布”的职责，否则会在系统里重建 reviewer/statistics 老流程。
- 不要为了兼容当前数据库结构，就把所有专项责任都伪装成普通车间白班账号。

### Phase 1 应该重排成什么

- 以“谁对原始值负责”而不是“谁现在在 Excel 里做汇总”来建模。
- 把第一层和第二层中真正掌握原始值的人，定义为 **直接责任人**。
- 把第三层中必须保留的条线，定义为 **专项数据 owner**，但只负责自己那一块原始数据，不负责拼整厂日报。
- 把第四层彻底改成 **系统自动汇总 + 领导驾驶舱输出**，人只看异常，不做人肉接力。

## Phase 1 试点配置建议

### 人员口径

- `主提报人`：主操/机台账号。负责产量、在制、开机状态、投入产出、道次等生产主链原始值。
- `班次协调人`：调度班长。负责盯缺报、补报、异常解释，但不再做人工总汇总。
- `专项 owner`：电工班长、液压班长、机修班长、成品库负责人、质检内勤、计划科负责人、水/电/气负责人。
- `异常管理员`：admin。只处理异常、权限和规则，不做人肉日报。

### 班次口径

- 继续保留 `A 白班 / B 小夜 / C 大夜`，因为这和现场实际一致，也与现有 `ShiftConfig` 兼容。
- 排班不应再是“每车间 1 个试点白班”，而应至少按 `车间/业务单元 × 班次 × 责任类型` 生成应报清单。
- 生产主链数据默认按班次采集；成品库、合同、成品率、水电气等专项数据可以先保留“日填报”或“班后补录”模式，但必须明确 owner。

### 车间/业务单元口径

- `第一批主链车间`：铸锭、铸轧、热轧、冷轧、精整、剪切、回收。这些决定了日产量、月累计、在制料和主产线状态，是 Phase 1 的主战场。
- `第一批专项单元`：成品库、质检、计划科、能耗/水气。这些直接影响库存、成品率、合同与能耗口径，但不应压倒生产主链。
- `后置远景域`：MES、自动扫码补数、排产、合同排序、发货、出入库联动、成本闭环。这些保留接口缝，不进入当前主路径。

## AI 智能体小队设计思路

### 1. 采集清洗小队

- `报工代理`：接住主操/专项 owner 的原始输入，统一格式。
- `校验代理`：校验字段完整性、范围、跨表一致性。
- `补全代理`：补班次、业务日、车间、责任归属等上下文。
- `催报代理`：按应报清单追踪缺报，而不是追着 Excel 汇总人跑。
- `对账代理`：在主链和专项数据之间做轻量核对，先抓异常，不要求一次性全自动闭环。

### 2. 分析决策小队

- `日报代理`：自动生成领导摘要，不再依赖总统计拼文字。
- `预警代理`：盯产量、在制、吨耗、库存、合同缺口等波动。
- `可视化代理`：把结果整理成领导可读的驾驶舱、摘要卡片和趋势图。
- `经营分析代理`：后续承接成本核算、产销平衡、排产建议，但这属于 Phase 2/3。

### 当前阶段的边界

- Phase 1 只需要把“采集清洗小队”做扎实，再给领导一个最小可用的“日报 + 异常 + 看板”输出。
- 现在最重要的不是“多聪明的 AI”，而是“让数据 ownership 一次定对，让系统先掌握真实数据”。

## 下一步应该改什么

- 先改 `pilot_schedule_seed.py`：从“每车间一个白班占位账号”改成“按责任单元生成应报清单”。
- 再改 `real_master_data.py`：保留现有真实生产车间骨架，但补出 Phase 1 所需的直接责任人和专项 owner 结构。
- 最后改 `config_readiness_service.py`：从“有没有数据”升级成“有没有按 Phase 1 责任链配置正确”。

## 需要你拍板的反问

- 反问 1：Phase 1 的主提报人，你是要 **主操/机台账号直接报** 为主，还是要 **调度班长汇总后报** 为主？我现在更倾向前者，因为这才符合“去统计”，但需要你明确。
- 反问 2：第一批必须掌握住的硬数据，是不是先锁成 `日产量/月累计 + 在制料 + 电气能耗 + 成品库出入库 + 成品率 + 合同/余合同` 这几类？液压/机修耗材要不要一起进首批？
- 反问 3：第三层里的 `成品库 / 质检 / 计划科 / 水电气负责人`，你要不要 Phase 1 就纳入系统做专项 owner，还是先把生产主链跑稳，再一条条接入？
- 反问 4：车间试点范围上，你更想先按 `全主价值链` 一次铺开，还是先选最关键、最容易拿到真数据的 `2-3 个车间` 做第一轮？
- 反问 5：你说“去统计”，那现有车间统计在 Phase 1 里是要 **完全退出主流程，只保留抽查**，还是先作为异常兜底角色存在一段时间？

## Missing For Go-Live

- 把 Phase 1 模式固化到后端 bootstrap contract，让前端明确知道“现在是人工直录优先”。
- 把移动端默认填报路径切回简单班次表单，而不是工单驱动表单。
- 把桌面端导航收口到驾驶舱和最小必要配置页，隐藏 review/statistics 旧叙事。
- 把 README 与试点清单改成“先手工直录、后扫码补数、MES 后接”的统一口径。
- 在现有运行环境上做一次完整回归，确认我们收口的是产品语义，而不是破坏可用链路。

## File Map

- `backend/app/config.py`: Phase 1 数据录入模式、扫码开关、MES 展示开关。
- `backend/app/schemas/mobile.py`: `MobileBootstrapOut` 新字段定义。
- `backend/app/services/mobile_report_service.py`: 注入 `data_entry_mode`、`scan_assist_enabled`、`mes_display_enabled`、`phase_notice`。
- `backend/tests/test_mobile_bootstrap.py`: 新 bootstrap contract 回归测试。
- `frontend/src/router/index.js`: 默认移动填报路由改回手工班次表单；桌面默认 landing 不再落到统计/审核路径。
- `frontend/src/views/mobile/MobileEntry.vue`: 展示 Phase 1 提示语，确保入口 CTA 指向手工直录。
- `frontend/src/views/mobile/ShiftReportForm.vue`: 作为 Phase 1 默认表单，文案改成“主操手工录入”。
- `frontend/src/views/Layout.vue`: 导航只保留驾驶舱和主数据维护，去掉 review/statistics 菜单入口。
- `backend/tests/test_mobile_entry_copy_consistency.py`: 通过读源码文本锁住移动入口、桌面导航和文档口径。
- `README.md`: 顶层项目定位与目标用户说明。
- `docs/pilot-readiness-checklist.md`: 落地口径改为“无 MES 也能上线试点”。

### Task 1: 固化 Phase 1 Bootstrap Contract

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/schemas/mobile.py`
- Modify: `backend/app/services/mobile_report_service.py`
- Test: `backend/tests/test_mobile_bootstrap.py`

- [ ] **Step 1: 先写失败测试，锁定 Phase 1 bootstrap 字段**

```python
from app.services import mobile_report_service


def test_get_mobile_bootstrap_exposes_phase1_manual_mode(monkeypatch) -> None:
    current_user = User(
        id=21,
        username='leader-a',
        password_hash='x',
        name='班长A',
        role='team_leader',
        workshop_id=2,
        team_id=10,
        is_mobile_user=True,
        is_active=True,
    )

    monkeypatch.setattr('app.services.mobile_report_service.assert_mobile_user_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.mobile_report_service.dingtalk_service.service.build_mobile_bootstrap',
        lambda *_args, **_kwargs: {
            'entry_mode': 'wecom_h5',
            'dingtalk_enabled': False,
            'user_has_dingtalk_binding': False,
            'current_identity_source': 'wecom_oauth',
        },
    )
    monkeypatch.setattr('app.services.mobile_report_service.build_scope_summary', lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        'app.services.mobile_report_service.scope_to_dict',
        lambda _scope: {
            'role': 'team_leader',
            'data_scope_type': 'self_team',
            'workshop_id': 2,
            'team_id': 10,
            'is_mobile_user': True,
            'is_reviewer': False,
            'is_manager': False,
        },
    )
    monkeypatch.setattr('app.services.mobile_report_service.get_bound_machine_for_user', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.mobile_report_service.settings.MOBILE_DATA_ENTRY_MODE', 'manual_only', raising=False)
    monkeypatch.setattr('app.services.mobile_report_service.settings.MOBILE_SCAN_ASSIST_ENABLED', False, raising=False)
    monkeypatch.setattr('app.services.mobile_report_service.settings.MOBILE_MES_DISPLAY_ENABLED', False, raising=False)

    payload = mobile_report_service.get_mobile_bootstrap(DummyDB(), current_user=current_user)

    assert payload['data_entry_mode'] == 'manual_only'
    assert payload['scan_assist_enabled'] is False
    assert payload['mes_display_enabled'] is False
    assert '主操手工录入' in payload['phase_notice']
```

- [ ] **Step 2: 运行测试，确认当前 contract 还不满足新口径**

```bash
docker compose run --rm backend sh -lc "pytest tests/test_mobile_bootstrap.py -q"
```

Expected: FAIL，报 `KeyError: 'data_entry_mode'`、`AttributeError` 或 `ValidationError`，证明新字段还不存在。

- [ ] **Step 3: 用最小改动补齐设置、schema 和 service**

```python
# backend/app/config.py
MOBILE_DATA_ENTRY_MODE: str = 'manual_only'
MOBILE_SCAN_ASSIST_ENABLED: bool = False
MOBILE_MES_DISPLAY_ENABLED: bool = False

if self.MOBILE_DATA_ENTRY_MODE not in {'manual_only', 'scan_assisted', 'mes_assisted'}:
    issues.append('MOBILE_DATA_ENTRY_MODE must be manual_only, scan_assisted, or mes_assisted')
```

```python
# backend/app/schemas/mobile.py
class MobileBootstrapOut(BaseModel):
    entry_mode: str
    data_entry_mode: str = 'manual_only'
    scan_assist_enabled: bool = False
    mes_display_enabled: bool = False
    phase_notice: str | None = None
    dingtalk_enabled: bool
    user_has_dingtalk_binding: bool
    current_identity_source: str
    current_scope_summary: dict
```

```python
# backend/app/services/mobile_report_service.py
payload['data_entry_mode'] = settings.MOBILE_DATA_ENTRY_MODE
payload['scan_assist_enabled'] = settings.MOBILE_SCAN_ASSIST_ENABLED
payload['mes_display_enabled'] = settings.MOBILE_MES_DISPLAY_ENABLED
payload['phase_notice'] = (
    '当前阶段先由主操手工录入，系统自动校验与汇总；扫码补数与 MES 自动带数后续开放。'
    if settings.MOBILE_DATA_ENTRY_MODE == 'manual_only'
    else '当前入口已开放扩展录入能力，请按现场配置操作。'
)
```

- [ ] **Step 4: 重跑 bootstrap 测试，确认 contract 通过**

```bash
docker compose run --rm backend sh -lc "pytest tests/test_mobile_bootstrap.py -q"
```

Expected: PASS。

- [ ] **Step 5: 提交这一小步**

```bash
git add backend/app/config.py backend/app/schemas/mobile.py backend/app/services/mobile_report_service.py backend/tests/test_mobile_bootstrap.py
git commit -m "feat: expose phase1 mobile bootstrap mode"
```

### Task 2: 恢复移动端默认手工直录路径

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/views/mobile/ShiftReportForm.vue`
- Test: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: 先写前端源码回归测试，锁住默认路由与入口文案**

```python
def test_phase1_mobile_route_uses_shift_report_form() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "const ShiftReportForm = () => import('../views/mobile/ShiftReportForm.vue')" in source
    assert "component: ShiftReportForm" in source


def test_mobile_entry_explains_manual_first_rollout() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "当前阶段先由主操手工录入" in source
```

- [ ] **Step 2: 运行文本测试，确认当前源码仍然走错路径**

```bash
docker compose run --rm backend sh -lc "pytest tests/test_mobile_entry_copy_consistency.py -q"
```

Expected: FAIL，因为当前 `mobile-report-form` 仍指向 `DynamicEntryForm.vue`，且入口文案还没有 Phase 1 提示。

- [ ] **Step 3: 把默认移动填报路由切回简单班次表单，并加入口提示**

```js
// frontend/src/router/index.js
const ShiftReportForm = () => import('../views/mobile/ShiftReportForm.vue')
const DynamicEntryForm = () => import('../views/mobile/DynamicEntryForm.vue')

{
  path: '/mobile/report/:businessDate/:shiftId',
  name: 'mobile-report-form',
  component: ShiftReportForm,
  meta: { requiresAuth: true, title: '班次填报', zone: 'mobile' }
},
{
  path: '/mobile/report-advanced/:businessDate/:shiftId',
  name: 'mobile-report-advanced',
  component: DynamicEntryForm,
  meta: { requiresAuth: true, title: '高级填报', zone: 'mobile' }
},
```

```vue
<!-- frontend/src/views/mobile/MobileEntry.vue -->
<el-alert
  v-if="!authenticating && !authError && bootstrap.phase_notice"
  :title="bootstrap.phase_notice"
  type="success"
  show-icon
  :closable="false"
  class="panel"
/>
```

```js
// frontend/src/views/mobile/MobileEntry.vue
const currentFacts = computed(() => [
  { label: '业务日期', value: current.value?.business_date || '-' },
  { label: '班次', value: current.value?.shift_name || current.value?.shift_code || '-' },
  { label: '车间', value: current.value?.workshop_name || bootstrap.value?.workshop_name || '-' },
  {
    label: '录入方式',
    value: bootstrap.value?.data_entry_mode === 'manual_only' ? '主操手工直录' : '扩展录入'
  },
  { label: '当前状态', value: formatStatusLabel(current.value?.report_status) },
  { label: '当前负责人', value: current.value?.leader_name || auth.displayName }
])
```

```vue
<!-- frontend/src/views/mobile/ShiftReportForm.vue -->
<div>
  <div class="mobile-kicker">班长手机填报</div>
  <h1>班次填报</h1>
  <p>当前阶段先由主操手工录入原始值，系统自动校验、汇总和催报。</p>
</div>
```

- [ ] **Step 4: 重跑文本测试和前端构建**

```bash
docker compose run --rm backend sh -lc "pytest tests/test_mobile_entry_copy_consistency.py -q"
cd frontend && npm run build
```

Expected: 文本测试 PASS，Vite build PASS。

- [ ] **Step 5: 提交这一小步**

```bash
git add frontend/src/router/index.js frontend/src/views/mobile/MobileEntry.vue frontend/src/views/mobile/ShiftReportForm.vue backend/tests/test_mobile_entry_copy_consistency.py
git commit -m "feat: restore manual-first mobile report path"
```

### Task 3: 收口桌面端导航，隐藏旧审核叙事

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/Layout.vue`
- Test: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: 先写文本回归测试，锁住新 landing 和导航范围**

```python
def test_phase1_desktop_landing_skips_statistics_and_review_defaults() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "if (authStore.canAccessStatisticsDashboard) return { name: 'statistics-dashboard' }" not in source
    assert "if (authStore.canAccessReviewDesk) return { name: 'shift-center' }" not in source


def test_phase1_layout_hides_review_and_statistics_navigation() -> None:
    source = _read_repo_file("frontend/src/views/Layout.vue")

    assert "统计观察看板" not in source
    assert "班次观察台" not in source
    assert "差异处置" not in source
```

- [ ] **Step 2: 跑测试，确认当前桌面端仍然暴露旧流程入口**

```bash
docker compose run --rm backend sh -lc "pytest tests/test_mobile_entry_copy_consistency.py -q"
```

Expected: FAIL，因为 `desktopLanding()` 仍然会回落到统计/审核入口，`Layout.vue` 仍然渲染旧菜单。

- [ ] **Step 3: 修改 landing 与导航，只保留驾驶舱和最小必要配置**

```js
// frontend/src/router/index.js
function desktopLanding(authStore) {
  if (authStore.canAccessFactoryDashboard) return { name: 'factory-dashboard' }
  if (authStore.canAccessWorkshopDashboard) return { name: 'workshop-dashboard' }
  if (authStore.isAdmin || authStore.isManager) return { name: 'master-workshop' }
  return { name: 'login' }
}
```

```vue
<!-- frontend/src/views/Layout.vue -->
<div class="brand-subtitle">智能生产数据系统</div>

<template v-if="auth.canAccessFactoryDashboard">
  <el-menu-item index="/dashboard/factory">
    <el-icon><DataBoard /></el-icon>
    <span>厂长驾驶舱</span>
  </el-menu-item>
</template>

<template v-if="auth.canAccessWorkshopDashboard">
  <el-menu-item index="/dashboard/workshop">
    <el-icon><Monitor /></el-icon>
    <span>车间主任看板</span>
  </el-menu-item>
</template>
```

```js
// frontend/src/views/Layout.vue
const roleSubtitle = computed(() => {
  const roleLabel = formatRoleLabel(auth.role)
  const scopeLabel = formatScopeLabel(auth.user?.data_scope_type)
  if (auth.isAdmin) return '管理端：维护主数据、处理异常、查看自动汇总结果'
  if (auth.isManager) return `驾驶舱：${roleLabel}，聚焦聚合结果与异常波动`
  if (auth.isMobileUser) return `填报端：${roleLabel}，岗位直录后系统自动处理`
  return `${roleLabel} / ${scopeLabel}`
})
```

- [ ] **Step 4: 重跑文本测试和前端构建**

```bash
docker compose run --rm backend sh -lc "pytest tests/test_mobile_entry_copy_consistency.py -q"
cd frontend && npm run build
```

Expected: PASS，桌面端默认 landing 不再掉回统计/审核路径，导航构建正常。

- [ ] **Step 5: 提交这一小步**

```bash
git add frontend/src/router/index.js frontend/src/views/Layout.vue backend/tests/test_mobile_entry_copy_consistency.py
git commit -m "refactor: trim desktop pilot navigation"
```

### Task 4: 对齐 README 与试点清单的项目定位

**Files:**
- Modify: `README.md`
- Modify: `docs/pilot-readiness-checklist.md`
- Test: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: 先写文档口径测试，避免后续又漂回“先接 MES”**

```python
def test_readme_describes_phase1_manual_first_scope() -> None:
    readme = _read_repo_file("README.md")

    assert "先由主操手工录入" in readme
    assert "扫码补数" in readme
    assert "MES 接口保留为后续阶段能力" in readme


def test_pilot_checklist_does_not_require_mes_for_phase1_go_live() -> None:
    checklist = _read_repo_file("docs/pilot-readiness-checklist.md")

    assert "Phase 1 不以 MES 联调为上线前提" in checklist
    assert "主操手工直录可独立跑通" in checklist
```

- [ ] **Step 2: 跑测试，确认文档口径还没完全对齐**

```bash
docker compose run --rm backend sh -lc "pytest tests/test_mobile_entry_copy_consistency.py -q"
```

Expected: FAIL，因为现有 README 和 checklist 还没有明确写出“无 MES 也可上线试点”的边界。

- [ ] **Step 3: 更新顶层 README 和试点清单**

```md
<!-- README.md -->
## 当前落地策略

- Phase 1 先由主操手工录入当前班次原始值，系统自动校验、汇总、催报并推送领导驾驶舱。
- 扫码补数和随行卡自动带数属于下一阶段增强能力，本阶段只保留接口和组件资产，不进入默认操作路径。
- MES 接口保留为后续阶段能力；Phase 1 不以 MES 联调作为上线前提。
```

```md
<!-- docs/pilot-readiness-checklist.md -->
## Phase 1 上线口径（2026-04-17）

- [ ] 主操手工直录可独立跑通，不依赖 MES 返回数据
- [ ] 班次提交后 5 分钟内可在驾驶舱看到自动汇总结果
- [ ] 异常数据可自动退回并给出中文修改指引
- [ ] 催报消息可在班次结束后 30 分钟触发
- [ ] Phase 1 不以 MES 联调为上线前提，MES 仅保留后端接口缝
```

- [ ] **Step 4: 重跑文本测试**

```bash
docker compose run --rm backend sh -lc "pytest tests/test_mobile_entry_copy_consistency.py -q"
```

Expected: PASS。

- [ ] **Step 5: 提交这一小步**

```bash
git add README.md docs/pilot-readiness-checklist.md backend/tests/test_mobile_entry_copy_consistency.py
git commit -m "docs: align phase1 manual-first positioning"
```

### Task 5: 做完整验证并给试点上线留最终门槛

**Files:**
- Verify: `backend/tests/test_mobile_bootstrap.py`
- Verify: `backend/tests/test_mobile_entry_copy_consistency.py`
- Verify: `frontend/src/router/index.js`
- Verify: `frontend/src/views/Layout.vue`
- Verify: `frontend/src/views/mobile/MobileEntry.vue`
- Verify: `frontend/src/views/mobile/ShiftReportForm.vue`
- Verify: `README.md`
- Verify: `docs/pilot-readiness-checklist.md`

- [ ] **Step 1: 先跑聚焦回归测试**

```bash
docker compose run --rm backend sh -lc "pytest tests/test_mobile_bootstrap.py tests/test_mobile_entry_copy_consistency.py -q"
```

Expected: PASS。

- [ ] **Step 2: 再跑完整后端测试套件**

```bash
docker compose run --rm backend sh -lc "pytest -q"
```

Expected: PASS，测试数会比当前基线更高，但必须全绿。

- [ ] **Step 3: 重新构建前端**

```bash
cd frontend && npm run build
```

Expected: PASS，没有缺失 import、未使用导出导致的构建错误。

- [ ] **Step 4: 重新拉起并做健康检查**

```bash
docker compose up -d --build
curl.exe -k https://localhost/readyz
```

Expected: 返回 `status=ready`，并且 `hard_gate_passed=true`。

- [ ] **Step 5: 提交最终集成结果**

```bash
git add backend/app/config.py backend/app/schemas/mobile.py backend/app/services/mobile_report_service.py backend/tests/test_mobile_bootstrap.py frontend/src/router/index.js frontend/src/views/Layout.vue frontend/src/views/mobile/MobileEntry.vue frontend/src/views/mobile/ShiftReportForm.vue backend/tests/test_mobile_entry_copy_consistency.py README.md docs/pilot-readiness-checklist.md
git commit -m "feat: close phase1 no-mes pilot gap"
```

## Self-Review

- Spec coverage: “先不上 MES、主操先手工录入、后续再接扫码自动补数” 已分别在 Task 1、Task 2、Task 4 中落地；桌面端旧审核叙事收口在 Task 3；完整验收在 Task 5。
- Placeholder scan: 已检查，无 `TODO`、`TBD`、`implement later`、`similar to Task N` 等占位写法。
- Type consistency: `data_entry_mode`、`scan_assist_enabled`、`mes_display_enabled`、`phase_notice` 在 config、schema、service、frontend copy 和测试中保持同名。
