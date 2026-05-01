# 移动填报端清理与品质提升 — 设计规格

## 问题诊断

DynamicEntryForm.vue（2387 行）是移动端最大的文件，存在三类问题：

### 1. CSS 残留硬编码

| 文件 | 问题 | 行号 |
|------|------|------|
| DynamicEntryForm.vue | `var(--font-display, 'SF Pro Display', system-ui)` | 2254 |
| DynamicEntryForm.vue | `var(--font-number, 'SF Pro Display', 'DIN Alternate', system-ui)` | 2329 |
| DynamicEntryForm.vue | `var(--shadow-card)` 私有变量 | 2316 |
| DynamicEntryForm.vue | `border-radius: 16px` | 2315 |
| DynamicEntryForm.vue | `border-radius: 14px` | 2323 |
| DynamicEntryForm.vue | `border-radius: 12px` | 2302, 2334 |
| ShiftReportForm.vue | `var(--font-number)` 缺 xt 前缀 | 821 |
| ShiftReportForm.vue | `font-size: 24px` 硬编码 | 822 |

### 2. 死代码和占位内容

- **外部系统线索卡片**（DynamicEntryForm lines 158-165）：三个静态文字"前工序事实 / 后工序同步 / 不补后续码"，没有数据源，纯占屏幕空间
- **语音录入 stub**：`isVoiceFieldSupported()` 永远返回 `false`，模板中 7 处 `v-if="isVoiceFieldSupported(field)"` 永远不渲染，但代码仍在
- **外部系统线索 CSS**（lines 2337-2356）：`.entry-external-trace` 样式随卡片一起删除

### 3. 代码结构（第二轮处理）

2387 行巨型文件，可拆分为：
- 表达式解析器（93 行纯函数）→ `utils/expressionEvaluator.js`
- OWNER_MODE_CONFIG（170 行配置）→ `config/ownerModeConfig.js`
- OCR 状态管理 → `composables/useOcrState.js`
- 提交冷却 + 离线队列 → `composables/useSubmitQueue.js`
- 字段值解析 → `composables/useFieldResolution.js`

## 本轮改造清单（第一轮：CSS + 死代码）

### 1. DynamicEntryForm.vue — CSS 收敛

精确替换列表：

```
var(--font-display, 'SF Pro Display', system-ui)  → var(--xt-font-display)
var(--font-number, 'SF Pro Display', 'DIN Alternate', system-ui) → var(--xt-font-number)
var(--shadow-card)                                  → var(--xt-shadow-sm)
border-radius: 16px  (line 2315)                    → border-radius: var(--xt-radius-2xl)
border-radius: 14px  (line 2323)                    → border-radius: var(--xt-radius-xl)
border-radius: 12px  (lines 2302, 2334)             → border-radius: var(--xt-radius-lg)
```

### 2. DynamicEntryForm.vue — 删除外部系统线索卡片

删除模板 lines 158-165（`entry-external-trace-card`）和对应 CSS lines 2337-2356（`.entry-external-trace` 及 `.entry-external-trace span`）。

### 3. DynamicEntryForm.vue — 清理语音录入 stub

删除脚本中：
- `voiceListeningField` ref（line 752）
- `isVoiceFieldSupported()` 函数（lines 1354-1356）
- `toggleVoicePrefill()` 函数（lines 1358-1360）

删除模板中所有 7 处语音按钮块（`v-if="isVoiceFieldSupported(field)"` 开头的 `<el-button>` 块）。

### 4. ShiftReportForm.vue — CSS 收敛

```
var(--font-number)  → var(--xt-font-number)
font-size: 24px     → font-size: var(--xt-text-2xl)
```

## 不改的部分

- 所有 JS 逻辑、数据流、API 调用
- 模板结构（除删除的卡片和语音按钮外）
- 代码拆分（留给第二轮）
- CoilEntryWorkbench 和 UnifiedEntryForm（上一轮已收敛）

## 验收标准

1. DynamicEntryForm.vue 中不再出现 `--font-display`、`--font-number`（无 xt 前缀）、`--shadow-card` 私有变量
2. 不再出现 `border-radius: 12px/14px/16px` 硬编码
3. 外部系统线索卡片和对应 CSS 已删除
4. 语音录入 stub 代码已删除
5. ShiftReportForm.vue 中 `--font-number` 改为 `--xt-font-number`，`24px` 改为 token
6. `npx vite build` 零错误
