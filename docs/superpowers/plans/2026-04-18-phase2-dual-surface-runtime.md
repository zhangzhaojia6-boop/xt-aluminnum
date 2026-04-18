# Phase 2 Dual-Surface Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前内部系统拆成“极简滑屏填报端 + 流程追踪审阅端”，并先核实后端数据链、自动链和权限边界，再做视觉和动效升级。

**Architecture:** 先在后端补齐审阅端运行轨迹 contract，并把 reviewer 旧语义从主路径收口；再在前端把路由、壳层和权限拆成双端，填报端用纯滑屏模块交互，审阅端用独立运行壳层承载机器人流程追踪。所有前端流程表达都必须映射到真实的 service / workflow 输出，避免出现“界面演了一套、后端跑的是另一套”。

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, pytest, Vue 3, Pinia, Vue Router, Element Plus, Playwright, Node test, Docker Compose

---

## File Map

- Modify: `backend/app/core/permissions.py` — 收口 reviewer/manager/dashboard 访问边界
- Modify: `backend/app/routers/dashboard.py` — 审阅端 dashboard 准入逻辑与新 runtime trace 输出
- Modify: `backend/app/schemas/dashboard.py` — Factory / Workshop dashboard response typed contract
- Modify: `backend/app/services/report_service.py` — 构建审阅端流程追踪 trace 与更清晰的数据来源摘要
- Modify: `backend/tests/test_dashboard_routes.py` — dashboard contract 与权限回归
- Modify: `backend/tests/test_reviewer_scope_permissions.py` — reviewer 旧路径收口验证
- Modify: `backend/tests/test_mobile_scope_isolation.py` — 填报端权限边界不回退
- Modify: `frontend/src/stores/auth.js` — 双端能力 getter
- Modify: `frontend/src/router/index.js` — 填报端 / 审阅端独立入口与默认落点
- Create: `frontend/src/views/review/ReviewLayout.vue` — 审阅端独立壳层
- Create: `frontend/src/components/review/AgentRuntimeFlow.vue` — 前后场机器人流程追踪组件
- Create: `frontend/src/components/mobile/MobileSwipeWorkspace.vue` — 填报端滑屏容器
- Create: `frontend/src/utils/mobileSwipe.js` — 滑屏阻尼/吸附纯函数
- Modify: `frontend/src/views/mobile/MobileEntry.vue` — 入口去掉多余 facts / squad 解释
- Modify: `frontend/src/views/mobile/ShiftReportForm.vue` — 班次填报改成滑屏工作台
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue` — owner-only / 工单型填报统一成滑屏页组
- Modify: `frontend/src/views/Layout.vue` — 仅保留管理配置壳层，审阅流量迁移到 review shell
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue` — 接入 runtime trace 与审阅端新层级
- Modify: `frontend/src/views/dashboard/WorkshopDirector.vue` — 接入 runtime trace 与车间运行层
- Modify: `frontend/src/styles.css` — Stripe 风格配色与全局动效收口
- Create: `frontend/tests/mobileSwipe.test.js` — 纯函数级滑屏阻尼测试
- Modify: `frontend/e2e/mobile-entry-smoke.spec.js` — 填报入口断言更新
- Modify: `frontend/e2e/dynamic-entry-layout.spec.js` — 滑屏填报断言更新
- Create: `frontend/e2e/review-runtime.spec.js` — 审阅端流程追踪 smoke
- Modify: `README.md` — 首版发布说明与 Git 初始化说明

## Task 0: Git 初始化与执行基线

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 初始化本地 Git 仓库并建立主分支**

Run:

```powershell
git init
git branch -M main
git status --short
```

Expected:

```text
Initialized empty Git repository
```

- [ ] **Step 2: 把 README 先补上本轮发布口径，避免后续提交没有交付说明**

```md
## Phase 2 首版发布说明

- 双端分离：
  - `/mobile` 只服务主操与专项 owner
  - `/review/*` 只服务管理员与管理层
- 填报端：
  - 改为滑屏模块录入
  - 去掉多余 AI 说明字段
- 审阅端：
  - 新增流程追踪动画
  - 先看来源、流转、风险，再看结果
```

- [ ] **Step 3: 提交初始化基线**

```powershell
git add README.md .gitignore
git commit -m "chore: 初始化仓库并补首版发布说明"
```

## Task 1: 后端核查与审阅端 Runtime Trace Contract

**Files:**
- Modify: `backend/app/core/permissions.py`
- Modify: `backend/app/routers/dashboard.py`
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/report_service.py`
- Modify: `backend/tests/test_dashboard_routes.py`
- Modify: `backend/tests/test_reviewer_scope_permissions.py`
- Modify: `backend/tests/test_mobile_scope_isolation.py`

- [ ] **Step 1: 先写失败测试，锁定审阅端 contract 和 reviewer 收口**

```python
# backend/tests/test_dashboard_routes.py
def test_factory_dashboard_exposes_runtime_trace(monkeypatch) -> None:
    def fake_dashboard(_db, *, target_date):
        return {
            'target_date': '2026-04-18',
            'leader_summary': {'summary_text': '今日正常', 'summary_source': 'deterministic'},
            'leader_metrics': {'today_total_output': 123.4},
            'runtime_trace': {
                'frontline': [
                    {'stage': 'collect', 'label': '主操直录', 'status': 'done', 'count': 6},
                    {'stage': 'owner', 'label': '专项补录', 'status': 'active', 'count': 3},
                ],
                'backline': [
                    {'stage': 'validate', 'label': '自动校验', 'status': 'done', 'count': 9},
                    {'stage': 'report', 'label': '自动汇总', 'status': 'pending', 'count': 1},
                ],
                'delivery': {'status': 'pending', 'missing': ['成品库未补录']},
            },
        }

    monkeypatch.setattr('app.routers.dashboard.report_service.build_factory_dashboard', fake_dashboard)
    client = TestClient(app)
    response = client.get('/api/v1/dashboard/factory-director', params={'target_date': '2026-04-18'})
    payload = response.json()
    assert payload['runtime_trace']['frontline'][0]['stage'] == 'collect'
    assert payload['runtime_trace']['backline'][1]['label'] == '自动汇总'
    assert payload['runtime_trace']['delivery']['status'] == 'pending'


# backend/tests/test_reviewer_scope_permissions.py
def test_reviewer_cannot_enter_manager_review_surface() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_manager_dashboard_access(
            _user(role='reviewer', is_reviewer=True, is_manager=False)
        )

    assert exc.value.status_code == 403
```

- [ ] **Step 2: 跑这组测试，确认现在是红灯**

Run:

```powershell
docker compose run --rm backend sh -lc "pytest backend/tests/test_dashboard_routes.py backend/tests/test_reviewer_scope_permissions.py backend/tests/test_mobile_scope_isolation.py -q"
```

Expected:

```text
FAILED test_factory_dashboard_exposes_runtime_trace
FAILED test_reviewer_cannot_enter_manager_review_surface
```

- [ ] **Step 3: 用最小实现补齐 runtime trace 和 manager-only 审阅准入**

```python
# backend/app/core/permissions.py
def assert_manager_dashboard_access(current_user: User) -> ScopeSummary:
    summary = build_scope_summary(current_user)
    if not summary.is_admin and not summary.is_manager:
        raise _forbidden('Dashboard access denied')
    return summary


# backend/app/routers/dashboard.py
from app.core.permissions import assert_manager_dashboard_access


def _ensure_manager_review_surface(current_user: User):
    return assert_manager_dashboard_access(current_user)


@router.get('/factory-director', response_model=FactoryDashboardResponse, response_model_exclude_none=True)
def factory_director_dashboard(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_manager_review_surface(current_user)
    return report_service.build_factory_dashboard(db, target_date=target_date or date.today())


# backend/app/schemas/dashboard.py
class RuntimeTraceStageOut(BaseModel):
    stage: str
    label: str
    status: str
    count: int | None = None


class RuntimeTraceOut(BaseModel):
    frontline: list[RuntimeTraceStageOut] = []
    backline: list[RuntimeTraceStageOut] = []
    delivery: dict | None = None


class FactoryDashboardResponse(BaseModel):
    target_date: date | None = None
    leader_summary: LeaderSummaryOut | None = None
    leader_metrics: LeaderMetricsOut | None = None
    runtime_trace: RuntimeTraceOut | None = None


class WorkshopDashboardResponse(BaseModel):
    target_date: date | None = None
    workshop_id: int | None = None
    total_output: float | None = None
    month_to_date_output: float | None = None
    runtime_trace: RuntimeTraceOut | None = None


# backend/app/services/report_service.py
def _build_runtime_trace(*, mobile_summary: dict[str, Any], reminder_summary: dict[str, Any], exception_lane: dict[str, Any]) -> dict[str, Any]:
    return {
        'frontline': [
            {'stage': 'collect', 'label': '主操直录', 'status': 'done', 'count': int(mobile_summary.get('reported_shift_count') or 0)},
            {'stage': 'owner', 'label': '专项补录', 'status': 'active' if int(mobile_summary.get('owner_entry_count') or 0) else 'idle', 'count': int(mobile_summary.get('owner_entry_count') or 0)},
        ],
        'backline': [
            {'stage': 'validate', 'label': '自动校验', 'status': 'done', 'count': int(exception_lane.get('returned_shift_count') or 0)},
            {'stage': 'report', 'label': '自动汇总', 'status': 'active' if int(reminder_summary.get('today_reminder_count') or 0) == 0 else 'pending', 'count': int(reminder_summary.get('today_reminder_count') or 0)},
        ],
        'delivery': {
            'status': 'attention' if int(exception_lane.get('unreported_shift_count') or 0) else 'done',
            'missing': _build_delivery_missing_labels(exception_lane=exception_lane),
        },
    }
```

- [ ] **Step 4: 重跑后端目标测试，确认 contract 和权限收口转绿**

Run:

```powershell
docker compose run --rm backend sh -lc "pytest backend/tests/test_dashboard_routes.py backend/tests/test_reviewer_scope_permissions.py backend/tests/test_mobile_scope_isolation.py -q"
```

Expected:

```text
3 passed
```

- [ ] **Step 5: 提交这一小段后端收口**

```powershell
git add backend/app/core/permissions.py backend/app/routers/dashboard.py backend/app/schemas/dashboard.py backend/app/services/report_service.py backend/tests/test_dashboard_routes.py backend/tests/test_reviewer_scope_permissions.py backend/tests/test_mobile_scope_isolation.py
git commit -m "feat: 收口审阅端权限并补齐运行轨迹契约"
```

## Task 2: 双端路由与独立壳层拆分

**Files:**
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/router/index.js`
- Create: `frontend/src/views/review/ReviewLayout.vue`
- Modify: `frontend/src/views/Layout.vue`
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: 先写失败断言，锁定 review shell 和默认落点**

```python
# backend/tests/test_mobile_entry_copy_consistency.py
def test_router_exposes_separate_review_surface() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "const ReviewLayout = () => import('../views/review/ReviewLayout.vue')" in source
    assert "path: '/review'" in source
    assert "zone: 'review'" in source


def test_auth_store_separates_review_access_from_mobile_access() -> None:
    source = _read_repo_file("frontend/src/stores/auth.js")

    assert "canAccessReviewSurface()" in source
    assert "canAccessFillSurface()" in source
```

- [ ] **Step 2: 跑文案/路由测试，确认还没实现**

Run:

```powershell
docker compose run --rm backend sh -lc "pytest backend/tests/test_mobile_entry_copy_consistency.py -q"
```

Expected:

```text
FAILED test_router_exposes_separate_review_surface
FAILED test_auth_store_separates_review_access_from_mobile_access
```

- [ ] **Step 3: 最小拆分路由、getter 和壳层**

```js
// frontend/src/stores/auth.js
canAccessFillSurface() {
  return this.isMobileUser
},
canAccessReviewSurface() {
  return this.isAdmin || this.isManager
},
canAccessDesktopConfig() {
  return this.isAdmin || this.isManager
}


// frontend/src/router/index.js
const ReviewLayout = () => import('../views/review/ReviewLayout.vue')

function defaultLanding(authStore) {
  if (authStore.canAccessFillSurface && !authStore.canAccessReviewSurface) return { name: 'mobile-entry' }
  if (authStore.canAccessReviewSurface) return { name: 'factory-dashboard' }
  if (authStore.canAccessFillSurface) return { name: 'mobile-entry' }
  return { name: 'login' }
}

{
  path: '/review',
  component: ReviewLayout,
  meta: { requiresAuth: true, zone: 'review' },
  children: [
    { path: 'factory', name: 'factory-dashboard', component: FactoryDirector, meta: { access: 'review_surface', title: '厂长审阅端' } },
    { path: 'workshop', name: 'workshop-dashboard', component: WorkshopDirector, meta: { access: 'review_surface', title: '车间审阅端' } },
  ]
}


// frontend/src/views/review/ReviewLayout.vue
<template>
  <el-container class="review-shell" data-testid="review-shell">
    <el-header class="review-shell__header">
      <div>
        <div class="review-shell__eyebrow">审阅端</div>
        <h1>{{ route.meta.title || '运行审阅' }}</h1>
        <p>先看数据从哪来、流到哪、哪里卡住，再看结果。</p>
      </div>
      <div class="review-shell__actions">
        <el-button plain @click="goFill">打开填报入口</el-button>
        <el-button v-if="auth.canAccessDesktopConfig" plain @click="goConfig">系统配置</el-button>
      </div>
    </el-header>
    <el-main class="review-shell__main">
      <router-view />
    </el-main>
  </el-container>
</template>
```

- [ ] **Step 4: 重跑文案/路由测试，确认双端边界成立**

Run:

```powershell
docker compose run --rm backend sh -lc "pytest backend/tests/test_mobile_entry_copy_consistency.py -q"
```

Expected:

```text
all assertions passed
```

- [ ] **Step 5: 提交双端拆分骨架**

```powershell
git add frontend/src/stores/auth.js frontend/src/router/index.js frontend/src/views/review/ReviewLayout.vue frontend/src/views/Layout.vue backend/tests/test_mobile_entry_copy_consistency.py
git commit -m "feat: 拆分填报端与审阅端路由壳层"
```

## Task 3: 填报端滑屏工作台

**Files:**
- Create: `frontend/src/components/mobile/MobileSwipeWorkspace.vue`
- Create: `frontend/src/utils/mobileSwipe.js`
- Create: `frontend/tests/mobileSwipe.test.js`
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/views/mobile/ShiftReportForm.vue`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Modify: `frontend/e2e/mobile-entry-smoke.spec.js`
- Modify: `frontend/e2e/dynamic-entry-layout.spec.js`

- [ ] **Step 1: 先写纯函数测试和 E2E 断言，锁住滑屏体验与减字目标**

```js
// frontend/tests/mobileSwipe.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import { clampSwipeOffset, resolveSwipeSnapIndex } from '../src/utils/mobileSwipe.js'

test('resolveSwipeSnapIndex snaps to next page when drag crosses threshold', () => {
  assert.equal(resolveSwipeSnapIndex({ currentIndex: 0, deltaX: -140, pageWidth: 320, pageCount: 4 }), 1)
})

test('resolveSwipeSnapIndex keeps current page when drag is too short', () => {
  assert.equal(resolveSwipeSnapIndex({ currentIndex: 1, deltaX: -30, pageWidth: 320, pageCount: 4 }), 1)
})

test('clampSwipeOffset applies damped edge resistance', () => {
  assert.equal(clampSwipeOffset({ offset: 40, min: -640, max: 0 }), 16)
})


// frontend/e2e/mobile-entry-smoke.spec.js
await expect(page.getByText('采集清洗小队')).toHaveCount(0)
await expect(page.getByText('分析决策小队')).toHaveCount(0)
await expect(page.getByTestId('mobile-go-report')).toBeVisible()


// frontend/e2e/dynamic-entry-layout.spec.js
await expect(page.getByTestId('mobile-swipe-workspace')).toBeVisible()
await expect(page.getByTestId('swipe-page-indicator')).toContainText('1 /')
```

- [ ] **Step 2: 跑前端纯函数测试和两条 Playwright smoke，确认是红灯**

Run:

```powershell
cd frontend
node --test tests/mobileSwipe.test.js
npx playwright test e2e/mobile-entry-smoke.spec.js e2e/dynamic-entry-layout.spec.js
```

Expected:

```text
ERR_MODULE_NOT_FOUND: Cannot find module '../src/utils/mobileSwipe.js'
1 or more Playwright assertions failed
```

- [ ] **Step 3: 先写滑屏纯函数，再把两类表单换成同一套滑屏壳**

```js
// frontend/src/utils/mobileSwipe.js
export function clampSwipeOffset({ offset, min, max }) {
  if (offset > max) return Math.round((offset - max) * 0.4)
  if (offset < min) return min + Math.round((offset - min) * 0.4)
  return offset
}

export function resolveSwipeSnapIndex({ currentIndex, deltaX, pageWidth, pageCount }) {
  const threshold = Math.max(48, pageWidth * 0.18)
  if (deltaX <= -threshold) return Math.min(currentIndex + 1, pageCount - 1)
  if (deltaX >= threshold) return Math.max(currentIndex - 1, 0)
  return currentIndex
}


// frontend/src/components/mobile/MobileSwipeWorkspace.vue
<template>
  <section class="mobile-swipe-workspace" data-testid="mobile-swipe-workspace">
    <div class="mobile-swipe-workspace__track" :style="trackStyle">
      <article v-for="page in pages" :key="page.key" class="mobile-swipe-workspace__page">
        <slot :name="page.key" />
      </article>
    </div>
    <div class="mobile-swipe-workspace__indicator" data-testid="swipe-page-indicator">
      {{ activeIndex + 1 }} / {{ pages.length }}
    </div>
  </section>
</template>


// frontend/src/views/mobile/MobileEntry.vue
const currentFacts = computed(() => [])
const agentSquads = computed(() => [])
const pageSubtitle = computed(() => '只录本岗原始值，系统自动归档与处理。')


// frontend/src/views/mobile/ShiftReportForm.vue
<MobileSwipeWorkspace :pages="swipePages">
  <template #overview><section class="mobile-swipe-panel">班次信息与提醒</section></template>
  <template #production><section class="mobile-swipe-panel">生产与能耗字段</section></template>
  <template #exception><section class="mobile-swipe-panel">异常与备注</section></template>
  <template #submit><section class="mobile-swipe-panel">提交确认</section></template>
</MobileSwipeWorkspace>


// frontend/src/views/mobile/DynamicEntryForm.vue
<MobileSwipeWorkspace :pages="visibleSwipePages">
  <template #work_order><section class="mobile-swipe-panel">随行卡与工单头信息</section></template>
  <template #core><section class="mobile-swipe-panel">岗位核心原始值</section></template>
  <template #supplemental><section class="mobile-swipe-panel">补充字段与备注</section></template>
  <template #submit><section class="mobile-swipe-panel">提交与连续录入</section></template>
</MobileSwipeWorkspace>
```

- [ ] **Step 4: 重跑 node test、build 和两条 Playwright，确认滑屏工作台可用**

Run:

```powershell
cd frontend
node --test tests/mobileSwipe.test.js
npm run build
npx playwright test e2e/mobile-entry-smoke.spec.js e2e/dynamic-entry-layout.spec.js
```

Expected:

```text
All tests passed
vite build completed
2 passed
```

- [ ] **Step 5: 提交填报端滑屏工作台**

```powershell
git add frontend/src/components/mobile/MobileSwipeWorkspace.vue frontend/src/utils/mobileSwipe.js frontend/tests/mobileSwipe.test.js frontend/src/views/mobile/MobileEntry.vue frontend/src/views/mobile/ShiftReportForm.vue frontend/src/views/mobile/DynamicEntryForm.vue frontend/e2e/mobile-entry-smoke.spec.js frontend/e2e/dynamic-entry-layout.spec.js
git commit -m "feat: 重做填报端滑屏工作台"
```

## Task 4: 审阅端流程追踪动画与 Stripe 风格统一

**Files:**
- Create: `frontend/src/components/review/AgentRuntimeFlow.vue`
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`
- Modify: `frontend/src/views/dashboard/WorkshopDirector.vue`
- Modify: `frontend/src/styles.css`
- Create: `frontend/e2e/review-runtime.spec.js`
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: 先写 smoke 与静态文案断言**

```python
# backend/tests/test_mobile_entry_copy_consistency.py
def test_review_dashboards_use_runtime_trace_component() -> None:
    factory = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")
    workshop = _read_repo_file("frontend/src/views/dashboard/WorkshopDirector.vue")

    assert "AgentRuntimeFlow" in factory
    assert "AgentRuntimeFlow" in workshop
    assert "数据从哪来" in factory
    assert "当前流到哪" in factory


# frontend/e2e/review-runtime.spec.js
import { expect, test } from '@playwright/test'

test('review shell renders cute runtime robots and risk layer', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill('admin')
  await page.getByTestId('login-password').fill('Admin@123456')
  await page.getByTestId('login-submit').click()
  await page.goto('/review/factory')

  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(page.getByTestId('agent-runtime-flow')).toBeVisible()
  await expect(page.getByText('缺报')).toBeVisible()
  await expect(page.getByText('异常')).toBeVisible()
})
```

- [ ] **Step 2: 运行 smoke 和静态断言，确认还没接上**

Run:

```powershell
docker compose run --rm backend sh -lc "pytest backend/tests/test_mobile_entry_copy_consistency.py -q"
cd frontend
npx playwright test e2e/review-runtime.spec.js
```

Expected:

```text
FAILED test_review_dashboards_use_runtime_trace_component
Error: No tests found / or selector not found
```

- [ ] **Step 3: 创建 runtime flow 组件并接入两个 dashboard**

```vue
<!-- frontend/src/components/review/AgentRuntimeFlow.vue -->
<template>
  <section class="agent-runtime-flow" data-testid="agent-runtime-flow">
    <div class="agent-runtime-flow__layer">
      <div class="agent-runtime-flow__title">数据从哪来</div>
      <div class="agent-runtime-flow__bots">
        <article v-for="item in trace.frontline" :key="item.stage" class="agent-runtime-flow__bot" :data-status="item.status">
          <div class="agent-runtime-flow__bubble-face"></div>
          <strong>{{ item.label }}</strong>
          <span>{{ item.count ?? 0 }}</span>
        </article>
      </div>
    </div>
    <div class="agent-runtime-flow__layer">
      <div class="agent-runtime-flow__title">当前流到哪</div>
      <div class="agent-runtime-flow__rail">
        <span v-for="item in trace.backline" :key="item.stage" class="agent-runtime-flow__pulse">{{ item.label }}</span>
      </div>
    </div>
    <div class="agent-runtime-flow__risk">
      <span>缺报</span>
      <span>异常</span>
      <span>退回</span>
      <span>交付风险</span>
    </div>
  </section>
</template>


<!-- frontend/src/views/dashboard/FactoryDirector.vue -->
<AgentRuntimeFlow :trace="data.runtime_trace || fallbackRuntimeTrace" />


<!-- frontend/src/views/dashboard/WorkshopDirector.vue -->
<AgentRuntimeFlow :trace="data.runtime_trace || fallbackRuntimeTrace" compact />
```

- [ ] **Step 4: 用全局样式把 palette 和动效统一到 Stripe 风格**

```css
/* frontend/src/styles.css */
:root {
  --shell-bg: #f6f9fc;
  --panel-bg: rgba(255, 255, 255, 0.92);
  --panel-border: rgba(15, 23, 42, 0.08);
  --brand-blue: #0a5bd8;
  --brand-cyan: #12b5cb;
  --brand-ink: #10233c;
}

.agent-runtime-flow__bot {
  animation: bubbleFloat 3.2s ease-in-out infinite;
}

.agent-runtime-flow__pulse {
  animation: dataPulse 2.6s linear infinite;
}

.mobile-swipe-workspace__track {
  transition: transform 280ms cubic-bezier(0.22, 1, 0.36, 1);
}
```

- [ ] **Step 5: 重跑 build、静态断言和 review smoke**

Run:

```powershell
docker compose run --rm backend sh -lc "pytest backend/tests/test_mobile_entry_copy_consistency.py -q"
cd frontend
npm run build
npx playwright test e2e/review-runtime.spec.js
```

Expected:

```text
passed
vite build completed
1 passed
```

- [ ] **Step 6: 提交审阅端运行图层与视觉统一**

```powershell
git add frontend/src/components/review/AgentRuntimeFlow.vue frontend/src/views/dashboard/FactoryDirector.vue frontend/src/views/dashboard/WorkshopDirector.vue frontend/src/styles.css frontend/e2e/review-runtime.spec.js backend/tests/test_mobile_entry_copy_consistency.py
git commit -m "feat: 增强审阅端运行图层与动效语言"
```

## Task 5: 总验收与浏览器复核

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 跑后端全量测试**

Run:

```powershell
docker compose run --rm backend sh -lc "pytest -q"
```

Expected:

```text
all tests passed
```

- [ ] **Step 2: 跑前端 build 和关键 E2E**

Run:

```powershell
cd frontend
npm run build
npx playwright test e2e/mobile-entry-smoke.spec.js e2e/dynamic-entry-layout.spec.js e2e/review-runtime.spec.js
```

Expected:

```text
vite build completed
all targeted Playwright specs passed
```

- [ ] **Step 3: 做浏览器人工验收**

Checklist:

```text
1. /mobile 入口只看到岗位任务与进入填报按钮
2. 滑屏切页时无明显卡顿，边缘有轻微阻尼
3. /review/factory 先看到来源、流转、风险，再看到结果卡
4. 软萌泡泡机器人有轻微漂浮和数据脉冲，不抢阅读层级
5. 管理员仍可进入配置页，填报用户无法误入审阅端
```

- [ ] **Step 4: 提交总验收记录**

```powershell
git add README.md
git commit -m "docs: 记录 phase2 双端验收结果"
```

## Self-Review

- Spec coverage:
  - 双端分离：Task 2
  - 填报端极简滑屏：Task 3
  - 审阅端流程追踪动画：Task 4
  - 后端核查优先：Task 1
  - Git 初始化与发布说明：Task 0
- Placeholder scan:
  - 本计划没有 `TODO / TBD / implement later` 占位词
  - 每个任务都给出目标文件、示例代码和命令
- Type consistency:
  - runtime trace 统一使用 `runtime_trace`
  - 双端访问统一使用 `canAccessFillSurface / canAccessReviewSurface`
  - 滑屏组件统一命名为 `MobileSwipeWorkspace`
