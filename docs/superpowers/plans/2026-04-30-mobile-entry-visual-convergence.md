# Mobile Entry Visual Convergence — Implementation Plan

> **For agentic workers:** Execute tasks in order. Each task has exact file paths and code.

**Goal:** Align mobile entry forms to the xt design token system and DESIGN-MOBILE.md spec by removing all CSS fallback values, unifying input heights, and cleaning dead code.

**Architecture:** Pure CSS refactoring — no JS changes.

**Tech Stack:** Vue 3 scoped CSS, xt-tokens.css

---

### Task 1: UnifiedEntryForm.vue — Remove all CSS fallback values

**Files:**
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue` (lines 350-635, `<style scoped>`)

- [ ] **Step 1: Replace all var() with fallback to var() without fallback**

Use find-and-replace (replace_all) for each pattern. Order matters — do longer patterns first to avoid partial matches.

```
var(--xt-bg-page, #f5f5f7)        → var(--xt-bg-page)
var(--xt-bg-ink, #1a1a2e)         → var(--xt-bg-ink)
var(--xt-text-secondary, #666)    → var(--xt-text-secondary)
var(--xt-text-danger, #d32f2f)    → var(--xt-danger)
var(--xt-primary, #3b82f6)        → var(--xt-primary)
var(--xt-text-tertiary, #999)     → var(--xt-text-muted)
var(--xt-bg-panel, #fff)          → var(--xt-bg-panel)
var(--xt-text-primary, #222)      → var(--xt-text)
var(--xt-border-default, #ddd)    → var(--xt-border)
var(--xt-border-light, #eee)      → var(--xt-border-light)
var(--xt-font-number, 'Bahnschrift', monospace) → var(--xt-font-number)
```

- [ ] **Step 2: Replace hardcoded shadows**

Find and replace these exact strings (replace_all):

```
box-shadow: 0 1px 3px rgba(0,0,0,0.06)          → box-shadow: var(--xt-shadow-sm)
box-shadow: 0 0 0 3px rgba(59,130,246,0.12)      → box-shadow: var(--app-focus-ring)
background: rgba(59,130,246,0.08)                 → background: var(--xt-primary-soft)
```

- [ ] **Step 3: Replace hardcoded border-radius**

Find all `border-radius: 12px` in the style block and replace with `border-radius: var(--xt-radius-xl)` (replace_all).

Find `border-radius: 6px` and replace with `border-radius: var(--xt-radius-md)` (replace_all).

- [ ] **Step 4: Verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/mobile/UnifiedEntryForm.vue
git commit -m "style: remove all CSS fallback values from UnifiedEntryForm"
```

---

### Task 2: UnifiedEntryForm.vue — Fix input height and delete dead code

**Files:**
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue`

- [ ] **Step 1: Update input min-height from 44px to 48px**

Find in the `<style scoped>` block:
```css
  min-height: 44px;
```

Replace with:
```css
  min-height: 48px;
```

(This should appear once, in the `.ue-input` rule.)

- [ ] **Step 2: Delete dead .ue-identity__logout CSS rule**

Find and delete this entire block (approximately lines 384-392):
```css
.ue-identity__logout {
  background: none;
  border: 1px solid rgba(255,255,255,0.25);
  color: rgba(255,255,255,0.7);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}
```

Replace with empty string (delete it).

- [ ] **Step 3: Replace `#fff` in .ue-identity color**

Find in `.ue-identity`:
```css
  color: #fff;
```

Replace with:
```css
  color: var(--xt-text-inverse);
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/mobile/UnifiedEntryForm.vue
git commit -m "style: fix input height to 48px and remove dead logout CSS"
```

---

### Task 3: MobileEntry.vue — Clean CSS fallback

**Files:**
- Modify: `frontend/src/views/mobile/MobileEntry.vue`

- [ ] **Step 1: Replace fallback pattern**

Find (replace_all):
```
var(--xt-text-tertiary, #999)  → var(--xt-text-muted)
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/mobile/MobileEntry.vue
git commit -m "style: remove CSS fallback from MobileEntry"
```

---

### Task 4: Final verification

- [ ] **Step 1: Full build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds with zero errors.

- [ ] **Step 2: Verify no fallback patterns remain in UnifiedEntryForm**

Run: `grep -n 'var(--xt-[a-z].*,' frontend/src/views/mobile/UnifiedEntryForm.vue | grep -v '//'`
Expected: Zero matches.

- [ ] **Step 3: Verify no dead .ue-identity__logout**

Run: `grep -n 'ue-identity__logout' frontend/src/views/mobile/UnifiedEntryForm.vue`
Expected: Zero matches.
