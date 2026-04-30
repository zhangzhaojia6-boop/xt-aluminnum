# 移动填报端视觉收敛 — 设计规格

## 问题诊断

移动端 6 个 Vue 文件共 6000+ 行，存在以下视觉断裂：

| 维度 | UnifiedEntryForm | MobileEntry | CoilEntryWorkbench | ShiftReportForm | DynamicEntryForm |
|------|-----------------|-------------|-------------------|----------------|-----------------|
| CSS 变量 | 大量 fallback（`var(--xt-xx, #666)`） | 使用 xt token | 混合 | 独立体系 | 独立体系 |
| 身份栏 | `.ue-identity` sticky | `.mobile-entry-stage__identity` | `.coil-identity` | `.mobile-top` | `.mobile-top` |
| 卡片容器 | `.ue-fields` 自定义 shadow | 无卡片 | `.coil-list` | `.entry-flow-layout` | `.entry-form-groups` |
| 输入框 | `.ue-input` 44px | 无输入 | 自定义 | el-input | el-input |
| 提交按钮 | `.ue-submit` 自定义 | el-button | 自定义 | el-button | el-button |
| 动画 | 无 | reveal 动画 | 无 | 无 | 无 |

核心问题：
1. UnifiedEntryForm 有 30+ 处 CSS fallback 值（`var(--xt-xx, #hardcoded)`），应直接用 token 无 fallback
2. 五个页面的身份栏各自实现，样式不统一
3. ShiftReportForm 和 DynamicEntryForm 用 Element Plus 默认组件，与 DESIGN-MOBILE.md 的"不用 el-form-item"规则冲突
4. 输入框高度不一致（44px vs Element Plus 默认 32px）

## 设计方向

已有 `DESIGN-MOBILE.md` 作为权威规范。本次改造不重新设计，而是让代码严格对齐规范。

**视觉论点：** 工业精密仪表感——深色身份栏锚定身份，浅色表单区大字号录入，角色用色条区分。

**改造原则：** 只动 CSS，不改 JS 逻辑和数据流。

## 改造清单

### 1. UnifiedEntryForm.vue — 清除所有 CSS fallback

当前 30+ 处 `var(--xt-xxx, #fallback)` 模式，全部改为 `var(--xt-xxx)` 无 fallback。

精确替换列表：

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
var(--xt-font-number, ...)        → var(--xt-font-number)
```

同时替换残留的硬编码 shadow：
```
box-shadow: 0 1px 3px rgba(0,0,0,0.06)  → box-shadow: var(--xt-shadow-sm)
box-shadow: 0 0 0 3px rgba(59,130,246,0.12) → box-shadow: var(--app-focus-ring)
background: rgba(59,130,246,0.08) → background: var(--xt-primary-soft)
```

### 2. UnifiedEntryForm.vue — 输入框高度对齐 DESIGN-MOBILE.md

当前 `.ue-input` 是 `min-height: 44px`，DESIGN-MOBILE.md 规定 48px：

```css
.ue-input {
  min-height: 48px;  /* was 44px */
}
```

### 3. UnifiedEntryForm.vue — 卡片容器对齐规范

当前 `.ue-fields` 用硬编码 shadow 和 radius：
```css
/* 当前 */
border-radius: 12px;
box-shadow: 0 1px 3px rgba(0,0,0,0.06);

/* 改为 */
border-radius: var(--xt-radius-xl);
box-shadow: var(--xt-shadow-sm);
```

### 4. UnifiedEntryForm.vue — 删除残留的 .ue-identity__logout 样式

`.ue-identity__logout` 按钮已在之前的改造中从模板删除，但 CSS 规则仍在（lines 384-392）。删除这段死代码。

### 5. MobileEntry.vue — 清除 CSS fallback

当前 `.mobile-entry-stage__facts-label` 有 fallback：
```
color: var(--xt-text-tertiary, #999) → color: var(--xt-text-muted)
```

### 6. CoilEntryWorkbench.vue — 身份栏对齐

当前 `.coil-identity` 的白色文字用 `rgba(255, 255, 255, 0.92/0.55/0.82)`。这些是合理的深色背景上的透明度变体，保留不动。但确认 border-left 色条存在且使用 `var(--role-color)`。

### 7. ShiftReportForm.vue — 清除残留硬编码

`color: var(--xt-text-inverse)` 已在上一轮替换。检查是否还有其他硬编码。

## 不改的部分

- 所有 JS 逻辑、数据获取、computed 属性
- MobileEntry 的 hero 区域布局（已经符合规范）
- CoilEntryWorkbench 的深色背景白色文字透明度变体（合理设计模式）
- DynamicEntryForm 和 ShiftReportForm 的 Element Plus 组件使用（改造范围过大，留给第二轮）
- MobileBottomNav 的结构（功能性组件，不涉及视觉收敛）

## 验收标准

1. UnifiedEntryForm.vue 中不再出现任何 `var(--xt-xxx, #fallback)` 模式
2. 输入框最小高度统一为 48px
3. 卡片容器使用 `--xt-radius-xl` 和 `--xt-shadow-sm`
4. 无死代码（.ue-identity__logout 已删除）
5. `npx vite build` 零错误
