# Full Platform Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the entire frontend with a unified design system, new component library, merged navigation, AI workstation, and efficiency tools — one-shot full upgrade.

**Architecture:** Four-phase sequential build: (1) design foundation tokens/CSS/logo/motion, (2) Xt* component library + ManageShell + EntryShell + routing, (3) all pages rewritten with new components, (4) AI workstation + efficiency tools + backend APIs + old code cleanup. Each phase produces a working commit.

**Tech Stack:** Vue 3, Element Plus, Pinia, Vue Router, Vite 8, Playwright E2E, CSS Custom Properties, SSE for AI streaming, Python/FastAPI backend for new APIs.

**Spec:** `docs/superpowers/specs/2026-04-27-full-platform-upgrade-design.md`

---

## Phase 1: Design Foundation

### Task 1: Create unified token system

**Files:**
- Create: `frontend/src/design/xt-tokens.css`

- [ ] **Step 1: Create the token file with all CSS custom properties**

```css
/* frontend/src/design/xt-tokens.css */
:root {
  /* ── Colors ── */
  --xt-primary: #0071e3;
  --xt-primary-hover: #0058b0;
  --xt-primary-light: rgba(0, 113, 227, 0.08);

  --xt-gray-50: #f9fafb;
  --xt-gray-100: #f3f4f6;
  --xt-gray-200: #e5e7eb;
  --xt-gray-300: #d1d5db;
  --xt-gray-400: #9ca3af;
  --xt-gray-500: #6b7280;
  --xt-gray-600: #4b5563;
  --xt-gray-700: #374151;
  --xt-gray-800: #1f2937;
  --xt-gray-900: #111827;

  --xt-success: #22c55e;
  --xt-success-light: rgba(34, 197, 94, 0.08);
  --xt-warning: #f59e0b;
  --xt-warning-light: rgba(245, 158, 11, 0.08);
  --xt-danger: #ef4444;
  --xt-danger-light: rgba(239, 68, 68, 0.08);
  --xt-info: #3b82f6;
  --xt-info-light: rgba(59, 130, 246, 0.08);

  /* ── Backgrounds ── */
  --xt-bg-page: #f5f7fa;
  --xt-bg-panel: #ffffff;
  --xt-bg-panel-soft: #fafafa;

  /* ── Text ── */
  --xt-text: #1f2937;
  --xt-text-secondary: #6b7280;
  --xt-text-muted: #9ca3af;
  --xt-text-inverse: #ffffff;

  /* ── Borders ── */
  --xt-border: #e5e7eb;
  --xt-border-light: #f3f4f6;

  /* ── Typography ── */
  --xt-font-body: 'MiSans', -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --xt-font-number: 'DIN Alternate', 'Barlow Condensed', 'SF Pro Display', monospace;
  --xt-font-mono: 'SF Mono', 'Fira Code', 'Consolas', monospace;

  --xt-text-xs: 12px;
  --xt-text-sm: 13px;
  --xt-text-base: 14px;
  --xt-text-lg: 16px;
  --xt-text-xl: 20px;
  --xt-text-2xl: 24px;
  --xt-text-3xl: 32px;

  /* ── Spacing (8px grid) ── */
  --xt-space-1: 4px;
  --xt-space-2: 8px;
  --xt-space-3: 12px;
  --xt-space-4: 16px;
  --xt-space-5: 20px;
  --xt-space-6: 24px;
  --xt-space-8: 32px;
  --xt-space-10: 40px;
  --xt-space-12: 48px;

  /* ── Radius ── */
  --xt-radius-sm: 4px;
  --xt-radius-md: 6px;
  --xt-radius-lg: 8px;
  --xt-radius-xl: 12px;

  /* ── Shadows ── */
  --xt-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --xt-shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
  --xt-shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);

  /* ── Motion ── */
  --xt-motion-fast: 120ms;
  --xt-motion-normal: 200ms;
  --xt-motion-slow: 350ms;
  --xt-ease: cubic-bezier(0.25, 0.1, 0.25, 1);

  /* ── Layout ── */
  --xt-sidebar-width: 240px;
  --xt-sidebar-collapsed: 64px;
  --xt-topbar-height: 56px;
  --xt-content-max: 1400px;
  --xt-tabbar-height: 56px;
}
```

- [ ] **Step 2: Verify the file parses correctly**

Run: `cd frontend && npx vite build --configLoader native 2>&1 | head -5`
Expected: No CSS parse errors (build may fail for other reasons, that's fine)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/design/xt-tokens.css
git commit -m "feat(design): add unified xt-tokens.css design token system"
```

---

### Task 2: Create industrial decoration layer

**Files:**
- Create: `frontend/src/design/industrial.css`

- [ ] **Step 1: Create the industrial decoration CSS**

```css
/* frontend/src/design/industrial.css */

/* Blueprint grid — visible only on large empty areas */
.xt-page {
  position: relative;
}

.xt-page::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 113, 227, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 113, 227, 0.03) 1px, transparent 1px);
  background-size: 48px 48px;
  pointer-events: none;
  z-index: 0;
}

/* Tech accent bar — top of content area */
.xt-page::after {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--xt-primary), transparent 60%);
  pointer-events: none;
  z-index: 100;
}

/* Login page — dark industrial atmosphere */
.xt-login-bg {
  background:
    linear-gradient(135deg, #0a0f1a 0%, #111827 50%, #0a1628 100%);
  position: relative;
  overflow: hidden;
}

.xt-login-bg::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0, 113, 227, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 113, 227, 0.06) 1px, transparent 1px);
  background-size: 32px 32px;
  pointer-events: none;
}

.xt-login-bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 600px 400px at 30% 40%, rgba(0, 113, 227, 0.12), transparent),
    radial-gradient(ellipse 400px 300px at 70% 60%, rgba(59, 130, 246, 0.06), transparent);
  pointer-events: none;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/design/industrial.css
git commit -m "feat(design): add industrial.css decoration layer"
```

---

### Task 3: Create motion system

**Files:**
- Create: `frontend/src/design/xt-motion.css`

- [ ] **Step 1: Create the motion CSS**

```css
/* frontend/src/design/xt-motion.css */

/* Page transition */
.xt-fade-enter-active,
.xt-fade-leave-active {
  transition: opacity var(--xt-motion-normal) var(--xt-ease);
}
.xt-fade-enter-from,
.xt-fade-leave-to {
  opacity: 0;
}

/* Card entrance — staggered */
.xt-rise-enter-active {
  transition:
    opacity var(--xt-motion-normal) var(--xt-ease),
    transform var(--xt-motion-normal) var(--xt-ease);
}
.xt-rise-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

/* Stagger utility: apply --xt-stagger-index via v-for index */
.xt-stagger-enter-active {
  transition:
    opacity var(--xt-motion-normal) var(--xt-ease),
    transform var(--xt-motion-normal) var(--xt-ease);
  transition-delay: calc(var(--xt-stagger-index, 0) * 50ms);
}
.xt-stagger-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

/* Shimmer skeleton */
@keyframes xt-shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.xt-shimmer {
  background: linear-gradient(
    90deg,
    var(--xt-gray-100) 25%,
    var(--xt-gray-200) 50%,
    var(--xt-gray-100) 75%
  );
  background-size: 200% 100%;
  animation: xt-shimmer 1.5s infinite;
  border-radius: var(--xt-radius-sm);
}

/* CountUp number animation helper class */
.xt-countup {
  font-family: var(--xt-font-number);
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/design/xt-motion.css
git commit -m "feat(design): add xt-motion.css animation system"
```

---

### Task 4: Create logo SVG components

**Files:**
- Create: `frontend/src/components/xt/XtLogo.vue`

- [ ] **Step 1: Create the logo component with three variants**

```vue
<!-- frontend/src/components/xt/XtLogo.vue -->
<template>
  <div class="xt-logo" :class="`xt-logo--${variant}`">
    <svg
      v-if="variant === 'icon'"
      viewBox="0 0 32 32"
      class="xt-logo__icon"
      aria-label="鑫泰"
    >
      <!-- Abstract aluminum/metal geometric mark -->
      <path
        d="M16 2L28 8v16l-12 6L4 24V8l12-6z"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      />
      <path
        d="M16 2v28M4 8l24 16M28 8L4 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1"
        opacity="0.4"
      />
      <path
        d="M10 14l6-4 6 4v8l-6 4-6-4v-8z"
        :fill="color ? 'var(--xt-primary)' : 'currentColor'"
        opacity="0.15"
      />
      <path
        d="M10 14l6-4 6 4v8l-6 4-6-4v-8z"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      />
    </svg>
    <svg
      v-else
      viewBox="0 0 32 32"
      class="xt-logo__icon"
      aria-label="鑫泰"
    >
      <path
        d="M16 2L28 8v16l-12 6L4 24V8l12-6z"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      />
      <path
        d="M16 2v28M4 8l24 16M28 8L4 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1"
        opacity="0.4"
      />
      <path
        d="M10 14l6-4 6 4v8l-6 4-6-4v-8z"
        :fill="color ? 'var(--xt-primary)' : 'currentColor'"
        opacity="0.15"
      />
      <path
        d="M10 14l6-4 6 4v8l-6 4-6-4v-8z"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      />
    </svg>
    <span v-if="variant === 'full' || variant === 'compact'" class="xt-logo__text">
      <span class="xt-logo__cn">鑫泰</span>
      <span v-if="variant === 'full'" class="xt-logo__en">XINTAI</span>
    </span>
  </div>
</template>

<script setup>
defineProps({
  variant: { type: String, default: 'full', validator: v => ['full', 'compact', 'icon'].includes(v) },
  color: { type: Boolean, default: true }
})
</script>

<style scoped>
.xt-logo {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  color: var(--xt-text);
}
.xt-logo--icon { gap: 0; }
.xt-logo__icon {
  flex-shrink: 0;
}
.xt-logo--full .xt-logo__icon,
.xt-logo--compact .xt-logo__icon {
  width: 28px;
  height: 28px;
}
.xt-logo--icon .xt-logo__icon {
  width: 32px;
  height: 32px;
}
.xt-logo__text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
}
.xt-logo__cn {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.05em;
}
.xt-logo__en {
  font-size: 9px;
  font-weight: 500;
  letter-spacing: 0.15em;
  color: var(--xt-text-secondary);
  text-transform: uppercase;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/xt/XtLogo.vue
git commit -m "feat(design): add XtLogo component with full/compact/icon variants"
```

---

### Task 5: Create global base styles

**Files:**
- Create: `frontend/src/design/xt-base.css`

- [ ] **Step 1: Create the base reset and global styles**

```css
/* frontend/src/design/xt-base.css */

*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}

body {
  font-family: var(--xt-font-body);
  font-size: var(--xt-text-base);
  line-height: 1.58;
  color: var(--xt-text);
  background: var(--xt-bg-page);
}

#app {
  min-height: 100vh;
  min-height: 100dvh;
}

a {
  color: var(--xt-primary);
  text-decoration: none;
}

img, svg {
  display: block;
  max-width: 100%;
}

button {
  cursor: pointer;
  font: inherit;
}

input, textarea, select {
  font: inherit;
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--xt-gray-300);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--xt-gray-400);
}

/* Element Plus overrides */
:root {
  --el-color-primary: var(--xt-primary);
  --el-color-success: var(--xt-success);
  --el-color-warning: var(--xt-warning);
  --el-color-danger: var(--xt-danger);
  --el-color-info: var(--xt-info);
  --el-border-radius-base: var(--xt-radius-md);
  --el-font-family: var(--xt-font-body);
  --el-font-size-base: var(--xt-text-base);
  --el-border-color: var(--xt-border);
  --el-border-color-light: var(--xt-border-light);
  --el-bg-color: var(--xt-bg-panel);
  --el-text-color-primary: var(--xt-text);
  --el-text-color-regular: var(--xt-text);
  --el-text-color-secondary: var(--xt-text-secondary);
  --el-text-color-placeholder: var(--xt-text-muted);
}

/* Element Plus button refinements */
.el-button {
  border-radius: var(--xt-radius-md);
  transition: all var(--xt-motion-fast) var(--xt-ease);
}

.el-button--primary {
  background: var(--xt-primary);
  border-color: var(--xt-primary);
}

.el-button--primary:hover {
  background: var(--xt-primary-hover);
  border-color: var(--xt-primary-hover);
}

/* Element Plus input refinements */
.el-input__wrapper {
  border-radius: var(--xt-radius-sm);
  transition: box-shadow var(--xt-motion-fast) var(--xt-ease);
}

/* Element Plus table refinements */
.el-table {
  --el-table-border-color: var(--xt-border-light);
  --el-table-header-bg-color: var(--xt-gray-50);
  --el-table-row-hover-bg-color: var(--xt-primary-light);
  font-size: var(--xt-text-sm);
}

.el-table th.el-table__cell {
  font-weight: 600;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/design/xt-base.css
git commit -m "feat(design): add xt-base.css global reset and Element Plus overrides"
```

---

### Task 6: Wire new design system into main.js

**Files:**
- Modify: `frontend/src/main.js`

- [ ] **Step 1: Update main.js imports to use new design files**

Replace the CSS import block in `main.js`. Keep the old imports commented out temporarily so the app still works during migration. The new imports should be:

```js
// New design system
import './design/xt-tokens.css'
import './design/xt-base.css'
import './design/xt-motion.css'
import './design/industrial.css'

// Legacy (remove after full migration)
import './design/tokens.css'
import './design/theme.css'
import './styles.css'
```

- [ ] **Step 2: Verify the app still builds**

Run: `cd frontend && npx vite build --configLoader native 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/main.js
git commit -m "feat(design): wire new xt-* design system into main.js"
```

---

## Phase 2: Component Library + Shell + Routing

### Task 7: Create XtCard component

**Files:**
- Create: `frontend/src/components/xt/XtCard.vue`
- Create: `frontend/e2e/xt-components.spec.js`

- [ ] **Step 1: Write E2E test for XtCard**

```js
// frontend/e2e/xt-components.spec.js
import { expect, test } from '@playwright/test'

test.describe('Xt Component Library', () => {
  test('XtCard renders with title and content', async ({ page }) => {
    await page.setContent(`
      <div id="app"></div>
      <script type="module">
        import { createApp, h } from '/node_modules/vue/dist/vue.esm-browser.js'
        import XtCard from '/src/components/xt/XtCard.vue'
        createApp({ render: () => h(XtCard, { title: 'Test Card' }, { default: () => 'Card body' }) }).mount('#app')
      </script>
    `)
    await expect(page.getByText('Test Card')).toBeVisible()
    await expect(page.getByText('Card body')).toBeVisible()
  })
})
```

Note: This E2E approach may need adjustment based on how Vite serves dev assets. If the above doesn't work, test XtCard by navigating to a page that uses it after it's integrated.

- [ ] **Step 2: Create XtCard component**

```vue
<!-- frontend/src/components/xt/XtCard.vue -->
<template>
  <div class="xt-card" :class="{ 'xt-card--hoverable': hoverable }">
    <div v-if="title || $slots.header" class="xt-card__header">
      <slot name="header">
        <h3 class="xt-card__title">{{ title }}</h3>
      </slot>
    </div>
    <div class="xt-card__body" :style="{ padding }">
      <slot />
    </div>
    <div v-if="$slots.footer" class="xt-card__footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  padding: { type: String, default: '16px' },
  hoverable: { type: Boolean, default: false }
})
</script>

<style scoped>
.xt-card {
  background: var(--xt-bg-panel);
  border-radius: var(--xt-radius-lg);
  box-shadow: var(--xt-shadow-sm);
  overflow: hidden;
  transition: box-shadow var(--xt-motion-fast) var(--xt-ease);
}
.xt-card--hoverable:hover {
  box-shadow: var(--xt-shadow-md);
}
.xt-card__header {
  padding: var(--xt-space-3) var(--xt-space-4);
  border-bottom: 1px solid var(--xt-border-light);
}
.xt-card__title {
  font-size: var(--xt-text-sm);
  font-weight: 600;
  color: var(--xt-text);
}
.xt-card__footer {
  padding: var(--xt-space-3) var(--xt-space-4);
  border-top: 1px solid var(--xt-border-light);
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/xt/XtCard.vue frontend/e2e/xt-components.spec.js
git commit -m "feat(xt): add XtCard component"
```

---

### Task 8: Create XtKpi component

**Files:**
- Create: `frontend/src/components/xt/XtKpi.vue`

- [ ] **Step 1: Create XtKpi component**

```vue
<!-- frontend/src/components/xt/XtKpi.vue -->
<template>
  <div class="xt-kpi" :class="{ 'xt-kpi--loading': loading }">
    <template v-if="loading">
      <div class="xt-kpi__value xt-shimmer" style="width: 60px; height: 28px;" />
      <div class="xt-kpi__label xt-shimmer" style="width: 48px; height: 14px; margin-top: 4px;" />
    </template>
    <template v-else>
      <div class="xt-kpi__value xt-countup">{{ displayValue }}</div>
      <div class="xt-kpi__label">{{ label }}</div>
      <div v-if="trend != null" class="xt-kpi__trend" :class="trendClass">
        <span class="xt-kpi__arrow">{{ trend > 0 ? '↑' : trend < 0 ? '↓' : '→' }}</span>
        <span>{{ Math.abs(trend) }}%</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
  label: { type: String, default: '' },
  trend: { type: Number, default: null },
  loading: { type: Boolean, default: false },
  prefix: { type: String, default: '' },
  suffix: { type: String, default: '' }
})

const displayValue = ref(0)

const trendClass = computed(() => {
  if (props.trend > 0) return 'xt-kpi__trend--up'
  if (props.trend < 0) return 'xt-kpi__trend--down'
  return 'xt-kpi__trend--flat'
})

function animateCount(from, to, duration = 600) {
  const start = performance.now()
  const step = (now) => {
    const progress = Math.min((now - start) / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)
    displayValue.value = Math.round(from + (to - from) * eased)
    if (progress < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

watch(() => props.value, (newVal, oldVal) => {
  animateCount(oldVal || 0, newVal)
})

onMounted(() => {
  if (props.value) animateCount(0, props.value)
})

const formattedValue = computed(() => `${props.prefix}${displayValue.value}${props.suffix}`)
</script>

<style scoped>
.xt-kpi {
  display: flex;
  flex-direction: column;
  padding: var(--xt-space-3) var(--xt-space-4);
}
.xt-kpi__value {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 700;
  color: var(--xt-text);
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.xt-kpi__label {
  font-size: var(--xt-text-xs);
  color: var(--xt-text-secondary);
  margin-top: var(--xt-space-1);
}
.xt-kpi__trend {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: var(--xt-text-xs);
  font-weight: 500;
  margin-top: var(--xt-space-1);
}
.xt-kpi__trend--up { color: var(--xt-success); }
.xt-kpi__trend--down { color: var(--xt-danger); }
.xt-kpi__trend--flat { color: var(--xt-text-muted); }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/xt/XtKpi.vue
git commit -m "feat(xt): add XtKpi component with countUp animation"
```

---

### Task 9: Create XtStatus component

**Files:**
- Create: `frontend/src/components/xt/XtStatus.vue`

- [ ] **Step 1: Create XtStatus component**

```vue
<!-- frontend/src/components/xt/XtStatus.vue -->
<template>
  <span class="xt-status" :class="`xt-status--${tone}`">
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const TONE_MAP = {
  normal: 'info', success: 'success', ready: 'success', live: 'success',
  pending: 'warning', warning: 'warning', risk: 'danger', danger: 'danger',
  blocked: 'danger', rejected: 'danger', done: 'success', info: 'info',
  neutral: 'neutral', closed: 'neutral'
}

const props = defineProps({
  status: { type: String, default: 'neutral' },
  label: { type: String, default: '' }
})

const tone = computed(() => TONE_MAP[props.status] || 'neutral')
</script>

<style scoped>
.xt-status {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: var(--xt-text-xs);
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
}
.xt-status--success {
  background: var(--xt-success-light);
  color: #15803d;
}
.xt-status--warning {
  background: var(--xt-warning-light);
  color: #b45309;
}
.xt-status--danger {
  background: var(--xt-danger-light);
  color: #dc2626;
}
.xt-status--info {
  background: var(--xt-info-light);
  color: #2563eb;
}
.xt-status--neutral {
  background: var(--xt-gray-100);
  color: var(--xt-text-secondary);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/xt/XtStatus.vue
git commit -m "feat(xt): add XtStatus pill component"
```

---

### Task 10: Create XtTable component

**Files:**
- Create: `frontend/src/components/xt/XtTable.vue`

- [ ] **Step 1: Create XtTable component**

```vue
<!-- frontend/src/components/xt/XtTable.vue -->
<template>
  <div class="xt-table-wrap">
    <el-table
      v-loading="loading"
      :data="data"
      :stripe="stripe"
      :border="false"
      :row-class-name="rowClassName"
      class="xt-table"
      @selection-change="$emit('selection-change', $event)"
    >
      <el-table-column v-if="selectable" type="selection" width="44" />
      <slot />
      <template #empty>
        <slot name="empty">
          <div class="xt-table__empty">
            <p>暂无数据</p>
          </div>
        </slot>
      </template>
    </el-table>
    <div v-if="total > 0" class="xt-table__pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="currentPageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        small
        @current-change="$emit('page-change', $event)"
        @size-change="$emit('size-change', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  stripe: { type: Boolean, default: true },
  selectable: { type: Boolean, default: false },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  rowClassName: { type: [String, Function], default: '' }
})

defineEmits(['selection-change', 'page-change', 'size-change'])

const currentPage = ref(props.page)
const currentPageSize = ref(props.pageSize)

watch(() => props.page, v => { currentPage.value = v })
watch(() => props.pageSize, v => { currentPageSize.value = v })
</script>

<style scoped>
.xt-table-wrap {
  background: var(--xt-bg-panel);
  border-radius: var(--xt-radius-lg);
  overflow: hidden;
}
.xt-table {
  --el-table-border-color: var(--xt-border-light);
  --el-table-header-bg-color: var(--xt-gray-50);
  --el-table-row-hover-bg-color: var(--xt-primary-light);
}
.xt-table :deep(th.el-table__cell) {
  font-weight: 600;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.xt-table :deep(td.el-table__cell) {
  font-size: var(--xt-text-sm);
}
.xt-table__empty {
  padding: var(--xt-space-12) 0;
  color: var(--xt-text-muted);
  text-align: center;
}
.xt-table__pagination {
  display: flex;
  justify-content: flex-end;
  padding: var(--xt-space-3) var(--xt-space-4);
  border-top: 1px solid var(--xt-border-light);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/xt/XtTable.vue
git commit -m "feat(xt): add XtTable component with pagination"
```

---

### Task 11: Create XtPageHeader component

**Files:**
- Create: `frontend/src/components/xt/XtPageHeader.vue`

- [ ] **Step 1: Create XtPageHeader component**

```vue
<!-- frontend/src/components/xt/XtPageHeader.vue -->
<template>
  <header class="xt-page-header">
    <div class="xt-page-header__left">
      <span v-if="number" class="xt-page-header__number">{{ number }}</span>
      <div class="xt-page-header__titles">
        <h1 class="xt-page-header__title">{{ title }}</h1>
        <span v-if="subtitle" class="xt-page-header__subtitle">{{ subtitle }}</span>
      </div>
    </div>
    <div v-if="$slots.actions" class="xt-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
  <nav v-if="$slots.breadcrumb" class="xt-page-header__breadcrumb">
    <slot name="breadcrumb" />
  </nav>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  number: { type: String, default: '' }
})
</script>

<style scoped>
.xt-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--xt-space-4) 0;
  gap: var(--xt-space-4);
}
.xt-page-header__left {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
}
.xt-page-header__number {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-3xl);
  font-weight: 700;
  color: var(--xt-primary);
  line-height: 1;
  opacity: 0.7;
}
.xt-page-header__titles {
  display: flex;
  flex-direction: column;
}
.xt-page-header__title {
  font-size: var(--xt-text-xl);
  font-weight: 600;
  color: var(--xt-text);
  line-height: 1.3;
}
.xt-page-header__subtitle {
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.xt-page-header__actions {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}
.xt-page-header__breadcrumb {
  padding-bottom: var(--xt-space-3);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/xt/XtPageHeader.vue
git commit -m "feat(xt): add XtPageHeader component"
```

---

### Task 12: Create XtGrid, XtSkeleton, XtEmpty, XtActionBar components

**Files:**
- Create: `frontend/src/components/xt/XtGrid.vue`
- Create: `frontend/src/components/xt/XtSkeleton.vue`
- Create: `frontend/src/components/xt/XtEmpty.vue`
- Create: `frontend/src/components/xt/XtActionBar.vue`

- [ ] **Step 1: Create XtGrid**

```vue
<!-- frontend/src/components/xt/XtGrid.vue -->
<template>
  <div class="xt-grid" :style="gridStyle">
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  cols: { type: Number, default: 3 },
  gap: { type: String, default: 'var(--xt-space-4)' },
  minWidth: { type: String, default: '280px' }
})

const gridStyle = computed(() => ({
  display: 'grid',
  gridTemplateColumns: `repeat(auto-fit, minmax(${props.minWidth}, 1fr))`,
  gap: props.gap
}))
</script>
```

- [ ] **Step 2: Create XtSkeleton**

```vue
<!-- frontend/src/components/xt/XtSkeleton.vue -->
<template>
  <div class="xt-skeleton" :class="`xt-skeleton--${preset}`">
    <template v-if="preset === 'kpi-strip'">
      <div v-for="i in 4" :key="i" class="xt-skeleton__kpi">
        <div class="xt-shimmer" style="width: 60px; height: 28px;" />
        <div class="xt-shimmer" style="width: 48px; height: 14px; margin-top: 6px;" />
      </div>
    </template>
    <template v-else-if="preset === 'table'">
      <div class="xt-shimmer" style="width: 100%; height: 40px;" />
      <div v-for="i in 5" :key="i" class="xt-shimmer" style="width: 100%; height: 48px; margin-top: 2px;" />
    </template>
    <template v-else-if="preset === 'card'">
      <div class="xt-shimmer" style="width: 100%; height: 120px; border-radius: var(--xt-radius-lg);" />
    </template>
    <template v-else>
      <div class="xt-shimmer" style="width: 40%; height: 24px;" />
      <div class="xt-shimmer" style="width: 100%; height: 200px; margin-top: 16px; border-radius: var(--xt-radius-lg);" />
    </template>
  </div>
</template>

<script setup>
defineProps({
  preset: { type: String, default: 'page', validator: v => ['page', 'table', 'kpi-strip', 'card'].includes(v) }
})
</script>

<style scoped>
.xt-skeleton { padding: var(--xt-space-4); }
.xt-skeleton--kpi-strip {
  display: flex;
  gap: var(--xt-space-6);
}
.xt-skeleton__kpi {
  display: flex;
  flex-direction: column;
}
</style>
```

- [ ] **Step 3: Create XtEmpty**

```vue
<!-- frontend/src/components/xt/XtEmpty.vue -->
<template>
  <div class="xt-empty">
    <svg class="xt-empty__icon" viewBox="0 0 48 48" width="48" height="48">
      <rect x="8" y="12" width="32" height="24" rx="3" fill="none" stroke="currentColor" stroke-width="1.5" />
      <line x1="16" y1="22" x2="32" y2="22" stroke="currentColor" stroke-width="1.5" opacity="0.4" />
      <line x1="16" y1="28" x2="28" y2="28" stroke="currentColor" stroke-width="1.5" opacity="0.4" />
    </svg>
    <p class="xt-empty__text">{{ text }}</p>
    <slot />
  </div>
</template>

<script setup>
const PRESETS = {
  'no-data': '暂无数据',
  'no-results': '未找到匹配结果',
  'no-access': '暂无权限访问'
}

const props = defineProps({
  preset: { type: String, default: 'no-data' },
  text: { type: String, default: '' }
})

if (!props.text) props.text = PRESETS[props.preset] || PRESETS['no-data']
</script>

<style scoped>
.xt-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--xt-space-12) var(--xt-space-4);
  color: var(--xt-text-muted);
}
.xt-empty__icon { margin-bottom: var(--xt-space-3); }
.xt-empty__text {
  font-size: var(--xt-text-sm);
  margin-bottom: var(--xt-space-4);
}
</style>
```

- [ ] **Step 4: Create XtActionBar**

```vue
<!-- frontend/src/components/xt/XtActionBar.vue -->
<template>
  <div class="xt-action-bar" :class="{ 'xt-action-bar--fixed': fixed }">
    <slot />
  </div>
</template>

<script setup>
defineProps({
  fixed: { type: Boolean, default: true }
})
</script>

<style scoped>
.xt-action-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3) var(--xt-space-4);
  background: var(--xt-bg-panel);
  border-top: 1px solid var(--xt-border-light);
}
.xt-action-bar--fixed {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.06);
  padding-bottom: max(var(--xt-space-3), env(safe-area-inset-bottom));
}
</style>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/xt/XtGrid.vue frontend/src/components/xt/XtSkeleton.vue frontend/src/components/xt/XtEmpty.vue frontend/src/components/xt/XtActionBar.vue
git commit -m "feat(xt): add XtGrid, XtSkeleton, XtEmpty, XtActionBar components"
```

---

### Task 13: Create XtFilter component

**Files:**
- Create: `frontend/src/components/xt/XtFilter.vue`

- [ ] **Step 1: Create XtFilter component**

```vue
<!-- frontend/src/components/xt/XtFilter.vue -->
<template>
  <div class="xt-filter">
    <div class="xt-filter__main">
      <slot />
      <el-button v-if="hasMore" text size="small" @click="expanded = !expanded">
        {{ expanded ? '收起' : '更多筛选' }}
      </el-button>
    </div>
    <div v-if="expanded && hasMore" class="xt-filter__extra">
      <slot name="extra" />
    </div>
    <div v-if="activeTags.length" class="xt-filter__tags">
      <el-tag
        v-for="tag in activeTags"
        :key="tag.key"
        closable
        size="small"
        @close="$emit('clear-filter', tag.key)"
      >
        {{ tag.label }}: {{ tag.value }}
      </el-tag>
      <el-button text size="small" @click="$emit('clear-all')">清除全部</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  activeTags: { type: Array, default: () => [] },
  hasMore: { type: Boolean, default: false }
})

defineEmits(['clear-filter', 'clear-all'])

const expanded = ref(false)
</script>

<style scoped>
.xt-filter {
  padding: var(--xt-space-3) var(--xt-space-4);
  background: var(--xt-bg-panel);
  border-radius: var(--xt-radius-lg);
  margin-bottom: var(--xt-space-4);
}
.xt-filter__main {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  flex-wrap: wrap;
}
.xt-filter__extra {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  flex-wrap: wrap;
  margin-top: var(--xt-space-3);
  padding-top: var(--xt-space-3);
  border-top: 1px solid var(--xt-border-light);
}
.xt-filter__tags {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  flex-wrap: wrap;
  margin-top: var(--xt-space-3);
  padding-top: var(--xt-space-3);
  border-top: 1px solid var(--xt-border-light);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/xt/XtFilter.vue
git commit -m "feat(xt): add XtFilter component with expandable filters and tags"
```

---

### Task 14: Create XtBatchAction and XtExport components

**Files:**
- Create: `frontend/src/components/xt/XtBatchAction.vue`
- Create: `frontend/src/components/xt/XtExport.vue`

- [ ] **Step 1: Create XtBatchAction**

```vue
<!-- frontend/src/components/xt/XtBatchAction.vue -->
<template>
  <Transition name="xt-rise">
    <div v-if="count > 0" class="xt-batch-action">
      <span class="xt-batch-action__count">已选 {{ count }} 条</span>
      <slot />
      <el-button text size="small" @click="$emit('cancel')">取消选择</el-button>
    </div>
  </Transition>
</template>

<script setup>
defineProps({
  count: { type: Number, default: 0 }
})
defineEmits(['cancel'])
</script>

<style scoped>
.xt-batch-action {
  position: fixed;
  bottom: var(--xt-space-4);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-2) var(--xt-space-4);
  background: var(--xt-gray-900);
  color: var(--xt-text-inverse);
  border-radius: var(--xt-radius-xl);
  box-shadow: var(--xt-shadow-lg);
  z-index: 200;
}
.xt-batch-action__count {
  font-size: var(--xt-text-sm);
  font-weight: 500;
}
.xt-batch-action :deep(.el-button) {
  color: var(--xt-text-inverse);
}
</style>
```

- [ ] **Step 2: Create XtExport**

```vue
<!-- frontend/src/components/xt/XtExport.vue -->
<template>
  <el-dropdown trigger="click" @command="handleExport">
    <el-button :loading="exporting" size="small">
      导出 <el-icon class="el-icon--right"><Download /></el-icon>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="csv">导出 CSV</el-dropdown-item>
        <el-dropdown-item command="xlsx">导出 Excel</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { ref } from 'vue'
import { Download } from '@element-plus/icons-vue'

const props = defineProps({
  module: { type: String, required: true },
  filters: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['export'])
const exporting = ref(false)

async function handleExport(format) {
  exporting.value = true
  try {
    emit('export', { format, module: props.module, filters: props.filters })
  } finally {
    exporting.value = false
  }
}
</script>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/xt/XtBatchAction.vue frontend/src/components/xt/XtExport.vue
git commit -m "feat(xt): add XtBatchAction and XtExport components"
```

---

### Task 15: Create XtSearch global command palette

**Files:**
- Create: `frontend/src/components/xt/XtSearch.vue`

- [ ] **Step 1: Create XtSearch component**

```vue
<!-- frontend/src/components/xt/XtSearch.vue -->
<template>
  <Teleport to="body">
    <Transition name="xt-fade">
      <div v-if="visible" class="xt-search-overlay" @click.self="close">
        <div class="xt-search-dialog">
          <div class="xt-search__input-wrap">
            <el-icon size="18"><Search /></el-icon>
            <input
              ref="inputRef"
              v-model="query"
              class="xt-search__input"
              placeholder="搜索页面、批次号、主数据..."
              @keydown.escape="close"
              @keydown.down.prevent="moveDown"
              @keydown.up.prevent="moveUp"
              @keydown.enter.prevent="selectCurrent"
            />
            <kbd class="xt-search__kbd">ESC</kbd>
          </div>
          <div v-if="groups.length" class="xt-search__results">
            <div v-for="group in groups" :key="group.label" class="xt-search__group">
              <div class="xt-search__group-label">{{ group.label }}</div>
              <div
                v-for="(item, i) in group.items"
                :key="item.id"
                class="xt-search__item"
                :class="{ 'is-active': activeIndex === getGlobalIndex(group, i) }"
                @click="select(item)"
                @mouseenter="activeIndex = getGlobalIndex(group, i)"
              >
                <span class="xt-search__item-title">{{ item.title }}</span>
                <span v-if="item.hint" class="xt-search__item-hint">{{ item.hint }}</span>
              </div>
            </div>
          </div>
          <div v-else-if="query" class="xt-search__empty">
            未找到匹配结果
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'

const router = useRouter()
const visible = ref(false)
const query = ref('')
const inputRef = ref(null)
const activeIndex = ref(0)

const props = defineProps({
  navItems: { type: Array, default: () => [] }
})

const groups = computed(() => {
  if (!query.value) return []
  const q = query.value.toLowerCase()
  const navMatches = props.navItems.filter(n =>
    n.title.toLowerCase().includes(q) || (n.hint || '').toLowerCase().includes(q)
  )
  const result = []
  if (navMatches.length) result.push({ label: '导航', items: navMatches.slice(0, 5) })
  return result
})

const allItems = computed(() => groups.value.flatMap(g => g.items))

function getGlobalIndex(group, localIndex) {
  let offset = 0
  for (const g of groups.value) {
    if (g === group) return offset + localIndex
    offset += g.items.length
  }
  return 0
}

function moveDown() { activeIndex.value = Math.min(activeIndex.value + 1, allItems.value.length - 1) }
function moveUp() { activeIndex.value = Math.max(activeIndex.value - 1, 0) }
function selectCurrent() { if (allItems.value[activeIndex.value]) select(allItems.value[activeIndex.value]) }

function select(item) {
  if (item.path) router.push(item.path)
  close()
}

function open() {
  visible.value = true
  query.value = ''
  activeIndex.value = 0
  nextTick(() => inputRef.value?.focus())
}

function close() { visible.value = false }

function handleKeydown(e) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    visible.value ? close() : open()
  }
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))

defineExpose({ open, close })
</script>

<style scoped>
.xt-search-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  justify-content: center;
  padding-top: 15vh;
  z-index: 9999;
}
.xt-search-dialog {
  width: 560px;
  max-height: 420px;
  background: var(--xt-bg-panel);
  border-radius: var(--xt-radius-xl);
  box-shadow: var(--xt-shadow-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.xt-search__input-wrap {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3) var(--xt-space-4);
  border-bottom: 1px solid var(--xt-border-light);
  color: var(--xt-text-muted);
}
.xt-search__input {
  flex: 1;
  border: none;
  outline: none;
  font-size: var(--xt-text-lg);
  color: var(--xt-text);
  background: transparent;
}
.xt-search__kbd {
  font-size: 11px;
  padding: 2px 6px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  color: var(--xt-text-muted);
}
.xt-search__results {
  overflow-y: auto;
  padding: var(--xt-space-2) 0;
}
.xt-search__group-label {
  padding: var(--xt-space-2) var(--xt-space-4);
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.xt-search__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--xt-space-2) var(--xt-space-4);
  cursor: pointer;
  transition: background var(--xt-motion-fast);
}
.xt-search__item.is-active {
  background: var(--xt-primary-light);
}
.xt-search__item-title {
  font-size: var(--xt-text-sm);
  color: var(--xt-text);
}
.xt-search__item-hint {
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
}
.xt-search__empty {
  padding: var(--xt-space-8);
  text-align: center;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/xt/XtSearch.vue
git commit -m "feat(xt): add XtSearch global command palette (Cmd+K)"
```

---

### Task 16: Create XtNotification component

**Files:**
- Create: `frontend/src/components/xt/XtNotification.vue`

- [ ] **Step 1: Create XtNotification component**

```vue
<!-- frontend/src/components/xt/XtNotification.vue -->
<template>
  <div class="xt-notification">
    <el-badge :value="unreadCount" :hidden="!unreadCount" :max="99">
      <el-button circle size="small" @click="panelVisible = !panelVisible">
        <el-icon><Bell /></el-icon>
      </el-button>
    </el-badge>
    <Transition name="xt-rise">
      <div v-if="panelVisible" class="xt-notification__panel">
        <div class="xt-notification__header">
          <span>通知</span>
          <el-button v-if="unreadCount" text size="small" @click="$emit('read-all')">全部已读</el-button>
        </div>
        <div class="xt-notification__list">
          <div
            v-for="item in notifications"
            :key="item.id"
            class="xt-notification__item"
            :class="{ 'is-unread': !item.read }"
            @click="$emit('click', item)"
          >
            <div class="xt-notification__dot" v-if="!item.read" />
            <div class="xt-notification__content">
              <span class="xt-notification__title">{{ item.title }}</span>
              <span class="xt-notification__time">{{ item.time }}</span>
            </div>
          </div>
          <div v-if="!notifications.length" class="xt-notification__empty">暂无通知</div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Bell } from '@element-plus/icons-vue'

defineProps({
  notifications: { type: Array, default: () => [] },
  unreadCount: { type: Number, default: 0 }
})

defineEmits(['click', 'read-all'])

const panelVisible = ref(false)
</script>

<style scoped>
.xt-notification { position: relative; }
.xt-notification__panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 320px;
  max-height: 400px;
  background: var(--xt-bg-panel);
  border-radius: var(--xt-radius-lg);
  box-shadow: var(--xt-shadow-lg);
  overflow: hidden;
  z-index: 500;
}
.xt-notification__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--xt-space-3) var(--xt-space-4);
  border-bottom: 1px solid var(--xt-border-light);
  font-weight: 600;
  font-size: var(--xt-text-sm);
}
.xt-notification__list {
  overflow-y: auto;
  max-height: 340px;
}
.xt-notification__item {
  display: flex;
  align-items: flex-start;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3) var(--xt-space-4);
  cursor: pointer;
  transition: background var(--xt-motion-fast);
}
.xt-notification__item:hover { background: var(--xt-gray-50); }
.xt-notification__item.is-unread { background: var(--xt-primary-light); }
.xt-notification__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--xt-primary);
  margin-top: 6px;
  flex-shrink: 0;
}
.xt-notification__content { flex: 1; min-width: 0; }
.xt-notification__title {
  font-size: var(--xt-text-sm);
  color: var(--xt-text);
  display: block;
}
.xt-notification__time {
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
}
.xt-notification__empty {
  padding: var(--xt-space-8);
  text-align: center;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/xt/XtNotification.vue
git commit -m "feat(xt): add XtNotification bell + dropdown panel"
```

---

### Task 17: Create ManageShell layout

**Files:**
- Create: `frontend/src/layout/ManageShell.vue`

- [ ] **Step 1: Create ManageShell with sidebar + topbar**

```vue
<!-- frontend/src/layout/ManageShell.vue -->
<template>
  <div class="xt-manage" :class="{ 'xt-manage--collapsed': collapsed }">
    <aside class="xt-manage__sidebar">
      <div class="xt-manage__brand">
        <XtLogo :variant="collapsed ? 'icon' : 'full'" />
      </div>
      <nav class="xt-manage__nav">
        <div v-for="group in navGroups" :key="group.label" class="xt-manage__nav-group">
          <div v-if="!collapsed" class="xt-manage__nav-group-label">{{ group.label }}</div>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="xt-manage__nav-item"
            :class="{ 'is-active': isActive(item.path) }"
            :title="collapsed ? item.title : undefined"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span v-if="!collapsed" class="xt-manage__nav-label">{{ item.title }}</span>
          </router-link>
        </div>
      </nav>
      <button class="xt-manage__collapse-btn" @click="toggleCollapse">
        <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
      </button>
    </aside>
    <div class="xt-manage__main">
      <header class="xt-manage__topbar">
        <button class="xt-manage__hamburger" @click="mobileDrawer = true">
          <el-icon size="20"><Menu /></el-icon>
        </button>
        <div class="xt-manage__search-trigger" @click="$refs.search?.open()">
          <el-icon><Search /></el-icon>
          <span>搜索...</span>
          <kbd>⌘K</kbd>
        </div>
        <div class="xt-manage__topbar-right">
          <XtNotification :notifications="[]" :unread-count="0" />
          <div class="xt-manage__user">
            <span>{{ userName }}</span>
            <el-dropdown trigger="click">
              <el-avatar :size="28">{{ userInitial }}</el-avatar>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="$router.push('/entry')">操作员端</el-dropdown-item>
                  <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </header>
      <main class="xt-manage__content xt-page">
        <div class="xt-manage__container">
          <router-view v-slot="{ Component }">
            <Transition name="xt-fade" mode="out-in">
              <component :is="Component" />
            </Transition>
          </router-view>
        </div>
      </main>
    </div>
    <XtSearch ref="search" :nav-items="searchItems" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Fold, Expand, Menu, Search } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import XtLogo from '@/components/xt/XtLogo.vue'
import XtNotification from '@/components/xt/XtNotification.vue'
import XtSearch from '@/components/xt/XtSearch.vue'
import { manageNavGroups } from '@/config/manage-navigation'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const collapsed = ref(localStorage.getItem('xt-sidebar-collapsed') === 'true')
const mobileDrawer = ref(false)

const userName = computed(() => auth.user?.display_name || '用户')
const userInitial = computed(() => (auth.user?.display_name || 'U')[0])

const navGroups = computed(() => manageNavGroups(auth))

const searchItems = computed(() =>
  navGroups.value.flatMap(g => g.items.map(i => ({ id: i.path, title: i.title, path: i.path, hint: g.label })))
)

function isActive(path) {
  return route.path.startsWith(path)
}

function toggleCollapse() {
  collapsed.value = !collapsed.value
  localStorage.setItem('xt-sidebar-collapsed', collapsed.value)
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.xt-manage {
  display: flex;
  min-height: 100vh;
  min-height: 100dvh;
}
.xt-manage__sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: var(--xt-sidebar-width);
  background: var(--xt-bg-panel);
  border-right: 1px solid var(--xt-border-light);
  display: flex;
  flex-direction: column;
  transition: width var(--xt-motion-normal) var(--xt-ease);
  z-index: 200;
  overflow-y: auto;
  overflow-x: hidden;
}
.xt-manage--collapsed .xt-manage__sidebar {
  width: var(--xt-sidebar-collapsed);
}
.xt-manage__brand {
  padding: var(--xt-space-4);
  border-bottom: 1px solid var(--xt-border-light);
}
.xt-manage__nav {
  flex: 1;
  padding: var(--xt-space-2) var(--xt-space-2);
}
.xt-manage__nav-group {
  margin-bottom: var(--xt-space-3);
}
.xt-manage__nav-group-label {
  padding: var(--xt-space-2) var(--xt-space-2);
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 500;
}
.xt-manage__nav-item {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: var(--xt-space-2) var(--xt-space-3);
  border-radius: var(--xt-radius-md);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  text-decoration: none;
  transition: all var(--xt-motion-fast) var(--xt-ease);
}
.xt-manage__nav-item:hover {
  background: var(--xt-gray-100);
  color: var(--xt-text);
}
.xt-manage__nav-item.is-active {
  background: var(--xt-primary-light);
  color: var(--xt-primary);
  font-weight: 500;
}
.xt-manage__collapse-btn {
  padding: var(--xt-space-3);
  border: none;
  background: none;
  color: var(--xt-text-muted);
  border-top: 1px solid var(--xt-border-light);
  transition: color var(--xt-motion-fast);
}
.xt-manage__collapse-btn:hover { color: var(--xt-text); }
.xt-manage__main {
  flex: 1;
  margin-left: var(--xt-sidebar-width);
  transition: margin-left var(--xt-motion-normal) var(--xt-ease);
  display: flex;
  flex-direction: column;
}
.xt-manage--collapsed .xt-manage__main {
  margin-left: var(--xt-sidebar-collapsed);
}
.xt-manage__topbar {
  position: sticky;
  top: 0;
  height: var(--xt-topbar-height);
  display: flex;
  align-items: center;
  gap: var(--xt-space-4);
  padding: 0 var(--xt-space-6);
  background: var(--xt-bg-panel);
  border-bottom: 1px solid var(--xt-border-light);
  z-index: 100;
}
.xt-manage__hamburger {
  display: none;
  border: none;
  background: none;
  color: var(--xt-text);
}
.xt-manage__search-trigger {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: var(--xt-space-2) var(--xt-space-3);
  background: var(--xt-gray-100);
  border-radius: var(--xt-radius-md);
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
  cursor: pointer;
  min-width: 200px;
  transition: background var(--xt-motion-fast);
}
.xt-manage__search-trigger:hover { background: var(--xt-gray-200); }
.xt-manage__search-trigger kbd {
  margin-left: auto;
  font-size: 11px;
  padding: 1px 5px;
  border: 1px solid var(--xt-border);
  border-radius: 3px;
}
.xt-manage__topbar-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
}
.xt-manage__user {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  font-size: var(--xt-text-sm);
  color: var(--xt-text-secondary);
}
.xt-manage__content {
  flex: 1;
  padding: var(--xt-space-6);
}
.xt-manage__container {
  max-width: var(--xt-content-max);
  margin: 0 auto;
}

@media (max-width: 1023px) {
  .xt-manage__sidebar { width: var(--xt-sidebar-collapsed); }
  .xt-manage__main { margin-left: var(--xt-sidebar-collapsed); }
  .xt-manage__nav-label { display: none; }
  .xt-manage__nav-group-label { display: none; }
}
@media (max-width: 767px) {
  .xt-manage__sidebar { display: none; }
  .xt-manage__main { margin-left: 0; }
  .xt-manage__hamburger { display: flex; }
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/layout/ManageShell.vue
git commit -m "feat(shell): add ManageShell with sidebar, topbar, responsive layout"
```

---

### Task 18: Create manage navigation config

**Files:**
- Create: `frontend/src/config/manage-navigation.js`

- [ ] **Step 1: Create the navigation config for ManageShell**

```js
// frontend/src/config/manage-navigation.js
import {
  DataAnalysis, Document, Setting, Monitor,
  List, Calendar, Tickets, Warning, TrendCharts,
  Coin, Printer, Grid, Connection, Upload, ChatDotRound
} from '@element-plus/icons-vue'

const NAV_GROUPS = [
  {
    label: '总览',
    items: [
      { title: '总览', path: '/manage/overview', icon: Monitor, access: 'review' }
    ]
  },
  {
    label: '生产管理',
    items: [
      { title: '录入中心', path: '/manage/entry-center', icon: List, access: 'review' },
      { title: '班次中心', path: '/manage/shift', icon: Calendar, access: 'review' },
      { title: '对账中心', path: '/manage/reconciliation', icon: Tickets, access: 'review' }
    ]
  },
  {
    label: '质量管控',
    items: [
      { title: '异常审核', path: '/manage/anomaly', icon: Warning, access: 'review' },
      { title: '质量预警', path: '/manage/quality', icon: TrendCharts, access: 'review' }
    ]
  },
  {
    label: '数据分析',
    items: [
      { title: '统计中心', path: '/manage/statistics', icon: DataAnalysis, access: 'review' },
      { title: '成本效益', path: '/manage/cost', icon: Coin, access: 'review' },
      { title: '报表交付', path: '/manage/reports', icon: Printer, access: 'review' }
    ]
  },
  {
    label: '基础数据',
    items: [
      { title: '主数据', path: '/manage/master', icon: Grid, access: 'admin' },
      { title: '别名映射', path: '/manage/alias', icon: Connection, access: 'admin' },
      { title: '导入历史', path: '/manage/imports', icon: Upload, access: 'admin' }
    ]
  },
  {
    label: 'AI',
    items: [
      { title: 'AI 工作台', path: '/manage/ai', icon: ChatDotRound, access: 'review' }
    ]
  },
  {
    label: '系统管理',
    items: [
      { title: '系统设置', path: '/manage/admin/settings', icon: Setting, access: 'admin' }
    ]
  }
]

function canAccess(auth, access) {
  if (access === 'review') return auth.canAccessReviewSurface
  if (access === 'admin') return auth.canAccessAdminSurface
  return true
}

export function manageNavGroups(auth) {
  return NAV_GROUPS
    .map(group => ({
      ...group,
      items: group.items.filter(item => canAccess(auth, item.access))
    }))
    .filter(group => group.items.length > 0)
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/config/manage-navigation.js
git commit -m "feat(config): add manage-navigation.js for ManageShell sidebar"
```

---

### Task 19: Rewrite EntryShell with bottom tab bar

**Files:**
- Modify: `frontend/src/layout/EntryShell.vue`

- [ ] **Step 1: Rewrite EntryShell**

Replace the entire content of `EntryShell.vue` with:

```vue
<!-- frontend/src/layout/EntryShell.vue -->
<template>
  <div class="xt-entry">
    <header class="xt-entry__topbar">
      <XtLogo variant="compact" />
      <div class="xt-entry__shift">
        {{ currentShift }}
      </div>
      <span class="xt-entry__user">{{ userName }}</span>
    </header>
    <main class="xt-entry__content">
      <router-view v-slot="{ Component }">
        <Transition name="xt-fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </main>
    <nav class="xt-entry__tabbar">
      <router-link
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="xt-entry__tab"
        :class="{ 'is-active': isActive(tab.path) }"
      >
        <el-icon><component :is="tab.icon" /></el-icon>
        <span>{{ tab.label }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { HomeFilled, EditPen, Document, User } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import XtLogo from '@/components/xt/XtLogo.vue'

const route = useRoute()
const auth = useAuthStore()

const userName = computed(() => auth.user?.display_name || '操作员')
const currentShift = computed(() => auth.machineContext?.shift || '当前班次')

const tabs = [
  { path: '/entry', label: '首页', icon: HomeFilled },
  { path: '/entry/report', label: '录入', icon: EditPen },
  { path: '/entry/drafts', label: '草稿', icon: Document },
  { path: '/entry/profile', label: '我的', icon: User }
]

function isActive(path) {
  if (path === '/entry') return route.path === '/entry'
  return route.path.startsWith(path)
}
</script>

<style scoped>
.xt-entry {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
  max-width: 560px;
  margin: 0 auto;
  background: var(--xt-bg-page);
}
.xt-entry__topbar {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3) var(--xt-space-4);
  background: var(--xt-bg-panel);
  border-bottom: 1px solid var(--xt-border-light);
}
.xt-entry__shift {
  font-size: var(--xt-text-xs);
  color: var(--xt-text-secondary);
  background: var(--xt-gray-100);
  padding: 2px 8px;
  border-radius: 10px;
}
.xt-entry__user {
  margin-left: auto;
  font-size: var(--xt-text-sm);
  color: var(--xt-text-secondary);
}
.xt-entry__content {
  flex: 1;
  padding: var(--xt-space-4);
  padding-bottom: calc(var(--xt-tabbar-height) + var(--xt-space-4));
}
.xt-entry__tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: var(--xt-tabbar-height);
  display: flex;
  align-items: center;
  justify-content: space-around;
  background: var(--xt-bg-panel);
  border-top: 1px solid var(--xt-border-light);
  padding-bottom: env(safe-area-inset-bottom);
  z-index: 100;
  max-width: 560px;
  margin: 0 auto;
}
.xt-entry__tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--xt-space-1) var(--xt-space-3);
  color: var(--xt-text-muted);
  font-size: 10px;
  text-decoration: none;
  transition: color var(--xt-motion-fast);
}
.xt-entry__tab .el-icon { font-size: 20px; }
.xt-entry__tab.is-active {
  color: var(--xt-primary);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/layout/EntryShell.vue
git commit -m "feat(shell): rewrite EntryShell with bottom tab bar navigation"
```

---

### Task 20: Rewrite router with new route structure

**Files:**
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: Rewrite the router**

Replace the entire router file. Key changes:
- `/manage/*` routes using `ManageShell`
- `/entry/*` routes using rewritten `EntryShell`
- Legacy redirects from `/review/*`, `/admin/*`, `/mobile/*`, `/dashboard/*`
- Keep the same auth guard logic but update zone checks

```js
// frontend/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'

const ManageShell = () => import('@/layout/ManageShell.vue')
const EntryShell = () => import('@/layout/EntryShell.vue')

const CommandLogin = () => import('@/reference-command/pages/CommandLogin.vue')

// Entry pages
const CommandEntryHome = () => import('@/reference-command/pages/CommandEntryHome.vue')
const CommandEntryFlow = () => import('@/reference-command/pages/CommandEntryFlow.vue')
const EntryDrafts = () => import('@/views/entry/EntryDrafts.vue')
const ShiftReportForm = () => import('@/views/mobile/ShiftReportForm.vue')
const DynamicEntryForm = () => import('@/views/mobile/DynamicEntryForm.vue')
const OCRCapture = () => import('@/views/mobile/OCRCapture.vue')
const AttendanceConfirm = () => import('@/views/mobile/AttendanceConfirm.vue')
const ShiftReportHistory = () => import('@/views/mobile/ShiftReportHistory.vue')

// Manage pages (will be replaced in Phase 3, using existing for now)
const CommandOverview = () => import('@/reference-command/pages/CommandOverview.vue')
const CommandModulePage = () => import('@/reference-command/pages/CommandModulePage.vue')
const CommandReviewTasks = () => import('@/reference-command/pages/CommandReviewTasks.vue')
const AnomalyReview = () => import('@/views/attendance/AnomalyReview.vue')
const Statistics = () => import('@/views/dashboard/Statistics.vue')
const ReconciliationDetail = () => import('@/views/reconciliation/ReconciliationDetail.vue')
const ShiftCenter = () => import('@/views/shift/ShiftCenter.vue')
const OverviewCenter = () => import('@/views/review/OverviewCenter.vue')
const MachineWizard = () => import('@/views/master/MachineWizard.vue')
const AliasMapping = () => import('@/views/master/AliasMapping.vue')
const ImportHistory = () => import('@/views/imports/ImportHistory.vue')

// AI Workstation (Phase 4)
const AiWorkstation = () => import('@/views/ai/AiWorkstation.vue')

const routes = [
  { path: '/login', name: 'login', component: CommandLogin, meta: { access: 'public' } },

  // Entry surface (mobile-first)
  {
    path: '/entry',
    component: EntryShell,
    meta: { access: 'entry', zone: 'entry' },
    children: [
      { path: '', name: 'entry-home', component: CommandEntryHome },
      { path: 'report/:batch?', name: 'entry-flow', component: CommandEntryFlow },
      { path: 'advanced/:batch?', name: 'entry-advanced', component: DynamicEntryForm },
      { path: 'drafts', name: 'entry-drafts', component: EntryDrafts },
      { path: 'shift-report', name: 'entry-shift-report', component: ShiftReportForm },
      { path: 'shift-history', name: 'entry-shift-history', component: ShiftReportHistory },
      { path: 'ocr', name: 'entry-ocr', component: OCRCapture },
      { path: 'attendance', name: 'entry-attendance', component: AttendanceConfirm },
      { path: 'profile', name: 'entry-profile', component: () => import('@/views/mobile/MobileEntry.vue') }
    ]
  },

  // Manage surface (review + admin merged)
  {
    path: '/manage',
    component: ManageShell,
    meta: { access: 'review', zone: 'manage' },
    children: [
      { path: '', redirect: '/manage/overview' },
      { path: 'overview', name: 'manage-overview', component: OverviewCenter },
      { path: 'entry-center', name: 'manage-entry-center', component: CommandReviewTasks },
      { path: 'shift', name: 'manage-shift', component: ShiftCenter },
      { path: 'reconciliation', name: 'manage-reconciliation', component: ReconciliationDetail },
      { path: 'anomaly', name: 'manage-anomaly', component: AnomalyReview },
      { path: 'quality', name: 'manage-quality', component: CommandModulePage, props: { moduleId: 'quality' } },
      { path: 'statistics', name: 'manage-statistics', component: Statistics },
      { path: 'cost', name: 'manage-cost', component: CommandModulePage, props: { moduleId: 'cost' } },
      { path: 'reports', name: 'manage-reports', component: CommandModulePage, props: { moduleId: 'reports' } },
      { path: 'master', name: 'manage-master', component: MachineWizard, meta: { access: 'admin' } },
      { path: 'alias', name: 'manage-alias', component: AliasMapping, meta: { access: 'admin' } },
      { path: 'imports', name: 'manage-imports', component: ImportHistory, meta: { access: 'admin' } },
      { path: 'ai', name: 'manage-ai', component: AiWorkstation },
      { path: 'admin/settings', name: 'manage-admin-settings', component: CommandModulePage, props: { moduleId: 'ops' }, meta: { access: 'admin' } }
    ]
  },

  // Legacy redirects
  { path: '/review', redirect: '/manage/overview' },
  { path: '/review/overview', redirect: '/manage/overview' },
  { path: '/review/tasks', redirect: '/manage/entry-center' },
  { path: '/review/factory', redirect: '/manage/overview' },
  { path: '/review/reports', redirect: '/manage/reports' },
  { path: '/review/quality', redirect: '/manage/quality' },
  { path: '/review/cost', redirect: '/manage/cost' },
  { path: '/review/brain', redirect: '/manage/ai' },
  { path: '/review/reconciliation', redirect: '/manage/reconciliation' },
  { path: '/admin', redirect: '/manage/master' },
  { path: '/admin/:pathMatch(.*)*', redirect: to => `/manage/admin/${to.params.pathMatch}` },
  { path: '/mobile/:pathMatch(.*)*', redirect: '/entry' },
  { path: '/dashboard/:pathMatch(.*)*', redirect: '/manage/statistics' },
  { path: '/', redirect: '/manage/overview' },
  { path: '/:pathMatch(.*)*', redirect: '/manage/overview' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router

export function installRouterGuards(router, authStore) {
  router.beforeEach(async (to, from) => {
    const auth = authStore
    const access = to.meta.access || to.matched.find(r => r.meta.access)?.meta.access

    if (access === 'public') return true

    if (!auth.token) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    if (!auth.user) {
      try { await auth.fetchProfile() } catch { return '/login' }
    }

    if (auth.isFillOnly && to.meta.zone !== 'entry') {
      return '/entry'
    }

    if (access === 'admin' && !auth.canAccessAdminSurface) {
      return '/manage/overview'
    }

    return true
  })
}
```

Note: The `installRouterGuards` function replaces the inline `beforeEach` from the old router. Call it from `main.js` as `installRouterGuards(router, useAuthStore())` after creating the Pinia store. The existing auth guard logic (DingTalk SSO, mobile detection, zone access) should be preserved — adapt the above to match the exact checks in the current `router/index.js`.

- [ ] **Step 2: Create placeholder AiWorkstation page**

```vue
<!-- frontend/src/views/ai/AiWorkstation.vue -->
<template>
  <div class="ai-workstation">
    <XtPageHeader title="AI 工作台" subtitle="AI Workstation" number="AI" />
    <XtEmpty preset="no-data" text="AI 工作台即将上线" />
  </div>
</template>

<script setup>
import XtPageHeader from '@/components/xt/XtPageHeader.vue'
import XtEmpty from '@/components/xt/XtEmpty.vue'
</script>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.js frontend/src/views/ai/AiWorkstation.vue
git commit -m "feat(router): rewrite routes with /manage/* + /entry/* structure and legacy redirects"
```

---

### Task 21: Update main.js to use new router guards

**Files:**
- Modify: `frontend/src/main.js`

- [ ] **Step 1: Update main.js**

Update the router guard setup to use the new `installRouterGuards` function. The key change is calling `installRouterGuards(router, pinia)` instead of the old inline guard setup.

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx vite build --configLoader native 2>&1 | tail -10`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/main.js
git commit -m "feat(main): wire new router guards and design system imports"
```

---

### Task 22: Create component barrel export

**Files:**
- Create: `frontend/src/components/xt/index.js`

- [ ] **Step 1: Create barrel export**

```js
// frontend/src/components/xt/index.js
export { default as XtCard } from './XtCard.vue'
export { default as XtKpi } from './XtKpi.vue'
export { default as XtStatus } from './XtStatus.vue'
export { default as XtTable } from './XtTable.vue'
export { default as XtPageHeader } from './XtPageHeader.vue'
export { default as XtGrid } from './XtGrid.vue'
export { default as XtSkeleton } from './XtSkeleton.vue'
export { default as XtEmpty } from './XtEmpty.vue'
export { default as XtActionBar } from './XtActionBar.vue'
export { default as XtFilter } from './XtFilter.vue'
export { default as XtBatchAction } from './XtBatchAction.vue'
export { default as XtExport } from './XtExport.vue'
export { default as XtSearch } from './XtSearch.vue'
export { default as XtNotification } from './XtNotification.vue'
export { default as XtLogo } from './XtLogo.vue'
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/xt/index.js
git commit -m "feat(xt): add barrel export for all Xt components"
```

---

## Phase 3: Page Migrations

All pages follow the same pattern: XtPageHeader → XtKpi strip → XtFilter → XtTable. Each task rewrites one page using the new Xt components while preserving existing business logic (API calls, store interactions, form bindings).

### Task 23: Rewrite Login page

**Files:**
- Modify: `frontend/src/reference-command/pages/CommandLogin.vue`

- [ ] **Step 1: Rewrite CommandLogin with industrial background**

Replace the template and styles. Keep the existing `<script setup>` logic (login, dingtalkLogin, qrLogin). Key visual changes:
- Use `xt-login-bg` class from `industrial.css` for the dark background
- Centered white card with `XtLogo` (full variant, large)
- Clean form with `el-input` using new token styles
- Remove all `cmd-login` classes and old gradient backgrounds

```vue
<template>
  <div class="xt-login-bg">
    <div class="xt-login-card">
      <div class="xt-login-brand">
        <XtLogo variant="full" :color="true" />
        <p class="xt-login-tagline">铝业智能制造执行系统</p>
      </div>
      <el-form @submit.prevent="handleLogin" class="xt-login-form">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" size="large" data-testid="login-username" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" size="large" show-password data-testid="login-password" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" size="large" class="xt-login-submit" data-testid="login-submit">
          登录
        </el-button>
      </el-form>
      <div v-if="showDingtalk" class="xt-login-sso">
        <el-divider>或</el-divider>
        <el-button @click="dingtalkLogin" size="large" plain>钉钉登录</el-button>
      </div>
      <div v-if="showQr" class="xt-login-qr">
        <el-divider>机台登录</el-divider>
        <el-button @click="qrLogin" size="large" plain>扫码登录</el-button>
      </div>
    </div>
  </div>
</template>
```

Styles:
```css
.xt-login-card {
  width: 380px;
  max-width: 90vw;
  background: var(--xt-bg-panel);
  border-radius: var(--xt-radius-xl);
  padding: var(--xt-space-8);
  box-shadow: var(--xt-shadow-lg);
  position: relative;
  z-index: 1;
}
.xt-login-bg {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.xt-login-brand {
  text-align: center;
  margin-bottom: var(--xt-space-8);
}
.xt-login-brand .xt-logo { justify-content: center; }
.xt-login-tagline {
  font-size: var(--xt-text-sm);
  color: var(--xt-text-secondary);
  margin-top: var(--xt-space-2);
}
.xt-login-submit { width: 100%; }
.xt-login-sso, .xt-login-qr { margin-top: var(--xt-space-4); }
```

- [ ] **Step 2: Verify login page renders**

Run: `cd frontend && npx vite build --configLoader native 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/reference-command/pages/CommandLogin.vue
git commit -m "feat(pages): rewrite login page with industrial background and new design"
```

---

### Task 24: Rewrite Overview page

**Files:**
- Modify: `frontend/src/views/review/OverviewCenter.vue`

- [ ] **Step 1: Rewrite OverviewCenter with Xt components**

Replace template and styles. Keep existing data fetching logic. Structure:
- `XtPageHeader` with title "总览" / "Overview" / number "01"
- `XtGrid` with 4-5 `XtKpi` cards for key metrics
- Quick-access shortcut grid using `XtCard` with `hoverable`
- Production line status section

```vue
<template>
  <div>
    <XtPageHeader title="总览" subtitle="Overview" number="01">
      <template #actions>
        <el-button size="small" @click="refresh">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </template>
    </XtPageHeader>

    <XtSkeleton v-if="loading" preset="kpi-strip" />
    <XtGrid v-else :cols="5" min-width="160px" style="margin-bottom: var(--xt-space-4);">
      <XtKpi v-for="kpi in kpis" :key="kpi.label" :value="kpi.value" :label="kpi.label" :trend="kpi.trend" />
    </XtGrid>

    <XtGrid :cols="4" min-width="200px">
      <XtCard v-for="shortcut in shortcuts" :key="shortcut.path" hoverable @click="$router.push(shortcut.path)">
        <div style="padding: var(--xt-space-4); text-align: center;">
          <el-icon size="24" :color="'var(--xt-primary)'"><component :is="shortcut.icon" /></el-icon>
          <p style="margin-top: var(--xt-space-2); font-size: var(--xt-text-sm);">{{ shortcut.title }}</p>
        </div>
      </XtCard>
    </XtGrid>
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/review/OverviewCenter.vue
git commit -m "feat(pages): rewrite overview page with Xt components"
```

---

### Task 25: Rewrite remaining manage pages (batch)

Each manage page follows the same pattern. For each page, replace the template with:
1. `XtPageHeader` (title, subtitle, number, actions slot with XtExport)
2. `XtFilter` (relevant filters for the module)
3. `XtTable` (data table with appropriate columns)
4. Keep existing `<script setup>` logic

**Files to modify (one commit per page):**

- [ ] **Step 1: Rewrite录入中心 (CommandReviewTasks.vue)**

Pattern: XtPageHeader("录入中心", "Entry Center", "02") → XtKpi strip → XtFilter (status, date range) → XtTable (batch records) with XtBatchAction for bulk approve.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/reference-command/pages/CommandReviewTasks.vue
git commit -m "feat(pages): rewrite entry center with Xt components"
```

- [ ] **Step 3: Rewrite 班次中心 (ShiftCenter.vue)**

Pattern: XtPageHeader("班次中心", "Shift Center", "03") → XtFilter (date picker) → XtTable (shift reports).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/shift/ShiftCenter.vue
git commit -m "feat(pages): rewrite shift center with Xt components"
```

- [ ] **Step 5: Rewrite 对账中心 (ReconciliationDetail.vue)**

Pattern: XtPageHeader("对账中心", "Reconciliation", "04") → XtKpi strip → XtTable with difference highlighting via XtStatus.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/reconciliation/ReconciliationDetail.vue
git commit -m "feat(pages): rewrite reconciliation center with Xt components"
```

- [ ] **Step 7: Rewrite 异常审核 (AnomalyReview.vue)**

Pattern: XtPageHeader("异常审核", "Anomaly Review", "05") → XtFilter (status, date) → XtTable with XtBatchAction for bulk processing.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/attendance/AnomalyReview.vue
git commit -m "feat(pages): rewrite anomaly review with Xt components"
```

- [ ] **Step 9: Rewrite 统计中心 (Statistics.vue)**

Pattern: XtPageHeader("统计中心", "Statistics", "06") → XtKpi strip → chart/table toggle view.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/views/dashboard/Statistics.vue
git commit -m "feat(pages): rewrite statistics center with Xt components"
```

- [ ] **Step 11: Rewrite 主数据 (MachineWizard.vue)**

Pattern: XtPageHeader("主数据", "Master Data", "07") → XtFilter → XtTable (CRUD list).

- [ ] **Step 12: Commit**

```bash
git add frontend/src/views/master/MachineWizard.vue
git commit -m "feat(pages): rewrite master data with Xt components"
```

- [ ] **Step 13: Rewrite 别名映射 (AliasMapping.vue)**

Pattern: XtPageHeader("别名映射", "Alias Mapping", "08") → XtTable (CRUD list).

- [ ] **Step 14: Commit**

```bash
git add frontend/src/views/master/AliasMapping.vue
git commit -m "feat(pages): rewrite alias mapping with Xt components"
```

- [ ] **Step 15: Rewrite 导入历史 (ImportHistory.vue)**

Pattern: XtPageHeader("导入历史", "Import History", "09") → XtFilter (date) → XtTable with XtBatchAction.

- [ ] **Step 16: Commit**

```bash
git add frontend/src/views/imports/ImportHistory.vue
git commit -m "feat(pages): rewrite import history with Xt components"
```

- [ ] **Step 17: Rewrite CommandModulePage (generic module page)**

This is used for quality, cost, reports, and admin settings. Update to use XtPageHeader + XtKpi + XtTable pattern, reading module config from props.

- [ ] **Step 18: Commit**

```bash
git add frontend/src/reference-command/pages/CommandModulePage.vue
git commit -m "feat(pages): rewrite CommandModulePage with Xt components"
```

---

### Task 26: Rewrite Entry pages

**Files to modify:**

- [ ] **Step 1: Rewrite CommandEntryHome (entry homepage)**

Mobile-first layout: current shift card → KPI strip → batch number input → quick action buttons. Use XtCard, XtKpi, XtGrid.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/reference-command/pages/CommandEntryHome.vue
git commit -m "feat(pages): rewrite entry home with Xt components"
```

- [ ] **Step 3: Rewrite CommandEntryFlow (entry flow)**

Step-by-step form with XtActionBar at bottom. Each step is one screen. Use el-steps + XtCard for each step content.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/reference-command/pages/CommandEntryFlow.vue
git commit -m "feat(pages): rewrite entry flow with Xt components"
```

- [ ] **Step 5: Rewrite DynamicEntryForm (advanced entry)**

Similar to entry flow but with dynamic fields. Use XtCard + XtActionBar.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "feat(pages): rewrite dynamic entry form with Xt components"
```

---

### Task 27: Write E2E tests for new layout

**Files:**
- Create: `frontend/e2e/manage-shell.spec.js`
- Modify: `frontend/e2e/login-delivery-smoke.spec.js`

- [ ] **Step 1: Write ManageShell E2E test**

```js
// frontend/e2e/manage-shell.spec.js
import { expect, test } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'

test.describe('ManageShell Layout', () => {
  test('sidebar navigation renders and links work', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/overview')
    await expect(page.locator('.xt-manage__sidebar')).toBeVisible()
    await expect(page.locator('.xt-manage__nav-item.is-active')).toContainText('总览')
  })

  test('sidebar collapses and remembers state', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/overview')
    await page.click('.xt-manage__collapse-btn')
    await expect(page.locator('.xt-manage--collapsed')).toBeVisible()
  })

  test('Cmd+K opens search palette', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/manage/overview')
    await page.keyboard.press('Control+k')
    await expect(page.locator('.xt-search-overlay')).toBeVisible()
  })

  test('legacy /review redirects to /manage', async ({ page }) => {
    await setupReviewSessionAndMocks(page)
    await page.goto('/review/overview')
    await expect(page).toHaveURL(/\/manage\/overview/)
  })
})
```

- [ ] **Step 2: Update login smoke test for new login page**

Update selectors in `login-delivery-smoke.spec.js` to match new login page structure (data-testid attributes are preserved).

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/manage-shell.spec.js frontend/e2e/login-delivery-smoke.spec.js
git commit -m "test(e2e): add ManageShell layout tests and update login smoke test"
```

---

## Phase 4: AI Workstation + Backend APIs + Cleanup

### Task 28: Create AI Workstation frontend

**Files:**
- Rewrite: `frontend/src/views/ai/AiWorkstation.vue`
- Create: `frontend/src/views/ai/AiConversationList.vue`
- Create: `frontend/src/views/ai/AiChatMessage.vue`
- Create: `frontend/src/stores/ai-chat.js`

- [ ] **Step 1: Create AI chat store**

```js
// frontend/src/stores/ai-chat.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useAiChatStore = defineStore('ai-chat', () => {
  const conversations = ref([])
  const currentId = ref(null)
  const messages = ref([])
  const streaming = ref(false)

  const currentConversation = computed(() =>
    conversations.value.find(c => c.id === currentId.value)
  )

  async function loadConversations() {
    const { data } = await axios.get('/api/ai/conversations')
    conversations.value = data
  }

  async function loadMessages(conversationId) {
    currentId.value = conversationId
    const { data } = await axios.get(`/api/ai/conversations/${conversationId}`)
    messages.value = data.messages
  }

  async function createConversation() {
    const { data } = await axios.post('/api/ai/conversations')
    conversations.value.unshift(data)
    currentId.value = data.id
    messages.value = []
    return data
  }

  async function sendMessage(content) {
    messages.value.push({ role: 'user', content, timestamp: Date.now() })
    streaming.value = true

    const assistantMsg = { role: 'assistant', content: '', timestamp: Date.now(), toolCalls: [] }
    messages.value.push(assistantMsg)

    try {
      const response = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: currentId.value, message: content })
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n').filter(l => l.startsWith('data: '))
        for (const line of lines) {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'text') assistantMsg.content += data.content
          if (data.type === 'tool_call') assistantMsg.toolCalls.push(data)
          if (data.type === 'done') break
        }
      }
    } finally {
      streaming.value = false
    }
  }

  async function deleteConversation(id) {
    await axios.delete(`/api/ai/conversations/${id}`)
    conversations.value = conversations.value.filter(c => c.id !== id)
    if (currentId.value === id) {
      currentId.value = null
      messages.value = []
    }
  }

  async function renameConversation(id, title) {
    await axios.patch(`/api/ai/conversations/${id}`, { title })
    const conv = conversations.value.find(c => c.id === id)
    if (conv) conv.title = title
  }

  async function stopGeneration() {
    if (currentId.value) {
      await axios.post(`/api/ai/conversations/${currentId.value}/stop`)
      streaming.value = false
    }
  }

  return {
    conversations, currentId, messages, streaming, currentConversation,
    loadConversations, loadMessages, createConversation, sendMessage,
    deleteConversation, renameConversation, stopGeneration
  }
})
```

- [ ] **Step 2: Create AiChatMessage component**

```vue
<!-- frontend/src/views/ai/AiChatMessage.vue -->
<template>
  <div class="ai-msg" :class="`ai-msg--${msg.role}`">
    <div class="ai-msg__bubble">
      <div v-if="msg.role === 'assistant'" class="ai-msg__content" v-html="renderedContent" />
      <div v-else class="ai-msg__content">{{ msg.content }}</div>
      <div v-if="msg.toolCalls?.length" class="ai-msg__tools">
        <details v-for="(tc, i) in msg.toolCalls" :key="i" class="ai-msg__tool">
          <summary>{{ tc.name }} <XtStatus :status="tc.status || 'done'" :label="tc.status || '完成'" /></summary>
          <pre class="ai-msg__tool-detail">{{ JSON.stringify(tc.result, null, 2) }}</pre>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import XtStatus from '@/components/xt/XtStatus.vue'

const props = defineProps({
  msg: { type: Object, required: true }
})

const renderedContent = computed(() => {
  // Basic markdown: bold, code, newlines
  return props.msg.content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
})
</script>

<style scoped>
.ai-msg { display: flex; margin-bottom: var(--xt-space-3); }
.ai-msg--user { justify-content: flex-end; }
.ai-msg--assistant { justify-content: flex-start; }
.ai-msg__bubble {
  max-width: 75%;
  padding: var(--xt-space-3) var(--xt-space-4);
  border-radius: var(--xt-radius-lg);
}
.ai-msg--user .ai-msg__bubble {
  background: var(--xt-primary);
  color: var(--xt-text-inverse);
}
.ai-msg--assistant .ai-msg__bubble {
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}
.ai-msg__content { font-size: var(--xt-text-sm); line-height: 1.6; }
.ai-msg__content :deep(code) {
  background: var(--xt-gray-100);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: var(--xt-font-mono);
  font-size: 12px;
}
.ai-msg__tools { margin-top: var(--xt-space-2); }
.ai-msg__tool {
  background: var(--xt-gray-50);
  border-radius: var(--xt-radius-sm);
  padding: var(--xt-space-2);
  margin-top: var(--xt-space-1);
  font-size: var(--xt-text-xs);
}
.ai-msg__tool summary {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}
.ai-msg__tool-detail {
  margin-top: var(--xt-space-2);
  font-family: var(--xt-font-mono);
  font-size: 11px;
  overflow-x: auto;
  max-height: 200px;
}
</style>
```

- [ ] **Step 3: Create AiConversationList component**

```vue
<!-- frontend/src/views/ai/AiConversationList.vue -->
<template>
  <aside class="ai-sidebar">
    <el-button type="primary" class="ai-sidebar__new" @click="$emit('new')">
      新建对话
    </el-button>
    <div class="ai-sidebar__list">
      <div
        v-for="conv in conversations"
        :key="conv.id"
        class="ai-sidebar__item"
        :class="{ 'is-active': conv.id === currentId }"
        @click="$emit('select', conv.id)"
      >
        <span class="ai-sidebar__title">{{ conv.title || '新对话' }}</span>
        <span class="ai-sidebar__time">{{ formatTime(conv.updated_at) }}</span>
        <el-button
          class="ai-sidebar__delete"
          text
          size="small"
          @click.stop="$emit('delete', conv.id)"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
      <div v-if="!conversations.length" class="ai-sidebar__empty">
        暂无对话
      </div>
    </div>
  </aside>
</template>

<script setup>
import { Delete } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

defineProps({
  conversations: { type: Array, default: () => [] },
  currentId: { type: [String, Number], default: null }
})

defineEmits(['new', 'select', 'delete'])

function formatTime(ts) {
  if (!ts) return ''
  return dayjs(ts).format('MM-DD HH:mm')
}
</script>

<style scoped>
.ai-sidebar {
  width: 240px;
  border-right: 1px solid var(--xt-border-light);
  display: flex;
  flex-direction: column;
  background: var(--xt-bg-panel-soft);
  height: 100%;
}
.ai-sidebar__new {
  margin: var(--xt-space-3);
}
.ai-sidebar__list {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--xt-space-2);
}
.ai-sidebar__item {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: var(--xt-space-2) var(--xt-space-3);
  border-radius: var(--xt-radius-md);
  cursor: pointer;
  transition: background var(--xt-motion-fast);
  position: relative;
}
.ai-sidebar__item:hover { background: var(--xt-gray-100); }
.ai-sidebar__item.is-active { background: var(--xt-primary-light); }
.ai-sidebar__title {
  flex: 1;
  font-size: var(--xt-text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ai-sidebar__time {
  font-size: 10px;
  color: var(--xt-text-muted);
  flex-shrink: 0;
}
.ai-sidebar__delete {
  opacity: 0;
  position: absolute;
  right: 4px;
}
.ai-sidebar__item:hover .ai-sidebar__delete { opacity: 1; }
.ai-sidebar__empty {
  padding: var(--xt-space-8);
  text-align: center;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
}
</style>
```

- [ ] **Step 4: Rewrite AiWorkstation page**

```vue
<!-- frontend/src/views/ai/AiWorkstation.vue -->
<template>
  <div class="ai-workstation">
    <AiConversationList
      :conversations="store.conversations"
      :current-id="store.currentId"
      @new="handleNew"
      @select="store.loadMessages"
      @delete="store.deleteConversation"
    />
    <div class="ai-workstation__main">
      <div class="ai-workstation__messages" ref="messagesRef">
        <AiChatMessage v-for="(msg, i) in store.messages" :key="i" :msg="msg" />
        <div v-if="!store.messages.length" class="ai-workstation__welcome">
          <XtLogo variant="icon" />
          <h2>鑫泰 AI 助手</h2>
          <p>可以帮你查询生产数据、分析异常、生成报表</p>
        </div>
      </div>
      <div class="ai-workstation__input">
        <textarea
          v-model="input"
          placeholder="输入消息... (Shift+Enter 换行)"
          @keydown.enter.exact.prevent="send"
          rows="1"
        />
        <el-button
          v-if="store.streaming"
          type="danger"
          circle
          size="small"
          @click="store.stopGeneration"
        >
          <el-icon><VideoPause /></el-icon>
        </el-button>
        <el-button
          v-else
          type="primary"
          circle
          size="small"
          :disabled="!input.trim()"
          @click="send"
        >
          <el-icon><Promotion /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { Promotion, VideoPause } from '@element-plus/icons-vue'
import { useAiChatStore } from '@/stores/ai-chat'
import AiConversationList from './AiConversationList.vue'
import AiChatMessage from './AiChatMessage.vue'
import XtLogo from '@/components/xt/XtLogo.vue'

const store = useAiChatStore()
const input = ref('')
const messagesRef = ref(null)

onMounted(() => store.loadConversations())

watch(() => store.messages.length, () => {
  nextTick(() => {
    if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  })
})

async function handleNew() {
  await store.createConversation()
}

async function send() {
  const text = input.value.trim()
  if (!text) return
  if (!store.currentId) await store.createConversation()
  input.value = ''
  await store.sendMessage(text)
}
</script>

<style scoped>
.ai-workstation {
  display: flex;
  height: calc(100vh - var(--xt-topbar-height));
  margin: calc(-1 * var(--xt-space-6));
  margin-top: calc(-1 * var(--xt-space-6));
}
.ai-workstation__main {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.ai-workstation__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--xt-space-6);
}
.ai-workstation__welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--xt-text-muted);
  text-align: center;
  gap: var(--xt-space-3);
}
.ai-workstation__welcome h2 {
  font-size: var(--xt-text-xl);
  color: var(--xt-text);
}
.ai-workstation__welcome p {
  font-size: var(--xt-text-sm);
}
.ai-workstation__input {
  display: flex;
  align-items: flex-end;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3) var(--xt-space-6);
  border-top: 1px solid var(--xt-border-light);
  background: var(--xt-bg-panel);
}
.ai-workstation__input textarea {
  flex: 1;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-lg);
  padding: var(--xt-space-2) var(--xt-space-3);
  font-size: var(--xt-text-sm);
  resize: none;
  min-height: 40px;
  max-height: 120px;
  font-family: var(--xt-font-body);
  outline: none;
  transition: border-color var(--xt-motion-fast);
}
.ai-workstation__input textarea:focus {
  border-color: var(--xt-primary);
}
</style>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/ai/AiWorkstation.vue frontend/src/views/ai/AiConversationList.vue frontend/src/views/ai/AiChatMessage.vue frontend/src/stores/ai-chat.js
git commit -m "feat(ai): implement AI workstation with chat, conversation list, and SSE streaming"
```

---

### Task 29: Backend AI API endpoints

**Files:**
- Create: `backend/app/api/ai.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Create AI API router**

```python
# backend/app/api/ai.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import asyncio

router = APIRouter(prefix="/api/ai", tags=["ai"])

class ChatRequest(BaseModel):
    conversation_id: str
    message: str

class ConversationRename(BaseModel):
    title: str

# In-memory store (replace with DB in production)
conversations_db = {}

@router.get("/conversations")
async def list_conversations():
    return sorted(conversations_db.values(), key=lambda c: c.get("updated_at", ""), reverse=True)

@router.post("/conversations")
async def create_conversation():
    import uuid, datetime
    conv_id = str(uuid.uuid4())
    conv = {"id": conv_id, "title": "", "messages": [], "created_at": datetime.datetime.now().isoformat(), "updated_at": datetime.datetime.now().isoformat()}
    conversations_db[conv_id] = conv
    return conv

@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    if conv_id not in conversations_db:
        raise HTTPException(404, "Conversation not found")
    return conversations_db[conv_id]

@router.patch("/conversations/{conv_id}")
async def rename_conversation(conv_id: str, body: ConversationRename):
    if conv_id not in conversations_db:
        raise HTTPException(404, "Conversation not found")
    conversations_db[conv_id]["title"] = body.title
    return conversations_db[conv_id]

@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    conversations_db.pop(conv_id, None)
    return {"ok": True}

@router.post("/chat")
async def chat(req: ChatRequest):
    if req.conversation_id not in conversations_db:
        raise HTTPException(404, "Conversation not found")

    conv = conversations_db[req.conversation_id]
    conv["messages"].append({"role": "user", "content": req.message})

    async def generate():
        # Placeholder: echo back with MCP tool simulation
        response_text = f"收到你的消息：{req.message}。AI 工作台功能正在开发中，MCP 工具连接即将上线。"
        for char in response_text:
            yield f"data: {json.dumps({'type': 'text', 'content': char})}\n\n"
            await asyncio.sleep(0.02)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        conv["messages"].append({"role": "assistant", "content": response_text})

    return StreamingResponse(generate(), media_type="text/event-stream")

@router.post("/conversations/{conv_id}/stop")
async def stop_generation(conv_id: str):
    return {"ok": True}
```

- [ ] **Step 2: Register AI router in main.py**

Add to `backend/app/main.py`:
```python
from app.api.ai import router as ai_router
app.include_router(ai_router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/ai.py backend/app/main.py
git commit -m "feat(backend): add AI chat API with SSE streaming"
```

---

### Task 30: Backend search and export APIs

**Files:**
- Create: `backend/app/api/search.py`
- Create: `backend/app/api/export.py`

- [ ] **Step 1: Create search API**

```python
# backend/app/api/search.py
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["search"])

@router.get("/search")
async def global_search(q: str = Query(..., min_length=1)):
    # Placeholder: search across navigation, batches, master data
    results = {
        "navigation": [],
        "production": [],
        "master": []
    }
    # Scaffold: search implementation depends on database schema
    # Wire up actual queries when integrating with production DB
    return results
```

- [ ] **Step 2: Create export API**

```python
# backend/app/api/export.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import tempfile, csv, os

router = APIRouter(prefix="/api", tags=["export"])

class ExportRequest(BaseModel):
    format: str  # "csv" or "xlsx"
    filters: Optional[Dict[str, Any]] = None

@router.post("/export/{module}")
async def export_data(module: str, req: ExportRequest):
    # Placeholder: generate export file based on module and filters
    if req.format not in ("csv", "xlsx"):
        raise HTTPException(400, "Unsupported format")

    # Generate a temporary CSV as placeholder
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix=f'.{req.format}', delete=False, newline='')
    writer = csv.writer(tmp)
    writer.writerow(["id", "batch", "status", "created_at"])
    writer.writerow(["1", "BATCH-001", "normal", "2026-04-27"])
    tmp.close()

    return FileResponse(tmp.name, filename=f"{module}_export.{req.format}", media_type="application/octet-stream")
```

- [ ] **Step 3: Register routers in main.py**

```python
from app.api.search import router as search_router
from app.api.export import router as export_router
app.include_router(search_router)
app.include_router(export_router)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/search.py backend/app/api/export.py backend/app/main.py
git commit -m "feat(backend): add global search and data export APIs"
```

---

### Task 31: Backend notifications API

**Files:**
- Create: `backend/app/api/notifications.py`

- [ ] **Step 1: Create notifications API**

```python
# backend/app/api/notifications.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# In-memory store (replace with DB)
notifications_db = []

@router.get("")
async def list_notifications():
    return notifications_db

@router.get("/unread-count")
async def unread_count():
    return {"count": sum(1 for n in notifications_db if not n.get("read"))}

@router.post("/{notification_id}/read")
async def mark_read(notification_id: str):
    for n in notifications_db:
        if n["id"] == notification_id:
            n["read"] = True
            return {"ok": True}
    return {"ok": False}
```

- [ ] **Step 2: Register in main.py and commit**

```bash
git add backend/app/api/notifications.py backend/app/main.py
git commit -m "feat(backend): add notifications API"
```

---

### Task 32: Remove legacy code

**Files to delete:**
- `frontend/src/components/app/` (entire directory)
- `frontend/src/reference-command/components/` (entire directory)
- `frontend/src/reference-command/shells/` (entire directory)
- `frontend/src/reference-command/styles/` (entire directory)
- `frontend/src/design/ambient.css`
- `frontend/src/design/tokens.css`
- `frontend/src/design/tokens.js`
- `frontend/src/design/centerTheme.js`
- `frontend/src/design/status.js` (logic moved into XtStatus)
- `frontend/src/layout/ReviewShell.vue`
- `frontend/src/layout/AdminShell.vue`
- `frontend/src/views/Layout.vue`

**Files to modify:**
- `frontend/src/main.js` — remove legacy CSS imports
- `frontend/src/styles.css` — delete entirely (all styles now in xt-* files and scoped components)

- [ ] **Step 1: Remove old component directories**

```bash
rm -rf frontend/src/components/app/
rm -rf frontend/src/reference-command/components/
rm -rf frontend/src/reference-command/shells/
rm -rf frontend/src/reference-command/styles/
```

- [ ] **Step 2: Remove old design files**

```bash
rm frontend/src/design/ambient.css
rm frontend/src/design/tokens.css
rm frontend/src/design/tokens.js
rm frontend/src/design/centerTheme.js
rm frontend/src/design/status.js
```

- [ ] **Step 3: Remove old shell/layout files**

```bash
rm frontend/src/layout/ReviewShell.vue
rm frontend/src/layout/AdminShell.vue
rm frontend/src/views/Layout.vue
```

- [ ] **Step 4: Remove styles.css and update main.js**

Delete `frontend/src/styles.css`. Update `main.js` to remove all legacy imports:

```js
// Remove these lines from main.js:
// import './design/tokens.css'
// import './design/theme.css'
// import './styles.css'
// import './reference-command/styles/command-tokens.css'
// import './reference-command/styles/command-layout.css'
```

Keep only:
```js
import './design/xt-tokens.css'
import './design/xt-base.css'
import './design/xt-motion.css'
import './design/industrial.css'
```

- [ ] **Step 5: Remove old navigation config references**

Update `frontend/src/config/navigation.js` — keep only what's needed for the entry surface (if anything). The manage surface now uses `manage-navigation.js`.

- [ ] **Step 6: Verify build**

Run: `cd frontend && npx vite build --configLoader native 2>&1 | tail -10`
Expected: Build succeeds with no import errors

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: remove all legacy components, shells, styles, and tokens"
```

---

### Task 33: Final E2E test pass

**Files:**
- Modify: `frontend/e2e/` (update all existing tests)

- [ ] **Step 1: Update all E2E tests for new selectors**

Go through each E2E test file and update selectors to match new component structure:
- Replace `.cmd-*` selectors with `.xt-*` selectors
- Replace `.app-shell*` selectors with `.xt-manage*` or `.xt-entry*`
- Update route expectations (e.g., `/review/overview` → `/manage/overview`)
- Keep `data-testid` selectors (these should be preserved in new components)

- [ ] **Step 2: Run E2E tests**

Run: `cd frontend && npx playwright test --reporter=list 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 3: Fix any failing tests**

Address failures by updating selectors or adding missing `data-testid` attributes to new components.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/
git commit -m "test(e2e): update all E2E tests for new Xt component structure"
```

---

### Task 34: Final build verification and cleanup

- [ ] **Step 1: Full production build**

Run: `cd frontend && npx vite build --configLoader native`
Expected: Build succeeds, no warnings about missing imports

- [ ] **Step 2: Check bundle size**

Run: `ls -la frontend/dist/assets/ | sort -k5 -n`
Expected: No single chunk > 500KB

- [ ] **Step 3: Verify dev server starts**

Run: `cd frontend && npx vite --host 0.0.0.0 --port 5173` (user runs manually)
Expected: Dev server starts, pages render correctly

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final build verification and cleanup"
```
