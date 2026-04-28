# Priority Frontend Visual Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `/login`, `/entry`, `/entry/report/*`, `/entry/advanced/*`, and `/review/brain` with the approved Phase 1 spec while keeping backend interfaces, payload shape, and backend permissions unchanged.

**Architecture:** Reuse the existing Vue + Pinia + mobile API contracts, make `/entry` the canonical mobile surface while preserving `/mobile/*` as redirects, convert login to permission-based auto-routing, and build the new `/review/brain` as a lightweight review-only surface inside the existing desktop shell. For the form flow, reuse the existing dynamic work-order engine and only change presentation, route shape, and UI semantics so “批次号” becomes the sole visible operator clue in Phase 1.

**Tech Stack:** Vue 3, Vue Router 4, Pinia, Element Plus, Vite, Playwright, existing `/mobile/*` and `/work-orders/*` APIs

---

## File Map

### Existing files to modify

- `frontend/src/router/index.js` — make `/entry` the canonical mobile route family, keep `/mobile/*` compatibility redirects, and add `/review/brain` plus login auto-routing behavior.
- `frontend/src/views/Login.vue` — remove manual role-entry emphasis, keep existing auth methods, and redirect to the permission-derived landing route after login.
- `frontend/src/views/mobile/MobileEntry.vue` — reshape the mobile entry home into the `03` shell with KPI strip, quick actions, batch-number-first workflow, and WeChat-sized layout.
- `frontend/src/views/mobile/MobileBottomNav.vue` — keep the mobile nav strictly entry/history/attendance and avoid any desktop/review/admin cross-navigation.
- `frontend/src/views/mobile/ShiftReportForm.vue` — turn the simple route into a thin wrapper around the shared dynamic flow so `/entry/report/*` and `/entry/advanced/*` share one data engine.
- `frontend/src/views/mobile/DynamicEntryForm.vue` — apply the `04` flow presentation, rename visible “随行卡号” semantics to “批次号”, surface system-fill badges, and keep scrap/yield as auto-suggested but operator-overridable.
- `frontend/src/views/Layout.vue` — add a review-brain navigation entry for review-capable desktop users.
- `frontend/src/stores/auth.js` — keep current session logic but reuse existing permission getters consistently for post-login landing.
- `frontend/e2e/login-delivery-smoke.spec.js` — assert login auto-routing behavior without a manual role picker.
- `frontend/e2e/mobile-entry-smoke.spec.js` — assert the new `/entry` shell, WeChat-oriented layout, and absence of review/admin navigation on the mobile surface.
- `frontend/e2e/dynamic-entry-layout.spec.js` — assert the simplified `/entry/report/*` and advanced `/entry/advanced/*` layout entry points.
- `frontend/e2e/zd1-machine-smoke.spec.js` — keep the real machine-account path green after the route change and the batch-number-first relabel.

### New files to create

- `frontend/src/views/review/ReviewBrain.vue` — minimal review brain page with one main question box, at most six suggested actions, evidence sources, recent context summary, and disabled no-op actions.
- `frontend/e2e/review-brain-smoke.spec.js` — assert the `/review/brain` shell, disabled actions, evidence block, and forbidden wording constraints.

---

### Task 1: Canonical `/entry` Routes and Login Auto-Routing

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/Login.vue`
- Test: `frontend/e2e/login-delivery-smoke.spec.js`
- Test: `frontend/e2e/mobile-entry-smoke.spec.js`

- [ ] **Step 1: Write the failing route and login tests**

```js
import { expect, test } from '@playwright/test'

const adminUser = process.env.PLAYWRIGHT_USERNAME || 'admin'
const adminPassword = process.env.PLAYWRIGHT_PASSWORD || 'Admin@123456'
const machineUser = process.env.PLAYWRIGHT_MACHINE_USERNAME || 'ZD-1'
const machinePassword = process.env.PLAYWRIGHT_MACHINE_PASSWORD || '104833'

test('desktop-capable user auto-routes after login without role selection', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(adminUser)
  await page.getByTestId('login-password').fill(adminPassword)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/dashboard\/factory/)
  await expect(page.getByText('进入录入端')).toHaveCount(0)
  await expect(page.getByText('进入审阅端')).toHaveCount(0)
  await expect(page.getByText('进入管理端')).toHaveCount(0)
})

test('machine account auto-routes to canonical /entry path', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(machineUser)
  await page.getByTestId('login-password').fill(machinePassword)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/entry$/)
})
```

- [ ] **Step 2: Run the login-focused tests to verify they fail on the current `/mobile` routing**

Run:

```bash
npm --prefix frontend run e2e -- login-delivery-smoke.spec.js mobile-entry-smoke.spec.js
```

Expected: FAIL because machine login still lands on `/mobile`, and login behavior still follows the old route family.

- [ ] **Step 3: Implement canonical `/entry` paths, `/mobile/*` redirects, and permission-based login landing**

`frontend/src/router/index.js`

```js
function mobileLanding() {
  return { name: 'mobile-entry' }
}

function defaultLanding(authStore) {
  if (authStore.canAccessMobile && !authStore.canAccessDesktop) return mobileLanding()
  const desktop = desktopLanding(authStore)
  if (desktop.name !== 'login') return desktop
  if (authStore.canAccessMobile) return mobileLanding()
  return { name: 'login' }
}

const routes = [
  { path: '/login', name: 'login', component: Login, meta: { title: '登录' } },
  {
    path: '/entry',
    name: 'mobile-entry',
    component: MobileEntry,
    meta: { requiresAuth: true, title: '录入端首页', zone: 'mobile' }
  },
  {
    path: '/entry/report/:businessDate/:shiftId',
    name: 'mobile-report-form',
    component: ShiftReportForm,
    meta: { requiresAuth: true, title: '填报流程页', zone: 'mobile', entryVariant: 'simple' }
  },
  {
    path: '/entry/advanced/:businessDate/:shiftId',
    name: 'mobile-report-form-advanced',
    component: DynamicEntryForm,
    meta: { requiresAuth: true, title: '高级填报流程页', zone: 'mobile', entryVariant: 'advanced' }
  },
  { path: '/mobile', redirect: (to) => ({ name: 'mobile-entry', query: to.query, hash: to.hash }) },
  {
    path: '/mobile/report/:businessDate/:shiftId',
    redirect: (to) => ({
      name: 'mobile-report-form',
      params: to.params,
      query: to.query,
      hash: to.hash
    })
  },
  {
    path: '/mobile/report-advanced/:businessDate/:shiftId',
    redirect: (to) => ({
      name: 'mobile-report-form-advanced',
      params: to.params,
      query: to.query,
      hash: to.hash
    })
  }
]
```

`frontend/src/views/Login.vue`

```js
function defaultLoginLanding() {
  if (auth.canAccessMobile && !auth.canAccessDesktop) return { name: 'mobile-entry' }
  if (auth.canAccessFactoryDashboard) return { name: 'factory-dashboard' }
  if (auth.canAccessWorkshopDashboard) return { name: 'workshop-dashboard' }
  if (auth.canAccessMobile) return { name: 'mobile-entry' }
  return { name: 'login' }
}

function resolveRedirectTarget() {
  if (!(typeof route.query.redirect === 'string' && route.query.redirect)) {
    return defaultLoginLanding()
  }
  return resolveRedirectPath()
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login({ username: form.username, password: form.password })
    ElMessage.success('登录成功')
    await router.replace(resolveRedirectTarget())
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 4: Re-run the login-focused tests until the `/entry` landing and auto-routing pass**

Run:

```bash
npm --prefix frontend run e2e -- login-delivery-smoke.spec.js mobile-entry-smoke.spec.js
```

Expected: PASS with admin landing on `/dashboard/factory` and machine accounts landing on `/entry`.

- [ ] **Step 5: Commit the route and login landing changes**

```bash
git add frontend/src/router/index.js frontend/src/views/Login.vue frontend/e2e/login-delivery-smoke.spec.js frontend/e2e/mobile-entry-smoke.spec.js
git commit -m "feat: make entry routing canonical and auto-route login"
```

### Task 2: Rebuild `/entry` into the `03` WeChat-Sized Entry Shell

**Files:**
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/views/mobile/MobileBottomNav.vue`
- Test: `frontend/e2e/mobile-entry-smoke.spec.js`

- [ ] **Step 1: Write the failing `/entry` shell test**

```js
import { expect, test } from '@playwright/test'

const username = process.env.PLAYWRIGHT_MACHINE_USERNAME || 'ZD-1'
const password = process.env.PLAYWRIGHT_MACHINE_PASSWORD || '104833'

test('entry home shows 03 shell, batch-number-first CTA, and no desktop navigation', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/entry$/)
  await expect(page.getByTestId('mobile-entry')).toBeVisible()
  await expect(page.getByTestId('entry-home-shell')).toBeVisible()
  await expect(page.getByTestId('entry-home-shell')).toContainText('03')
  await expect(page.getByTestId('entry-kpi-strip')).toBeVisible()
  await expect(page.getByTestId('entry-mes-notice')).toContainText('待 MES 对接')
  await expect(page.getByRole('button', { name: '进入后台' })).toHaveCount(0)
})
```

- [ ] **Step 2: Run the `/entry` smoke test to verify the old mobile shell fails it**

Run:

```bash
npm --prefix frontend run e2e -- mobile-entry-smoke.spec.js
```

Expected: FAIL because `MobileEntry.vue` still renders the old “岗位直录” hero and still exposes the desktop button.

- [ ] **Step 3: Implement the new `03` entry shell in `MobileEntry.vue` and trim nav to entry-only concerns**

`frontend/src/views/mobile/MobileEntry.vue`

```vue
<div class="mobile-shell mobile-shell--entry" data-testid="mobile-entry">
  <section class="entry-home-shell" data-testid="entry-home-shell">
    <header class="entry-home-shell__header">
      <div class="entry-home-shell__index">03</div>
      <div>
        <h1>独立填报端首页</h1>
        <p>{{ pageSubtitle }}</p>
      </div>
    </header>

    <div class="entry-kpi-strip" data-testid="entry-kpi-strip">
      <article v-for="item in entryKpis" :key="item.label" class="entry-kpi-tile">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <section class="entry-home-shell__actions">
      <el-button type="primary" size="large" data-testid="mobile-go-report" @click="goReport">
        进入批次号填报
      </el-button>
    </section>

    <section class="entry-home-shell__notice" data-testid="entry-mes-notice">
      <strong>线索追踪（待 MES 对接）</strong>
      <p>当前以批次号作为唯一主线索，扫码可预填，未对接 MES 前不伪造自动追踪。</p>
    </section>
  </section>

  <MobileBottomNav />
</div>
```

`frontend/src/views/mobile/MobileBottomNav.vue`

```js
const navItems = computed(() => [
  { name: 'mobile-entry', label: '入口', badge: 0 },
  { name: 'mobile-attendance-confirm', label: '考勤', badge: pendingAttendanceCount.value },
  { name: 'mobile-report-history', label: '历史', badge: 0 }
])
```

- [ ] **Step 4: Re-run the `/entry` smoke test and confirm the new shell passes at the canonical route**

Run:

```bash
npm --prefix frontend run e2e -- mobile-entry-smoke.spec.js
```

Expected: PASS with `/entry` visible, `03` shell present, and no desktop navigation button.

- [ ] **Step 5: Commit the entry-home shell changes**

```bash
git add frontend/src/views/mobile/MobileEntry.vue frontend/src/views/mobile/MobileBottomNav.vue frontend/e2e/mobile-entry-smoke.spec.js
git commit -m "feat: rebuild entry home for wechat-sized flow"
```

### Task 3: Put `/entry/report/*` on the Shared Flow Engine

**Files:**
- Modify: `frontend/src/views/mobile/ShiftReportForm.vue`
- Modify: `frontend/src/router/index.js`
- Test: `frontend/e2e/dynamic-entry-layout.spec.js`

- [ ] **Step 1: Write the failing simplified-flow test for `/entry/report/*`**

```js
import { expect, test } from '@playwright/test'

test('simple entry route uses the shared flow shell instead of the legacy mobile report form', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill('ZD-1')
  await page.getByTestId('login-password').fill('104833')
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/entry$/)
  await page.goto('/entry/report/2024-05-21/1')

  await expect(page).toHaveURL(/\/entry\/report\/2024-05-21\/1/)
  await expect(page.getByTestId('dynamic-entry-form')).toBeVisible()
  await expect(page.getByTestId('entry-flow-shell')).toBeVisible()
  await expect(page.getByTestId('entry-work-order-card')).toBeVisible()
})
```

- [ ] **Step 2: Run the flow-layout test to verify the legacy `ShiftReportForm.vue` fails it**

Run:

```bash
npm --prefix frontend run e2e -- dynamic-entry-layout.spec.js
```

Expected: FAIL because the simple route still renders the old `ShiftReportForm.vue` shell.

- [ ] **Step 3: Replace the simple route implementation with a thin wrapper around the shared dynamic flow**

`frontend/src/views/mobile/ShiftReportForm.vue`

```vue
<template>
  <DynamicEntryForm />
</template>

<script setup>
import DynamicEntryForm from './DynamicEntryForm.vue'
</script>
```

`frontend/src/router/index.js`

```js
{
  path: '/entry/report/:businessDate/:shiftId',
  name: 'mobile-report-form',
  component: ShiftReportForm,
  meta: { requiresAuth: true, title: '填报流程页', zone: 'mobile', entryVariant: 'simple' }
}
```

- [ ] **Step 4: Re-run the layout test until `/entry/report/*` resolves into the shared flow shell**

Run:

```bash
npm --prefix frontend run e2e -- dynamic-entry-layout.spec.js
```

Expected: PASS with `dynamic-entry-form` visible on the simplified route.

- [ ] **Step 5: Commit the shared-flow routing change**

```bash
git add frontend/src/views/mobile/ShiftReportForm.vue frontend/src/router/index.js frontend/e2e/dynamic-entry-layout.spec.js
git commit -m "refactor: route simple entry flow through shared engine"
```

### Task 4: Apply the `04` Batch-Number-First Flow Presentation

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Test: `frontend/e2e/dynamic-entry-layout.spec.js`
- Test: `frontend/e2e/zd1-machine-smoke.spec.js`

- [ ] **Step 1: Write the failing flow-presentation tests for the visible “批次号” semantics and auto-suggested values**

```js
import { expect, test } from '@playwright/test'

test('advanced entry flow shows 批次号 wording and source badges', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill('ZD-1')
  await page.getByTestId('login-password').fill('104833')
  await page.getByTestId('login-submit').click()
  await page.getByTestId('mobile-go-report').click()

  await expect(page).toHaveURL(/\/entry\/advanced\//)
  await expect(page.getByText('批次号')).toBeVisible()
  await expect(page.getByText('随行卡号')).toHaveCount(0)
  await expect(page.getByTestId('entry-flow-shell')).toContainText('系统回填 / 待确认')
  await expect(page.getByTestId('entry-yield-suggestion')).toBeVisible()
})
```

- [ ] **Step 2: Run the flow tests to verify the current wording and layout still fail**

Run:

```bash
npm --prefix frontend run e2e -- dynamic-entry-layout.spec.js zd1-machine-smoke.spec.js
```

Expected: FAIL because the UI still says “随行卡号”, the sections are old, and the suggested-value badges are missing.

- [ ] **Step 3: Implement the `04` presentation in `DynamicEntryForm.vue` without changing the work-order payload names**

`frontend/src/views/mobile/DynamicEntryForm.vue`

```vue
<div class="mobile-shell mobile-shell--entry-form" data-testid="dynamic-entry-form">
  <section class="entry-flow-shell" data-testid="entry-flow-shell">
    <header class="entry-flow-shell__header">
      <div class="entry-flow-shell__index">04</div>
      <div>
        <h1>{{ route.meta.entryVariant === 'simple' ? '填报流程页' : '高级填报流程页' }}</h1>
        <p>批次号为唯一主线索；系统可回填上一工序可推断字段，主操仍可修改确认。</p>
      </div>
    </header>

    <section class="entry-flow-shell__section" data-testid="entry-work-order-card">
      <label><span class="mobile-required">*</span> 批次号</label>
      <div class="mobile-inline-actions">
        <el-input
          v-model="trackingCardNo"
          placeholder="请输入或扫码批次号"
          :disabled="lookupLoading"
          @keyup.enter="lookupTrackingCard"
        />
        <el-button :loading="lookupLoading" @click="lookupTrackingCard">读取记录</el-button>
        <el-button plain @click="handleScanClick">相机扫码</el-button>
      </div>
      <div class="mobile-field-meta">本轮前端仅突出批次号主线索；底层仍兼容现有 trackingCardNo contract。</div>
    </section>

    <section class="entry-flow-shell__section" data-testid="entry-core-form">
      <div class="entry-source-badge">系统回填 / 待确认</div>
      <div class="entry-yield-suggestion" data-testid="entry-yield-suggestion">
        <span>自动成品率</span>
        <strong>{{ yieldDisplay }}</strong>
      </div>
    </section>
  </section>
</div>
```

`frontend/src/views/mobile/DynamicEntryForm.vue`

```js
const isSimpleVariant = computed(() => route.meta.entryVariant === 'simple')

function trackingCardLabel() {
  return '批次号'
}

function fieldSourceLabel(fieldName) {
  if (['alloy_grade', 'input_spec', 'input_weight'].includes(fieldName) && currentWorkOrder.value?.previous_stage_output) {
    return '系统回填 / 待确认'
  }
  return ''
}
```

- [ ] **Step 4: Re-run the advanced-flow and machine-account tests until the wording, path, and shared flow all pass**

Run:

```bash
npm --prefix frontend run e2e -- dynamic-entry-layout.spec.js zd1-machine-smoke.spec.js
```

Expected: PASS with `/entry/advanced/*` visible, “批次号” shown, and the machine-account path still able to save and submit.

- [ ] **Step 5: Commit the shared flow presentation changes**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue frontend/e2e/dynamic-entry-layout.spec.js frontend/e2e/zd1-machine-smoke.spec.js
git commit -m "feat: present entry flow around batch-number-first workflow"
```

### Task 5: Add the Minimal `/review/brain` Surface

**Files:**
- Create: `frontend/src/views/review/ReviewBrain.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/Layout.vue`
- Create: `frontend/e2e/review-brain-smoke.spec.js`

- [ ] **Step 1: Write the failing `/review/brain` smoke test**

```js
import { expect, test } from '@playwright/test'

const username = process.env.PLAYWRIGHT_USERNAME || 'admin'
const password = process.env.PLAYWRIGHT_PASSWORD || 'Admin@123456'

test('review brain is a minimal q-and-a entry with disabled no-op actions', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()
  await page.goto('/review/brain')

  await expect(page.getByTestId('review-brain-page')).toBeVisible()
  await expect(page.getByTestId('review-brain-question')).toBeVisible()
  await expect(page.getByTestId('review-brain-evidence')).toBeVisible()
  await expect(page.locator('[data-testid="review-brain-action"]')).toHaveCount(6)
  await expect(page.locator('[data-testid="review-brain-action"][disabled]')).toHaveCount(3)
  await expect(page.getByText('自动排产')).toHaveCount(0)
  await expect(page.getByText('自动关闭告警')).toHaveCount(0)
})
```

- [ ] **Step 2: Run the review-brain smoke test to verify the route does not exist yet**

Run:

```bash
npm --prefix frontend run e2e -- review-brain-smoke.spec.js
```

Expected: FAIL with a 404 or route-miss because `/review/brain` is not yet registered.

- [ ] **Step 3: Create the page, register the route, and expose one desktop navigation item**

`frontend/src/views/review/ReviewBrain.vue`

```vue
<template>
  <section class="review-brain-page" data-testid="review-brain-page">
    <header class="review-brain-page__header">
      <div class="review-brain-page__index">11</div>
      <div>
        <h1>AI 总控中心</h1>
        <p>辅助建议 / 系统提示</p>
      </div>
    </header>

    <el-card class="review-brain-page__card">
      <el-input
        type="textarea"
        :rows="5"
        placeholder="请输入今天要追问的问题"
        data-testid="review-brain-question"
      />
    </el-card>

    <el-card class="review-brain-page__card" data-testid="review-brain-evidence">
      <h3>证据来源</h3>
      <ul>
        <li>日报汇总（fallback）</li>
        <li>质量告警（fallback）</li>
        <li>成本解释（fallback）</li>
      </ul>
    </el-card>

    <div class="review-brain-page__actions">
      <el-button v-for="action in actions" :key="action.label" :disabled="action.disabled" data-testid="review-brain-action">
        {{ action.label }}
      </el-button>
    </div>
  </section>
</template>

<script setup>
const actions = [
  { label: '生成今日摘要', disabled: true },
  { label: '查看日报阻塞', disabled: false },
  { label: '查看质量告警', disabled: false },
  { label: '查看成本解释', disabled: false },
  { label: '追问上次结论', disabled: true },
  { label: '复制摘要', disabled: true }
]
</script>
```

`frontend/src/router/index.js`

```js
const ReviewBrain = () => import('../views/review/ReviewBrain.vue')

{
  path: 'review/brain',
  name: 'review-brain',
  component: ReviewBrain,
  meta: { title: 'AI 总控中心', zone: 'desktop', access: 'review' }
}
```

`frontend/src/views/Layout.vue`

```vue
<template v-if="auth.canAccessReviewDesk">
  <el-menu-item index="/review/brain">
    <el-icon><Monitor /></el-icon>
    <span>AI 总控中心</span>
  </el-menu-item>
</template>
```

- [ ] **Step 4: Re-run the review-brain smoke test until the route, nav entry, and disabled actions pass**

Run:

```bash
npm --prefix frontend run e2e -- review-brain-smoke.spec.js
```

Expected: PASS with one main question box, six actions max, and disabled no-op actions visible.

- [ ] **Step 5: Commit the review-brain surface**

```bash
git add frontend/src/views/review/ReviewBrain.vue frontend/src/router/index.js frontend/src/views/Layout.vue frontend/e2e/review-brain-smoke.spec.js
git commit -m "feat: add minimal review brain surface"
```

### Task 6: Full Verification for the Phase 1 Slice

**Files:**
- Modify: none unless verification exposes a defect
- Test: `frontend/e2e/*.spec.js`
- Test: `backend/tests/**`

- [ ] **Step 1: Run the targeted Playwright suite for the touched login and entry flows**

Run:

```bash
npm --prefix frontend run e2e -- login-delivery-smoke.spec.js mobile-entry-smoke.spec.js dynamic-entry-layout.spec.js zd1-machine-smoke.spec.js review-brain-smoke.spec.js
```

Expected: PASS with all touched route, layout, and disabled-action checks green.

- [ ] **Step 2: Run the production frontend build**

Run:

```bash
npm --prefix frontend run build
```

Expected: PASS with Vite completing a production bundle and no component-import errors.

- [ ] **Step 3: Run backend pytest even though the feature is frontend-only, because the delivery checklist requires it**

Run:

```bash
python -m pytest backend/tests -q
```

Expected: PASS, or a clearly reported pre-existing backend failure that is unrelated to the frontend-only change set.

- [ ] **Step 4: If all verification passes, capture the final implementation summary before reporting completion**

```md
- Changed files: router, login, entry home, shared entry flow, review brain, targeted e2e specs.
- Payload/backend changed: no.
- Closest-to-reference pages: /login, /entry, /entry/report/*, /entry/advanced/*, /review/brain.
- Remaining visual gaps: note any page still above the 5% target after manual review.
```

- [ ] **Step 5: Commit the fully verified Phase 1 change set**

```bash
git add frontend/src/router/index.js frontend/src/views/Login.vue frontend/src/views/mobile/MobileEntry.vue frontend/src/views/mobile/MobileBottomNav.vue frontend/src/views/mobile/ShiftReportForm.vue frontend/src/views/mobile/DynamicEntryForm.vue frontend/src/views/review/ReviewBrain.vue frontend/src/views/Layout.vue frontend/e2e/login-delivery-smoke.spec.js frontend/e2e/mobile-entry-smoke.spec.js frontend/e2e/dynamic-entry-layout.spec.js frontend/e2e/zd1-machine-smoke.spec.js frontend/e2e/review-brain-smoke.spec.js
git commit -m "feat: align priority entry and review surfaces with phase 1 spec"
```

---

## Spec Coverage Check

- `/login` auto-routing, no manual role-choice UI: covered by Task 1.
- `/entry` 03 visual shell, WeChat-sized mobile layout, no review/admin exposure: covered by Task 2.
- `/entry/report/*` and `/entry/advanced/*` shared 04 flow shell and batch-number-first semantics: covered by Tasks 3 and 4.
- “批次号” as sole visible clue in Phase 1, keep payload/backend intact: covered by Tasks 1, 3, and 4.
- scrap/yield auto-suggested but still editable: covered by Task 4.
- `/review/brain` minimal question box, <= 6 actions, disabled no-op actions: covered by Task 5.
- build/e2e/pytest completion gates: covered by Task 6.

## Placeholder Scan

- No `TODO`, `TBD`, “implement later”, or unresolved placeholders remain.
- Every code-changing step includes an explicit file path and code excerpt.
- Every test step includes the exact command and the expected failure/pass condition.

## Type and Naming Consistency

- Canonical mobile route names remain `mobile-entry`, `mobile-report-form`, and `mobile-report-form-advanced`; only the visible paths change to `/entry*`.
- The visible operator clue becomes “批次号”, but the current work-order contract can still use `trackingCardNo` internally in Phase 1.
- `/review/brain` is introduced as `review-brain` route name and uses `ReviewBrain.vue` consistently across route, layout, and e2e coverage.
