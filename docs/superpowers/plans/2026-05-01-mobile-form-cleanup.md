# Mobile Form Cleanup — Implementation Plan

> **For agentic workers:** Execute tasks in order. Each task has exact file paths and code.

**Goal:** Clean up CSS hardcoded values, remove dead code (external trace card, voice stubs), and align remaining mobile forms to xt design token system.

**Architecture:** CSS refactoring + dead code removal. No JS logic changes.

**Tech Stack:** Vue 3 scoped CSS, xt-tokens.css

---

### Task 1: DynamicEntryForm.vue — CSS token migration

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue` (lines 2245-2387, `<style scoped>`)

- [ ] **Step 1: Replace font-family fallbacks**

Find (replace_all):
```
var(--font-display, 'SF Pro Display', system-ui)
```
Replace with:
```
var(--xt-font-display)
```

Find (replace_all):
```
var(--font-number, 'SF Pro Display', 'DIN Alternate', system-ui)
```
Replace with:
```
var(--xt-font-number)
```

- [ ] **Step 2: Replace private shadow variable**

Find (replace_all):
```
box-shadow: var(--shadow-card);
```
Replace with:
```
box-shadow: var(--xt-shadow-sm);
```

- [ ] **Step 3: Replace hardcoded border-radius values**

In the `<style scoped>` block only:

Find the rule at line 2315:
```css
  border-radius: 16px;
```
(inside `.mobile-shell--entry-form :deep(.panel.mobile-card)`)
Replace with:
```css
  border-radius: var(--xt-radius-2xl);
```

Find the rule at line 2323:
```css
  border-radius: 14px;
```
(inside the `.mobile-static-chip, .mobile-summary-chip, .mobile-history-item, .mobile-inline-state` rule)
Replace with:
```css
  border-radius: var(--xt-radius-xl);
```

Find the rule at line 2302:
```css
  border-radius: 12px;
```
(inside `.mobile-sticky-actions__buttons .el-button`)
Replace with:
```css
  border-radius: var(--xt-radius-lg);
```

Find the rule at line 2334:
```css
  border-radius: 12px;
```
(inside `.mobile-inline-actions .el-button, .mobile-actions .el-button`)
Replace with:
```css
  border-radius: var(--xt-radius-lg);
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "style: migrate DynamicEntryForm CSS to xt design tokens"
```

---

### Task 2: DynamicEntryForm.vue — Delete external trace card

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

- [ ] **Step 1: Delete the external trace card from template**

Find and delete this entire block (approximately lines 158-165):
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

Replace with empty string (delete it).

- [ ] **Step 2: Delete the external trace CSS**

Find and delete this entire block (approximately lines 2337-2356):
```css
.entry-external-trace {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.entry-external-trace span {
  min-width: 0;
  padding: 9px 10px;
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-weight: 850;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

Replace with empty string (delete it).

- [ ] **Step 3: Verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

Run: `grep -n "entry-external-trace" frontend/src/views/mobile/DynamicEntryForm.vue`
Expected: Zero matches.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "fix: remove placeholder external trace card from DynamicEntryForm"
```

---

### Task 3: DynamicEntryForm.vue — Remove voice input stubs

**Files:**
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

- [ ] **Step 1: Remove voice-related template blocks**

There are 7 occurrences of voice button blocks in the template. Each looks like this pattern:

```html
                      <el-button
                        v-if="isVoiceFieldSupported(field)"
                        text
                        type="primary"
                        size="small"
                        :disabled="isEntryEditingDisabled"
                        @click.stop="toggleVoicePrefill(field)"
                      >
                        {{ voiceListeningField === field.name ? '停止语音' : '语音录入' }}
                      </el-button>
```

Find and delete ALL 7 occurrences of this pattern. The blocks appear at approximately these line ranges:
- Lines 231-240
- Lines 285-294
- Lines 353-362
- Lines 391-400
- Lines 449-458
- Lines 486-495
- Lines 516-525

Each block starts with `<el-button` and `v-if="isVoiceFieldSupported(field)"` and ends with `</el-button>`.

Delete each occurrence (replace with empty string).

- [ ] **Step 2: Remove voice-related script code**

Find and delete the `voiceListeningField` ref declaration:
```javascript
const voiceListeningField = ref('')
```

Find and delete the `isVoiceFieldSupported` function:
```javascript
function isVoiceFieldSupported(_field) {
  return false
}
```

Find and delete the `toggleVoicePrefill` function:
```javascript
function toggleVoicePrefill(_field) {
  voiceListeningField.value = ''
}
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

Run: `grep -n "isVoiceFieldSupported\|toggleVoicePrefill\|voiceListeningField" frontend/src/views/mobile/DynamicEntryForm.vue`
Expected: Zero matches.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "fix: remove dead voice input stubs from DynamicEntryForm"
```

---

### Task 4: ShiftReportForm.vue — CSS token migration

**Files:**
- Modify: `frontend/src/views/mobile/ShiftReportForm.vue` (line 821-822)

- [ ] **Step 1: Replace font-family**

Find (in the `<style scoped>` block):
```css
  font-family: var(--font-number);
```

Replace with:
```css
  font-family: var(--xt-font-number);
```

- [ ] **Step 2: Replace hardcoded font-size**

Find (in the same `.entry-calc-strip strong` rule, line 822):
```css
  font-size: 24px;
```

Replace with:
```css
  font-size: var(--xt-text-2xl);
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/mobile/ShiftReportForm.vue
git commit -m "style: migrate ShiftReportForm CSS to xt design tokens"
```

---

### Task 5: Final verification

- [ ] **Step 1: Full build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds with zero errors.

- [ ] **Step 2: Verify no private CSS variables remain**

Run: `grep -rn "var(--font-display\|var(--font-number[^)])\|var(--shadow-card" frontend/src/views/mobile/`
Expected: Zero matches (no private font/shadow variables).

- [ ] **Step 3: Verify no hardcoded border-radius in DynamicEntryForm**

Run: `grep -n "border-radius: 1[2-6]px" frontend/src/views/mobile/DynamicEntryForm.vue`
Expected: Zero matches.

- [ ] **Step 4: Verify external trace card removed**

Run: `grep -n "entry-external-trace\|entry-mes-trace" frontend/src/views/mobile/DynamicEntryForm.vue`
Expected: Zero matches.

- [ ] **Step 5: Verify voice stubs removed**

Run: `grep -n "isVoiceFieldSupported\|toggleVoicePrefill\|voiceListeningField" frontend/src/views/mobile/DynamicEntryForm.vue`
Expected: Zero matches.
