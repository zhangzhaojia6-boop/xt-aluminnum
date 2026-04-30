# Dashboard Visual Convergence — Implementation Plan

> **For agentic workers:** Execute tasks in order. Each task has exact file paths and code. Steps use checkbox syntax for tracking.

**Goal:** Unify the visual language of FactoryDirector, WorkshopDirector, and Statistics dashboards by migrating all styles to the xt design token system.

**Architecture:** Pure CSS refactoring — replace private CSS variables with xt tokens, unify stat-card/panel/grid styles, add reveal animations to Statistics.

**Tech Stack:** Vue 3 scoped CSS, xt-tokens.css design system

---

### Task 1: Statistics.vue — Replace private CSS variables with xt tokens

**Files:**
- Modify: `frontend/src/views/dashboard/Statistics.vue` (lines 241-298, `<style scoped>` block)

- [ ] **Step 1: Replace the entire `<style scoped>` block**

Find the current `<style scoped>` section (starts at line 241) and replace it with:

```css
<style scoped>
.page-stack {
  padding: var(--xt-space-4);
  background: var(--xt-bg-page);
  min-height: 100vh;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--xt-space-3);
  margin-bottom: var(--xt-space-4);
}

.stat-card {
  padding: var(--xt-space-4);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  box-shadow: var(--xt-shadow-sm);
  transition: transform var(--xt-motion-fast) var(--xt-ease),
              box-shadow var(--xt-motion-fast) var(--xt-ease),
              border-color var(--xt-motion-fast) ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  border-color: var(--xt-primary-border);
  box-shadow: var(--xt-shadow-md);
}

.stat-label {
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-bottom: var(--xt-space-1);
}

.stat-value {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 700;
  color: var(--xt-text);
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
}

.panel {
  padding: var(--xt-space-4);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  box-shadow: var(--xt-shadow-sm);
  margin-bottom: var(--xt-space-3);
}

.header-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--xt-space-4);
}

.note {
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
}

.stat-reveal {
  opacity: 0;
  transform: translateY(8px);
  animation: stat-reveal 0.24s var(--xt-ease) forwards;
}

.stat-reveal--1 { animation-delay: 0.02s; }
.stat-reveal--2 { animation-delay: 0.04s; }
.stat-reveal--3 { animation-delay: 0.06s; }

@keyframes stat-reveal {
  to { opacity: 1; transform: translateY(0); }
}
</style>
```

- [ ] **Step 2: Add reveal animation classes to template**

In the `<template>` section, add animation classes:

1. On the `.stat-grid` div (line 14), add class `stat-reveal stat-reveal--1`:
   ```html
   <div class="stat-grid stat-reveal stat-reveal--1" v-loading="loading">
   ```

2. On the first `el-card.panel` (line 77), add class `stat-reveal stat-reveal--2`:
   ```html
   <el-card class="panel stat-reveal stat-reveal--2" v-loading="loading">
   ```

3. On the second `el-card.panel` (line 87), add class `stat-reveal stat-reveal--2`:
   ```html
   <el-card class="panel stat-reveal stat-reveal--2" v-loading="loading">
   ```

4. On remaining `el-card.panel` elements, add `stat-reveal stat-reveal--3`.

- [ ] **Step 3: Update page header to eyebrow pattern**

Replace the current page header (lines 3-11):
```html
<div class="page-header">
  <div>
    <h1>统计观察看板</h1>
  </div>
  <div class="header-actions">
```

With:
```html
<div class="page-header">
  <div>
    <div class="page-eyebrow">数据观察</div>
    <h1>统计看板</h1>
  </div>
  <div class="header-actions">
```

Add the eyebrow style to the `<style scoped>` block:
```css
.page-eyebrow {
  font-size: var(--xt-text-xs);
  letter-spacing: 0.02em;
  color: var(--xt-text-muted);
}

.page-header h1 {
  margin: 0;
  font-size: var(--xt-text-2xl);
  line-height: 1.16;
  letter-spacing: 0;
  color: var(--xt-text);
}
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds with no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/dashboard/Statistics.vue
git commit -m "style: migrate Statistics dashboard to xt design tokens"
```

---

### Task 2: FactoryDirector.vue — Unify stat-grid to auto-fit

**Files:**
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`

- [ ] **Step 1: Replace fixed 4-column grid with auto-fit**

Find (around line 999):
```css
.review-factory .stat-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
```

Replace with:
```css
.review-factory .stat-grid {
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--xt-space-3);
}
```

- [ ] **Step 2: Remove redundant media queries**

Delete these media query blocks (they are no longer needed with auto-fit):

```css
@media (max-width: 1280px) {
  .review-factory .stat-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .review-factory .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
```

- [ ] **Step 3: Unify stat-card min-height**

Find:
```css
.review-factory .stat-card {
  min-height: 116px;
  padding: 15px;
}
```

Replace with:
```css
.review-factory .stat-card {
  padding: var(--xt-space-4);
}
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/dashboard/FactoryDirector.vue
git commit -m "style: unify FactoryDirector stat-grid to responsive auto-fit"
```

---

### Task 3: WorkshopDirector.vue — Align stat-grid gap to token

**Files:**
- Modify: `frontend/src/views/dashboard/WorkshopDirector.vue`

- [ ] **Step 1: Replace hardcoded gap**

Find (around line 506-510):
```css
.review-workshop__metric-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}
```

Replace with:
```css
.review-workshop__metric-grid {
  display: grid;
  gap: var(--xt-space-3);
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/dashboard/WorkshopDirector.vue
git commit -m "style: align WorkshopDirector grid gap to xt token"
```

---

### Task 4: Final build verification

- [ ] **Step 1: Full build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds with zero errors.

- [ ] **Step 2: Verify no private CSS variables remain in Statistics**

Run: `grep -n 'card-bg\|card-border\|shadow-card\|text-muted\|text-main\|font-number\|radius-card' frontend/src/views/dashboard/Statistics.vue`
Expected: No matches (zero output).

- [ ] **Step 3: Commit all if not already committed**

```bash
git status
```
