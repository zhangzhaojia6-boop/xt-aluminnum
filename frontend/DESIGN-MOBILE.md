# Mobile Collection Redesign — DESIGN.md

## 1. Visual Theme and Atmosphere

工业精密仪表感。深色身份栏锚定"我是谁、在哪、什么班次"，浅色表单区大字号录入，角色用顶部色条区分而非文字堆砌。整体节奏：一屏一任务，数字突出，标签退后。不追求"好看"，追求"一眼看懂、手指不犯错"。

## 2. Color Palette and Roles

沿用现有 xt-tokens.css OKLCH 体系，新增角色色条语义：

| Token | Value | Role |
|---|---|---|
| `--m-role-operator` | `oklch(51% 0.17 255)` | 主操（复用 primary） |
| `--m-role-energy` | `oklch(52% 0.13 158)` | 电工（复用 success 绿） |
| `--m-role-maintenance` | `oklch(61% 0.12 75)` | 机修（复用 warning 琥珀） |
| `--m-role-hydraulic` | `oklch(54% 0.095 54)` | 液压（复用 accent 金） |
| `--m-role-consumable` | `oklch(50% 0.15 252)` | 耗材统计（复用 info 蓝） |
| `--m-role-qc` | `oklch(55% 0.15 28)` | 质检（复用 danger 红） |
| `--m-role-weigher` | `oklch(43% 0.032 250)` | 称重（复用 text-secondary） |
| `--m-role-utility` | `oklch(52% 0.13 158)` | 水电气（绿） |
| `--m-role-inventory` | `oklch(54% 0.095 54)` | 成品库（金） |
| `--m-role-contracts` | `oklch(51% 0.17 255)` | 计划科（蓝） |

表单背景：`--xt-bg-page`（浅灰）
卡片背景：`--xt-bg-panel`（近白）
身份栏背景：`--xt-bg-ink`（深色）

## 3. Typography Rules

| Level | Size | Weight | Line-height | Letter-spacing | Use |
|---|---|---|---|---|---|
| 身份栏角色名 | 20px (`--xt-text-xl`) | 850 | 1.18 | -0.012em | 顶部角色标识 |
| 身份栏副信息 | 13px (`--xt-text-sm`) | 400 | 1.5 | normal | 车间、班次、日期 |
| 卡片标题 | 13px (`--xt-text-sm`) | 700 | 1.5 | 0.02em | 分段标题，大写感 |
| 字段标签 | 16px (`--xt-text-lg`) | 850 | 1.35 | normal | 输入字段名 |
| 数值显示 | 24px (`--xt-text-2xl`) | 900 | 1.1 | -0.012em | 汇总数字 |
| 数值输入 | 16px (`--xt-text-lg`) | 400 | 1.5 | normal | 表单输入 |

数字一律用 `--xt-font-number`（Bahnschrift），`font-variant-numeric: tabular-nums`。

## 4. Component Stylings

**身份栏（Role Identity Bar）**
- 深色背景 `--xt-bg-ink`，左侧角色色条 3px
- 角色名白色 850 weight，副信息 `rgba(255,255,255,0.6)`
- 固定在顶部，不随滚动

**录入卡片（Entry Card）**
- 白色背景，`--xt-radius-xl` 圆角，`--xt-shadow-sm` 阴影
- 顶部 2px 色条标识数据类别
- 聚焦态：shadow 从 sm 升到 md，transition 180ms

**数值输入框**
- 48px 最小高度，`--xt-radius-lg` 圆角
- 聚焦态：border 变 primary，外发光 `--app-focus-ring`
- 数字右对齐，单位标签右侧灰色

**提交按钮**
- 全宽，48px 高，`--xt-radius-lg`
- `active:scale(0.96)` 按压反馈
- 主色背景，白色文字

**卷列表项（Coil List Item）**
- 水平布局：卷号左对齐，投入/产出右对齐
- 底部 1px 分割线 `--xt-border-light`
- 点击展开详情

## 5. Layout Principles

- 移动端最大宽度 560px，居中
- 垂直间距 12px（`--xt-space-3`）
- 卡片内间距 16px（`--xt-space-4`）
- 表单字段间距 12px
- 底部安全区 `calc(104px + env(safe-area-inset-bottom))`
- 一屏一任务：每个分段（用电/天然气/用水）独立卡片

## 6. Depth and Elevation

| Level | Surface | Shadow | Use |
|---|---|---|---|
| 0 | `--xt-bg-page` | none | 页面背景 |
| 1 | `--xt-bg-panel` | `--xt-shadow-sm` | 卡片、表单区 |
| 2 | `--xt-bg-panel` | `--xt-shadow-md` | 聚焦态卡片 |
| 3 | `--xt-bg-ink` | `--xt-shadow-lg` | 身份栏 |

## 7. Do's and Don'ts

- DO: 数字用等宽体右对齐
- DO: 角色用色条区分，不用文字堆砌
- DO: 一屏一任务，不把所有字段平铺
- DO: 输入框 48px 最小高度，手指友好
- DON'T: 不用 Element Plus 默认蓝色主题色覆盖 xt-tokens
- DON'T: 不加解释性文案、helper text
- DON'T: 不用卡片嵌套卡片
- DON'T: 不用 el-form-item 的 label 布局，用自定义 mobile-field
- DON'T: 不引入新 CSS 框架

## 8. Responsive Behavior

- 唯一断点：560px（移动端最大宽度）
- 560px 以下：全宽，padding 16px
- 表单网格：单列，字段全宽
- 汇总网格：2 列（复用 mobile-overview-grid）
- 触摸目标最小 48px
- `touch-action: manipulation` 全局

## 9. Agent Prompt Guide

角色色条变量：
```
--m-role-operator: oklch(51% 0.17 255)
--m-role-energy: oklch(52% 0.13 158)
--m-role-maintenance: oklch(61% 0.12 75)
--m-role-hydraulic: oklch(54% 0.095 54)
--m-role-consumable: oklch(50% 0.15 252)
--m-role-qc: oklch(55% 0.15 28)
```

身份栏组件：`background: var(--xt-bg-ink); border-left: 3px solid var(--m-role-{role}); padding: 16px; border-radius: 12px;`

录入卡片：`background: var(--xt-bg-panel); border-top: 2px solid var(--m-role-{role}); border-radius: 12px; box-shadow: var(--xt-shadow-sm); padding: 16px;`

数值显示：`font-family: var(--xt-font-number); font-size: 24px; font-weight: 900; letter-spacing: -0.012em; font-variant-numeric: tabular-nums; text-align: right;`
