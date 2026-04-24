# Review Home AI Assistant Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把厂长/管理员审阅首页重构成“双核指挥型”，加入 `轻常驻 + 深展开` 的 AI 助手壳层，并补齐三端自适应、品牌化视觉和后续 API 联通的测试接缝。

**Architecture:** 前端以 `FactoryDirector.vue` 为主入口，拆出首页总览、流程追踪、AI 助手条与展开工作台的独立 review 组件；后端新增 deterministic 的 assistant mock contract，仅用于当前 UI 与测试联通，不接真实模型或 MCP。样式层继续沿用现有 `styles.css` 设计 token，但新增明确的 desktop/tablet/mobile 分层规则，避免三端错位，并把品牌方向统一收成 `现代东方感 + 铝带飞白型 + 青蓝银白` 的图形语汇。

**Tech Stack:** Vue 3 + Element Plus + Vite + Playwright；FastAPI + Pydantic + pytest；现有 Docker Compose 验证链。

---

## File Structure

- Modify: `frontend/src/views/review/ReviewLayout.vue`
  - 收紧审阅端壳层，给首页 AI 助手入口和三端 header 行为留位
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`
  - 首页双核指挥型主页面
- Modify: `frontend/src/views/dashboard/WorkshopDirector.vue`
  - 对齐审阅端视觉和响应式规则，避免首页与车间页割裂
- Modify: `frontend/src/components/review/AgentRuntimeFlow.vue`
  - 升级机器人视觉、流程动画、状态表达
- Create: `frontend/src/components/review/ReviewCommandDeck.vue`
  - 首页第一层总览图形卡
- Create: `frontend/src/components/review/ReviewAssistantDock.vue`
  - 首页轻常驻 AI 助手条
- Create: `frontend/src/components/review/ReviewAssistantWorkbench.vue`
  - 深展开 AI 助手工作台壳层
- Create: `frontend/src/api/assistant.js`
  - 助手 API 模块
- Modify: `frontend/src/styles.css`
  - 首页布局、三端响应式、机器人动画、助手壳层样式与品牌色/艺术字/流线装饰
- Create: `backend/app/schemas/assistant.py`
  - AI 助手 mock contract
- Create: `backend/app/services/assistant_service.py`
  - deterministic mock payload builder
- Create: `backend/app/routers/assistant.py`
  - 助手测试接缝路由
- Modify: `backend/app/main.py`
  - 挂载 assistant router
- Create: `backend/tests/test_assistant_routes.py`
  - 锁定 mock contract
- Modify: `backend/tests/test_dashboard_routes.py`
  - 如首页需要额外能力状态字段，补 route 断言
- Create: `frontend/e2e/review-home-redesign.spec.js`
  - 首页双核布局 + AI 助手入口 + 响应式 smoke

### Task 1: 审阅端壳层与三端布局基线

**Files:**
- Modify: `frontend/src/views/review/ReviewLayout.vue`
- Modify: `frontend/src/styles.css`
- Test: `frontend/e2e/review-home-redesign.spec.js`

- [ ] **Step 1: 先写首页壳层响应式 smoke 断言**

```js
test('review shell switches between desktop and compact layouts', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1024 })
  await page.goto('/review/factory')
  await expect(page.getByTestId('review-shell')).toHaveClass(/review-shell/)

  await page.setViewportSize({ width: 820, height: 1180 })
  await expect(page.getByTestId('review-shell')).toBeVisible()
  await expect(page.getByTestId('review-home-hero')).toBeVisible()
})
```

- [ ] **Step 2: 运行测试确认现在还不满足新布局预期**

Run: `cd frontend && npx playwright test e2e/review-home-redesign.spec.js`

Expected: FAIL，原因类似找不到 `review-home-hero` 或响应式类未生效。

- [ ] **Step 3: 修改审阅壳层，收紧 header 并给首页 AI 助手入口留位**

```vue
<el-header class="review-shell__header review-shell__header--adaptive">
  <div class="review-shell__copy">
    <div class="review-shell__eyebrow">审阅端</div>
    <h1>{{ route.meta.title || '运行审阅' }}</h1>
    <p>{{ compactHeader ? '先看全局和流程。' : '先看今天怎么样，再看数据怎么来的。' }}</p>
  </div>
  <div class="review-shell__actions review-shell__actions--adaptive">
    <el-button v-if="auth.canAccessFillSurface" plain @click="goFill">填报端</el-button>
    <el-button v-if="auth.canAccessDesktopConfig" plain @click="goConfig">系统配置</el-button>
    <el-button type="danger" plain @click="logout">退出</el-button>
  </div>
</el-header>
```

- [ ] **Step 4: 在全局样式中加入 desktop/tablet/mobile 的明确降级规则**

```css
.review-shell__header--adaptive {
  min-height: 108px;
}

@media (max-width: 1100px) {
  .review-shell__header--adaptive {
    padding: 20px 20px 8px;
  }
}

@media (max-width: 760px) {
  .review-shell__header--adaptive,
  .review-shell__actions--adaptive {
    display: grid;
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 5: 重新运行首条 Playwright 用例**

Run: `cd frontend && npx playwright test e2e/review-home-redesign.spec.js`

Expected: 该断言从壳层缺失切换为只剩首页内容断言失败。

### Task 2: 首页双核指挥型重构

**Files:**
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`
- Create: `frontend/src/components/review/ReviewCommandDeck.vue`
- Modify: `frontend/src/styles.css`
- Test: `frontend/e2e/review-home-redesign.spec.js`

- [ ] **Step 1: 先写首页双核结构的失败断言**

```js
test('factory review home shows command deck and runtime flow as twin cores', async ({ page }) => {
  await page.goto('/review/factory')
  await expect(page.getByTestId('review-home-hero')).toBeVisible()
  await expect(page.getByTestId('review-command-deck')).toBeVisible()
  await expect(page.getByTestId('agent-runtime-flow')).toBeVisible()
})
```

- [ ] **Step 2: 运行用例确认首页双核结构还不存在**

Run: `cd frontend && npx playwright test e2e/review-home-redesign.spec.js -g "twin cores"`

Expected: FAIL，缺少 `review-command-deck`。

- [ ] **Step 3: 抽出首页总览卡组件，减少 FactoryDirector 页面噪音**

```vue
<template>
  <section class="review-command-deck" data-testid="review-command-deck">
    <article v-for="card in cards" :key="card.key" class="review-command-deck__card">
      <span>{{ card.label }}</span>
      <strong>{{ card.value }}</strong>
      <small>{{ card.hint }}</small>
    </article>
  </section>
</template>
```

- [ ] **Step 4: 在 FactoryDirector 顶部改成双核首页结构**

```vue
<section class="review-home-hero panel" data-testid="review-home-hero">
  <div class="review-home-hero__grid">
    <ReviewCommandDeck :cards="heroCards" />
    <AgentRuntimeFlow
      title="前场送数，后场处理，今天卡在哪一眼看懂。"
      :trace="runtimeTrace"
      :risks="data.exception_lane || {}"
    />
  </div>
</section>
```

- [ ] **Step 5: 样式里把首屏收成 desktop 双核、tablet 双列、mobile 单列**

```css
.review-home-hero__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 16px;
}

@media (max-width: 1100px) {
  .review-home-hero__grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: 重新运行首页双核 Playwright 用例**

Run: `cd frontend && npx playwright test e2e/review-home-redesign.spec.js -g "twin cores"`

Expected: PASS

### Task 2.5: 品牌化首页视觉与 logo/艺术字占位

**Files:**
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`
- Modify: `frontend/src/views/review/ReviewLayout.vue`
- Modify: `frontend/src/styles.css`
- Test: `frontend/e2e/review-home-redesign.spec.js`

- [ ] **Step 1: 先补品牌占位与视觉结构断言**

```js
test('factory review home exposes branded hero and assistant identity', async ({ page }) => {
  await page.goto('/review/factory')
  await expect(page.getByTestId('review-brand-mark')).toBeVisible()
  await expect(page.getByTestId('review-brand-title')).toContainText('鑫泰铝业')
})
```

- [ ] **Step 2: 运行断言确认当前首页还没有品牌锚点**

Run: `cd frontend && npx playwright test e2e/review-home-redesign.spec.js -g "branded hero"`

Expected: FAIL

- [ ] **Step 3: 在审阅壳层与首页 hero 加入品牌占位**

要求：

- 采用 `图形 + 鑫泰铝业全称`
- 图形方向固定为 `铝带飞白型`
- 标题与副标题保持现代东方感，正文仍然极简

- [ ] **Step 4: 在样式层加入品牌 token**

要求：

- 主色固定为 `青蓝银白`
- 通过流线背景、掠光、高光边框表达“铝材流线”
- 艺术字只用于首页品牌标题，不影响正文可读性

- [ ] **Step 5: 重新运行品牌相关首页断言**

Run: `cd frontend && npx playwright test e2e/review-home-redesign.spec.js -g "branded hero"`

Expected: PASS

### Task 3: 升级流程追踪机器人视觉与动效

**Files:**
- Modify: `frontend/src/components/review/AgentRuntimeFlow.vue`
- Modify: `frontend/src/styles.css`
- Test: `frontend/e2e/review-runtime.spec.js`

- [ ] **Step 1: 先给运行图层补一条视觉结构断言**

```js
test('runtime flow shows upgraded source bots and result stages', async ({ page }) => {
  await page.goto('/review/factory')
  await expect(page.locator('.agent-runtime-flow__bot')).toHaveCount(4)
  await expect(page.locator('.agent-runtime-flow__stage')).toHaveCount(3)
})
```

- [ ] **Step 2: 运行 review-runtime 用例确认当前实现是旧视觉**

Run: `cd frontend && npx playwright test e2e/review-runtime.spec.js`

Expected: 如果结构数量变化不大则先 PASS；若直接 PASS，则继续下一步作为视觉重构保障线。

- [ ] **Step 3: 将机器人外观从“气泡卡”升级成更智能、更柔和的执行单元**

```vue
<div class="agent-runtime-flow__avatar">
  <div class="agent-runtime-flow__antenna" />
  <div class="agent-runtime-flow__face">
    <span class="agent-runtime-flow__eye" />
    <span class="agent-runtime-flow__eye" />
  </div>
</div>
```

- [ ] **Step 4: 用 CSS 补轻量呼吸、数据流、状态变色动画**

```css
.agent-runtime-flow__bot {
  animation: review-bot-float 4.6s ease-in-out infinite;
}

.agent-runtime-flow__pulse::after {
  animation: review-data-pulse 2.4s ease-out infinite;
}
```

- [ ] **Step 5: 重新运行运行图层 Playwright smoke**

Run: `cd frontend && npx playwright test e2e/review-runtime.spec.js`

Expected: PASS

### Task 4: 首页 AI 助手条与深展开工作台壳层

**Files:**
- Create: `frontend/src/components/review/ReviewAssistantDock.vue`
- Create: `frontend/src/components/review/ReviewAssistantWorkbench.vue`
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`
- Create: `frontend/src/api/assistant.js`
- Test: `frontend/e2e/review-home-redesign.spec.js`

- [ ] **Step 1: 先写 AI 助手入口的失败断言**

```js
test('factory review home exposes assistant dock and expandable workbench', async ({ page }) => {
  await page.goto('/review/factory')
  await expect(page.getByTestId('review-assistant-dock')).toBeVisible()
  await page.getByRole('button', { name: '打开 AI 助手' }).click()
  await expect(page.getByTestId('review-assistant-workbench')).toBeVisible()
})
```

- [ ] **Step 2: 运行用例确认助手入口尚未落地**

Run: `cd frontend && npx playwright test e2e/review-home-redesign.spec.js -g "assistant dock"`

Expected: FAIL

- [ ] **Step 3: 新建轻常驻助手条组件**

```vue
<template>
  <section class="review-assistant-dock" data-testid="review-assistant-dock">
    <div class="review-assistant-dock__copy">
      <span>AI 助手已接入</span>
      <strong>问答、搜索、检索、图像生成和自动化入口</strong>
    </div>
    <div class="review-assistant-dock__actions">
      <el-button plain>查今天异常</el-button>
      <el-button plain>搜某卷数据</el-button>
      <el-button plain>生成日报图</el-button>
      <el-button type="primary" @click="$emit('open')">打开 AI 助手</el-button>
    </div>
  </section>
</template>
```

- [ ] **Step 4: 新建深展开工作台壳层，先接 mock API，不接真实模型**

```vue
<template>
  <el-drawer v-model="visible" size="560px" class="review-assistant-workbench" data-testid="review-assistant-workbench">
    <div class="review-assistant-workbench__grid">
      <section v-for="group in capabilityGroups" :key="group.key">
        <h3>{{ group.label }}</h3>
        <p>{{ group.description }}</p>
      </section>
    </div>
  </el-drawer>
</template>
```

- [ ] **Step 5: 新建前端助手 API 模块，为后端 mock route 做接缝**

```js
import request from './request'

export function fetchAssistantCapabilities() {
  return request.get('/assistant/capabilities')
}

export function queryAssistant(payload) {
  return request.post('/assistant/query', payload)
}
```

- [ ] **Step 6: 在 FactoryDirector 挂载助手条与工作台**

```vue
<ReviewAssistantDock @open="assistantVisible = true" />
<ReviewAssistantWorkbench v-model:visible="assistantVisible" />
```

- [ ] **Step 7: 重新运行 AI 助手 Playwright 用例**

Run: `cd frontend && npx playwright test e2e/review-home-redesign.spec.js -g "assistant dock"`

Expected: PASS

### Task 5: 后端助手 mock contract 与 API 测试准备

**Files:**
- Create: `backend/app/schemas/assistant.py`
- Create: `backend/app/services/assistant_service.py`
- Create: `backend/app/routers/assistant.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_assistant_routes.py`

- [ ] **Step 1: 先写后端 route 测试**

```python
def test_assistant_capabilities_returns_mock_contract(client):
    response = client.get("/api/v1/assistant/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is True
    assert "query" in payload["capabilities"]
```

- [ ] **Step 2: 运行新测试确认接口还不存在**

Run: `docker compose run --rm backend sh -lc "pytest tests/test_assistant_routes.py -q"`

Expected: FAIL，提示 route 不存在或测试文件不存在。

- [ ] **Step 3: 定义 deterministic assistant schema**

```python
class AssistantCapabilitiesOut(BaseModel):
    connected: bool
    capabilities: list[str]
    integrations: list[str]


class AssistantQueryResponseOut(BaseModel):
    mode: Literal["answer", "search", "retrieve", "generate_image", "automation"]
    summary: str
    next_actions: list[str]
```

- [ ] **Step 4: 实现 mock service，不接真实 LLM / MCP**

```python
def build_assistant_capabilities() -> AssistantCapabilitiesOut:
    return AssistantCapabilitiesOut(
        connected=True,
        capabilities=["query", "search", "retrieve", "generate_image", "automation"],
        integrations=["dashboard", "history_digest", "runtime_trace", "mock_mcp", "mock_database"],
    )
```

- [ ] **Step 5: 新建 assistant router 并挂到 `/api/v1/assistant`**

```python
router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])

@router.get("/capabilities", response_model=AssistantCapabilitiesOut)
def get_capabilities():
    return build_assistant_capabilities()
```

- [ ] **Step 6: 运行 focused backend tests**

Run: `docker compose run --rm backend sh -lc "pytest tests/test_assistant_routes.py tests/test_dashboard_routes.py -q"`

Expected: PASS

### Task 6: 总验证与视觉验收

**Files:**
- Test: `backend/tests/test_assistant_routes.py`
- Test: `frontend/e2e/review-home-redesign.spec.js`
- Test: `frontend/e2e/review-runtime.spec.js`

- [ ] **Step 1: 跑后端全量**

Run: `docker compose run --rm backend sh -lc "pytest -q"`

Expected: PASS

- [ ] **Step 2: 跑前端构建**

Run: `cd frontend && npm run build`

Expected: Build 成功

- [ ] **Step 3: 跑关键 E2E**

Run: `cd frontend && npx playwright test e2e/review-home-redesign.spec.js e2e/review-runtime.spec.js e2e/mobile-entry-smoke.spec.js`

Expected: PASS

- [ ] **Step 4: 浏览器人工验收三端**

Run:

```bash
http://localhost:61434/review/factory
```

验收点：

- 桌面端：首页总览和流程追踪并列，AI 助手条清楚
- 平板端：首页降列正常，助手不挤爆布局
- 手机端：首页转纵向，文字不堆，流程不变形

- [ ] **Step 5: 记录结果并准备执行收口**

```bash
git status --short
```

Expected: 只包含本轮相关变更
