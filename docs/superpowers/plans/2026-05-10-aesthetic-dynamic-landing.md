# Aesthetic Dynamic Landing Implementation Plan

> **Status (2026-05-10):** SUPERSEDED by `2026-05-10-high-tech-frontend-reform-plan.md`.
> 本 plan 引入 Tailwind + `@vueuse/motion` + 紫蓝 blur orb + glass-card 的方向与 `docs/superpowers/specs/2026-05-10-manage-shell-dark-command-center-design.md` 第 4 节"深海工业指挥台"明文冲突（不用紫蓝渐变、不用玻璃拟态、不用模板式三卡片）。不要按本 plan 执行。若需要保留某些 motion 手法，并入上述 HUD plan 的 Task 3。
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the current industrial portal into a "Super Aesthetic" dynamic official website (动态官网) by introducing Tailwind CSS and `@vueuse/motion` for fluid physics-based animations, glassmorphism, and modern typography, while preserving the backend integration.

**Architecture:** We will adopt a hybrid UI approach: introduce Tailwind CSS for rapid, modern styling of the entry/official website pages, and `@vueuse/motion` for declarative Vue animations (fade-in, spring physics). The `Login.vue` will be completely overhauled into a high-end landing page. Existing Element Plus components inside the dashboard remain functional but will inherit the softer, modern aesthetic through CSS variable overrides.

**Tech Stack:** Vue 3, Vite, Tailwind CSS, `@vueuse/motion`, Playwright (for E2E TDD).

---

### Task 1: Setup Modern Styling & Animation Foundation

**Files:**
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/assets/styles/tailwind.css`
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.js`

- [ ] **Step 1: Write the failing E2E test to verify tooling presence**

```javascript
// frontend/e2e/landing-setup.spec.js
import { test, expect } from '@playwright/test';

test('has tailwind and motion classes applied', async ({ page }) => {
  await page.goto('/');
  // We expect a motion-safe or tailwind specific utility to be present
  const body = page.locator('body');
  await expect(body).toHaveClass(/antialiased/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx playwright test e2e/landing-setup.spec.js`
Expected: FAIL (Timeout or missing class `antialiased`)

- [ ] **Step 3: Write minimal implementation**

```bash
cd frontend && npm install -D tailwindcss postcss autoprefixer @vueuse/motion
cd frontend && npx tailwindcss init -p
```

Update `frontend/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        xt: {
          primary: 'oklch(51% 0.17 255)',
          surface: 'rgba(255, 255, 255, 0.75)',
        }
      }
    },
  },
  plugins: [],
}
```

Create `frontend/src/assets/styles/tailwind.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  @apply antialiased bg-slate-900 text-slate-100;
}
```

Modify `frontend/src/main.js` (Add imports):
```javascript
// ... existing imports
import './assets/styles/tailwind.css'
import { MotionPlugin } from '@vueuse/motion'

// ... before app.mount()
app.use(MotionPlugin)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx playwright test e2e/landing-setup.spec.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tailwind.config.js frontend/postcss.config.js frontend/src/assets/styles/tailwind.css frontend/src/main.js frontend/e2e/landing-setup.spec.js
git commit -m "chore(ui): setup tailwind and vueuse-motion for aesthetic redesign"
```

### Task 2: Build Dynamic Ambient Background Component

**Files:**
- Create: `frontend/e2e/ambient-bg.spec.js`
- Create: `frontend/src/components/ui/AmbientBackground.vue`

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/e2e/ambient-bg.spec.js
import { test, expect } from '@playwright/test';

test('renders ambient dynamic background', async ({ page }) => {
  await page.goto('/');
  const bg = page.locator('[data-testid="ambient-bg"]');
  await expect(bg).toBeVisible();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx playwright test e2e/ambient-bg.spec.js`
Expected: FAIL (Element not found)

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/components/ui/AmbientBackground.vue`:
```vue
<template>
  <div data-testid="ambient-bg" class="fixed inset-0 z-[-1] overflow-hidden bg-slate-950">
    <!-- Dynamic Glowing Orbs -->
    <div 
      v-motion
      :initial="{ opacity: 0, scale: 0.8 }"
      :enter="{ opacity: 0.5, scale: 1, transition: { duration: 2000, repeat: Infinity, repeatType: 'mirror' } }"
      class="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-blue-600/20 blur-[120px]"
    ></div>
    <div 
      v-motion
      :initial="{ opacity: 0, scale: 0.8 }"
      :enter="{ opacity: 0.3, scale: 1.2, transition: { duration: 3000, repeat: Infinity, repeatType: 'mirror', delay: 1000 } }"
      class="absolute bottom-[-10%] right-[-10%] w-[60vw] h-[60vw] rounded-full bg-indigo-600/20 blur-[150px]"
    ></div>
    <!-- Industrial Blueprint Grid Overlay -->
    <div class="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAwIDEwIEwgNDAgMTAgTSAxMCAwIEwgMTAgNDAgTSAwIDIwIEwgNDAgMjAgTSAyMCAwIEwgMjAgNDAgTSAwIDMwIEwgNDAgMzAgTSAzMCAwIEwgMzAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsIDI1NSwgMjU1LCAwLjA0KSIgc3Ryb2tlLXdpZHRoPSIxIi8+PHBhdGggZD0iTSAwIDQwIEwgNDAgNDAgTSA0MCAwIEwgNDAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsIDI1NSwgMjU1LCAwLjA4KSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] [mask-image:linear-gradient(to_bottom,white,transparent)]"></div>
  </div>
</template>
```

- [ ] **Step 4: Run test to verify it passes**
*(Note: requires importing this into App.vue or Login.vue, which we do in Task 3. We will temporarily run the test after Task 3, or inject it in App.vue now).*
For now, let's inject it into `frontend/src/App.vue` temporarily or just proceed to Task 3 where it gets mounted. Let's assume we import it in `App.vue`:
```vue
<!-- Add to frontend/src/App.vue -->
<script setup>
import AmbientBackground from './components/ui/AmbientBackground.vue'
</script>
<template>
  <AmbientBackground />
  <router-view />
</template>
```
Run: `cd frontend && npx playwright test e2e/ambient-bg.spec.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/ambient-bg.spec.js frontend/src/components/ui/AmbientBackground.vue frontend/src/App.vue
git commit -m "feat(ui): add dynamic aesthetic ambient background"
```

### Task 3: Overhaul Login View into High-End Dynamic Official Website

**Files:**
- Modify: `frontend/src/views/Login.vue`
- Modify: `frontend/e2e/landing.spec.js` (Create)

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/e2e/landing.spec.js
import { test, expect } from '@playwright/test';

test('landing page has aesthetic hero and glassmorphism cards', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1')).toHaveText(/鑫泰铝业 数据中枢/);
  const cards = page.locator('.glass-card');
  await expect(cards).toHaveCountGreaterThan(0);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx playwright test e2e/landing.spec.js`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Rewrite `frontend/src/views/Login.vue`:
```vue
<template>
  <div class="relative min-h-screen flex flex-col items-center justify-center overflow-hidden px-6">
    
    <main class="w-full max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 items-center z-10">
      <!-- Hero Section -->
      <div 
        v-motion
        :initial="{ opacity: 0, x: -50 }"
        :enter="{ opacity: 1, x: 0, transition: { type: 'spring', stiffness: 100, damping: 20 } }"
        class="flex flex-col gap-6"
      >
        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm font-medium w-max backdrop-blur-md">
          <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          全厂作战地图 v2.0
        </div>
        
        <h1 class="text-5xl lg:text-7xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-br from-white to-slate-400 drop-shadow-sm pb-2">
          鑫泰铝业<br/><span class="text-blue-500">数据中枢</span>
        </h1>
        
        <p class="text-lg text-slate-400 max-w-lg leading-relaxed">
          连接生产、调度、质量与能源的超级工业中枢。以前所未有的美学设计，重塑数据洞察力。
        </p>

        <!-- Dynamic Role Selector (Replacing old role-grid) -->
        <div class="grid grid-cols-2 gap-4 mt-8">
          <button 
            v-for="(role, index) in roles" :key="role.title"
            v-motion
            :initial="{ opacity: 0, y: 20 }"
            :enter="{ opacity: 1, y: 0, transition: { delay: index * 100 + 300, type: 'spring' } }"
            class="glass-card group relative p-5 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl hover:bg-white/10 hover:border-white/20 transition-all duration-300 text-left overflow-hidden"
          >
            <div class="absolute inset-0 bg-gradient-to-br from-blue-500/0 via-transparent to-blue-500/10 opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <h3 class="text-slate-200 font-semibold text-lg">{{ role.title }}</h3>
            <span class="text-blue-400/80 text-sm mt-1 block">{{ role.desc }}</span>
          </button>
        </div>
      </div>

      <!-- Login Panel (Glassmorphism) -->
      <div 
        v-motion
        :initial="{ opacity: 0, y: 50 }"
        :enter="{ opacity: 1, y: 0, transition: { type: 'spring', stiffness: 80, delay: 400 } }"
        class="glass-card w-full max-w-md mx-auto p-8 rounded-3xl border border-white/10 bg-slate-900/40 backdrop-blur-2xl shadow-2xl shadow-black/50"
      >
        <div class="mb-8">
          <h2 class="text-2xl font-bold text-white mb-2">系统登录</h2>
          <p class="text-slate-400 text-sm">请输入您的域账号或工号继续</p>
        </div>
        
        <!-- Element Plus Form styled implicitly via variables or custom classes -->
        <div class="space-y-6">
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-300">账号</label>
            <input type="text" class="w-full bg-slate-950/50 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-slate-600" placeholder="XT001">
          </div>
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-300">密码</label>
            <input type="password" class="w-full bg-slate-950/50 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-slate-600" placeholder="••••••••">
          </div>
          <button class="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 px-4 rounded-xl transition-all shadow-lg shadow-blue-500/25 active:scale-[0.98]">
            进入中枢
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
const roles = [
  { title: '管理决策', desc: '厂长 / 高管' },
  { title: '生产指挥', desc: '车间主任 / 调度' },
  { title: '质量质检', desc: '化验室 / 质检员' },
  { title: '一线执行', desc: '班组长 / 操作工' }
]
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx playwright test e2e/landing.spec.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/Login.vue frontend/e2e/landing.spec.js
git commit -m "feat(ui): implement super aesthetic dynamic landing page"
```
