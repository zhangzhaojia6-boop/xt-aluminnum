# 管理端仪表盘层级清晰化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 三个管理端仪表盘建立明确的视觉层级——第一眼看到核心数字，详情按需展开，视觉语言统一。

**Architecture:** FactoryDirector 砍战争室、精简 hero 为 3 卡片；Statistics 15 卡片分组收纳为 5+折叠；三端统一 stat-card 和表格样式。

**Tech Stack:** Vue 3, Element Plus, CSS custom properties (xt-tokens)

---

### Task 1: FactoryDirector——砍战争室，精简首屏（Claude Code）

**Files:**
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`

- [ ] **Step 1: Remove war room section from template**

Remove the entire `.review-home-hero__war-room` div (lines ~25-39), which contains:
- `<XtFactoryMap>` component
- `.review-home-hero__execution` div with `<XtExecutionRail>`

- [ ] **Step 2: Remove workshop ribbon**

Remove `.review-home-hero__workshop-ribbon` section (lines ~42-54) with `<XtWorkshopGlyph>` buttons.

- [ ] **Step 3: Restructure hero grid to 3 core cards**

Replace the current `.review-home-hero__grid` (which has 6 heroCards via ReviewCommandDeck + AgentRuntimeFlow) with 3 inline stat cards:

```html
<div class="review-home-hero__core-metrics">
  <div class="core-metric-card">
    <div class="core-metric-card__label">今日产量</div>
    <div class="core-metric-card__value">{{ formatNumber(leaderMetrics.today_total_output) }}</div>
    <div class="core-metric-card__unit">吨</div>
  </div>
  <div class="core-metric-card">
    <div class="core-metric-card__label">缺报班次</div>
    <div class="core-metric-card__value core-metric-card__value--alert"
         v-if="leaderMetrics.unreported_shift_count > 0">
      {{ leaderMetrics.unreported_shift_count }}
    </div>
    <div class="core-metric-card__value" v-else>0</div>
  </div>
  <div class="core-metric-card">
    <div class="core-metric-card__label">异常与退回</div>
    <div class="core-metric-card__value core-metric-card__value--alert"
         v-if="factoryAbnormalCount > 0">
      {{ factoryAbnormalCount }}
    </div>
    <div class="core-metric-card__value" v-else>0</div>
  </div>
</div>
```

- [ ] **Step 4: Add second-tier metrics row**

Below the 3 core cards, add a secondary row with smaller cards:

```html
<div class="review-home-hero__secondary-metrics">
  <div class="secondary-metric">
    <span class="secondary-metric__label">交付进度</span>
    <strong class="secondary-metric__value">{{ delivery.delivery_ready ? '可交付' : '未就绪' }}</strong>
  </div>
  <div class="secondary-metric">
    <span class="secondary-metric__label">单吨能耗</span>
    <strong class="secondary-metric__value">{{ formatNumber(leaderMetrics.energy_per_ton) }}</strong>
  </div>
  <div class="secondary-metric">
    <span class="secondary-metric__label">月累计</span>
    <strong class="secondary-metric__value">{{ formatNumber(monthToDateOutput) }} 吨</strong>
  </div>
</div>
```

- [ ] **Step 5: Remove unused imports and computed properties**

Remove imports: `XtFactoryMap`, `XtExecutionRail`, `XtWorkshopGlyph`.
Remove computed properties related to war room: `factoryMapNodes`, `factoryMapLines`, `factoryMapAlerts`, `factoryExecutionSteps`, `factoryExecutionActiveIndex`, `factoryDirectorBrief`, `workshopGlyphs`.
Remove `heroCards` computed and `ReviewCommandDeck` from hero section (keep it if used elsewhere).

- [ ] **Step 6: Clean up CSS**

Remove styles for: `.review-home-hero__war-room`, `.review-home-hero__execution`, `.review-home-hero__workshop-ribbon`, `.review-home-hero__workshop-card`.

Add styles for `.core-metric-card` and `.secondary-metric`:

```css
.review-home-hero__core-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--xt-space-4);
  margin-top: var(--xt-space-4);
}

.core-metric-card {
  background: var(--xt-bg-panel);
  border-radius: var(--xt-radius-xl);
  padding: var(--xt-space-5) var(--xt-space-4);
  text-align: center;
  box-shadow: var(--xt-shadow-sm);
}

.core-metric-card__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--xt-text-secondary);
  letter-spacing: 0.02em;
}

.core-metric-card__value {
  font-family: var(--xt-font-number);
  font-size: 36px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin-top: var(--xt-space-2);
}

.core-metric-card__value--alert {
  color: var(--xt-danger);
}

.core-metric-card__unit {
  font-size: 13px;
  color: var(--xt-text-muted);
  margin-top: 2px;
}

.review-home-hero__secondary-metrics {
  display: flex;
  gap: var(--xt-space-4);
  margin-top: var(--xt-space-3);
}

.secondary-metric {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3) var(--xt-space-4);
  background: var(--xt-bg-panel);
  border-radius: var(--xt-radius-lg);
  box-shadow: var(--xt-shadow-xs);
}

.secondary-metric__label {
  font-size: 13px;
  color: var(--xt-text-muted);
}

.secondary-metric__value {
  font-family: var(--xt-font-number);
  font-size: 18px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 7: Move detail stat cards into tabs**

The 8 stat cards in `.stat-grid` (lines ~100-179) should move into the "关注" tab pane, replacing the current `el-descriptions`. This consolidates all detail data into the tabbed area.

- [ ] **Step 8: Verify in browser**

Open FactoryDirector. Confirm:
- First screen: 3 large metric cards (产量, 缺报, 异常)
- Below: 3 secondary metrics (交付, 能耗, 月累计)
- "展开运行详情" toggle still works
- Tabs still functional with reporting table
- No war room, no workshop ribbon

- [ ] **Step 9: Commit**

```bash
git add frontend/src/views/dashboard/FactoryDirector.vue
git commit -m "refactor: FactoryDirector — 3-card hero, remove war room, establish visual hierarchy"
```

---

### Task 2: Statistics——分组收纳（Claude Code）

**Files:**
- Modify: `frontend/src/views/dashboard/Statistics.vue`

- [ ] **Step 1: Split 15 stat cards into core (5) + secondary (10)**

Wrap the first 5 cards in `.stat-grid--core`:
- 待处理班次
- 手机上报率
- 未报班次
- 未处理差异
- 交付状态

Wrap the remaining 10 in a collapsible section:

```html
<div class="stat-grid stat-grid--core stat-reveal stat-reveal--1" v-loading="loading">
  <!-- 5 core cards -->
</div>

<div class="stat-more-toggle" v-if="!moreMetricsExpanded">
  <button type="button" @click="moreMetricsExpanded = true" class="stat-more-btn">
    展开更多指标 ({{ 10 }})
  </button>
</div>

<div v-show="moreMetricsExpanded" class="stat-grid stat-reveal stat-reveal--1">
  <!-- 10 secondary cards -->
</div>
```

Add `const moreMetricsExpanded = ref(false)` to script.

- [ ] **Step 2: Wrap tables in el-collapse**

Replace the flat card stack with `el-collapse`:

```html
<el-collapse v-model="expandedPanels" class="stat-reveal stat-reveal--2">
  <el-collapse-item title="MES 同步状态" name="mes">
    <!-- existing MES descriptions -->
  </el-collapse-item>
  <el-collapse-item title="成品率矩阵" name="yield">
    <!-- existing yield matrix content -->
  </el-collapse-item>
  <el-collapse-item title="合同泳道" name="contract">
    <!-- existing contract lane content -->
  </el-collapse-item>
  <el-collapse-item title="待处理班次" name="pending">
    <!-- existing pending shifts table -->
  </el-collapse-item>
  <el-collapse-item title="提醒汇总" name="reminder">
    <!-- existing reminder table -->
  </el-collapse-item>
</el-collapse>
```

Add `const expandedPanels = ref(['pending'])` — only "待处理班次" expanded by default.

- [ ] **Step 3: Style the collapse and toggle**

```css
.stat-grid--core {
  /* Same as stat-grid but visually emphasized */
}

.stat-more-toggle {
  text-align: center;
  padding: var(--xt-space-3) 0;
}

.stat-more-btn {
  background: none;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-pill);
  padding: var(--xt-space-2) var(--xt-space-5);
  font-size: 13px;
  color: var(--xt-text-secondary);
  cursor: pointer;
  transition: all var(--xt-motion-fast);
}

.stat-more-btn:hover {
  border-color: var(--xt-primary);
  color: var(--xt-primary);
}
```

- [ ] **Step 4: Verify in browser**

Open Statistics. Confirm:
- First screen: 5 core stat cards
- "展开更多指标 (10)" button below
- Clicking expands remaining 10 cards
- Tables in collapse, only "待处理班次" expanded by default
- All data still accessible

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/dashboard/Statistics.vue
git commit -m "refactor: Statistics — 5 core cards + collapsible secondary, tables in accordion"
```

---

### Task 3: 三端视觉统一——stat-card 样式收敛（Claude Code）

**Files:**
- Modify: `frontend/src/design/xt-base.css` (or create `frontend/src/design/dashboard-shared.css`)
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue` (scoped styles)
- Modify: `frontend/src/views/dashboard/WorkshopDirector.vue` (scoped styles)
- Modify: `frontend/src/views/dashboard/Statistics.vue` (scoped styles)

- [ ] **Step 1: Audit current stat-card styles across 3 dashboards**

Check if `.stat-card`, `.stat-label`, `.stat-value` are defined in scoped styles or shared CSS. Identify inconsistencies.

- [ ] **Step 2: Consolidate stat-card into shared CSS**

If stat-card styles are duplicated across scoped styles, extract to `xt-base.css`:

```css
.stat-card {
  background: var(--xt-bg-panel);
  border-radius: var(--xt-radius-xl);
  padding: var(--xt-space-4);
  box-shadow: var(--xt-shadow-sm);
}

.stat-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--xt-text-secondary);
  letter-spacing: 0.02em;
}

.stat-value {
  font-family: var(--xt-font-number);
  font-size: 28px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.015em;
  line-height: 1.15;
  margin-top: var(--xt-space-1);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--xt-space-3);
}
```

- [ ] **Step 3: Unify responsive breakpoints**

Add consistent media queries:

```css
@media (max-width: 900px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: Remove duplicate stat-card styles from scoped sections**

In each dashboard's `<style scoped>`, remove any `.stat-card`, `.stat-label`, `.stat-value`, `.stat-grid` definitions that are now in shared CSS.

- [ ] **Step 5: Unify table styling**

Add shared dashboard table class:

```css
.dashboard-table {
  --el-table-border-color: var(--xt-border-light);
  --el-table-header-bg-color: var(--xt-bg-page);
  font-size: 13px;
}
```

Apply `.dashboard-table` class to all `el-table` instances in the three dashboards.

- [ ] **Step 6: Verify in browser**

Open all three dashboards. Confirm:
- Stat cards look identical across all three
- Tables have consistent styling
- Responsive behavior is consistent at 900px and 600px breakpoints

- [ ] **Step 7: Commit**

```bash
git add frontend/src/design/ frontend/src/views/dashboard/
git commit -m "style: unify stat-card, table, and responsive styles across dashboards"
```
