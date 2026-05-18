# 对比度与可访问性审计

**日期：** 2026-05-17
**计划：** `docs/superpowers/plans/2026-05-17-completion-finalize.md` E3
**范围：** Playwright Chromium + `@axe-core/playwright`，仅断言 `color-contrast`

## 结论

E3 已完成。审计覆盖登录页、经营驾驶舱、工厂/车间看板、6 个 Center 页、移动端入口和移动端填报页，最终 12 个页面均无 WCAG AA `color-contrast` 违规。

## 覆盖页面

| 计划页面 | 当前路由 | 审计范围 | 结果 |
| --- | --- | --- | --- |
| `/login` | `/login` | `.login-stage` | 通过 |
| `/dashboard/executive` | `/manage/executive` | `main` | 通过 |
| `/dashboard/factory` | `/manage/factory` | `main` | 通过 |
| `/dashboard/workshop` | `/manage/workshop` | `main` | 通过 |
| Center 1 | `/manage/ingestion` | `main` | 通过 |
| Center 2 | `/manage/entry-center?desktop=1` | `[data-testid="review-task-center"]` | 通过 |
| Center 3 | `/manage/reports` | `main` | 通过 |
| Center 4 | `/manage/quality` | `main` | 通过 |
| Center 5 | `/manage/reconciliation` | `main` | 通过 |
| Center 6 | `/manage/master` | `main` | 通过 |
| `/mobile/entry` | `/entry` | `.mobile-shell` | 通过 |
| `/mobile/shift-report` | `/mobile/report/2026-04-23/1` -> `/entry/report/2026-04-23/1` | `.mobile-shell` | 通过 |

说明：当前仓库没有独立 `/mobile/shift-report` 路由，兼容路由是 `/mobile/report/:businessDate/:shiftId`，会重定向到 `/entry/report/:businessDate/:shiftId`。

## 基线问题

| 页面 | 违规等级 | 问题 | 处理 |
| --- | --- | --- | --- |
| 工厂看板 | serious | `--xt-text-muted` 派生文本在浅底上对比度约 3.42；warning 文本约 3.65；success 标签边界值 4.49 | 调整 `frontend/src/design/xt-tokens.css` 的 muted/warning/success 基础 token |
| 车间看板 | serious | 同类 muted/warning/success 派生色对比不足 | 同上 |
| 经营驾驶舱 | serious | `.exec-btn` 白字蓝底 3.68；`.rank-rev` 深底灰字 3.22 | 该页颜色为 scoped 硬编码，最小改动修正 `ExecutiveDashboard.vue` 两处颜色 |
| 评审中心 | 环境/测试装配 | 页面依赖活跃日期、待归属、核对项接口，mock 不完整导致 axe include 找不到目标 | 在 `contrast.spec.js` 补齐页面依赖 mock，并将范围收窄到页面根节点 |

未保留 P1 中等违规。axe 最终报告中 `color-contrast` 违规为 0。

## 修复范围

- 新增 `frontend/e2e/a11y/contrast.spec.js`，覆盖 E3 目标页面。
- 新增 dev 依赖 `@axe-core/playwright`。
- 调整 `frontend/src/design/xt-tokens.css`：
  - `--xt-success: oklch(49% 0.13 158)`
  - `--xt-warning: oklch(49% 0.12 75)`
  - `--xt-text-muted: oklch(48% 0.028 250)`
- 例外修复 `frontend/src/views/executive/ExecutiveDashboard.vue`：
  - `.exec-btn` 背景由 `oklch(62% 0.18 255)` 调暗到 `oklch(52% 0.18 255)`
  - `.rank-rev` 文字由 `oklch(50% 0.02 252)` 提亮到 `oklch(70% 0.02 252)`

该例外是因为经营驾驶舱没有使用基础 token，E3 的 token-only 约束无法触达 axe 点名的硬编码颜色。

## 验收命令

```powershell
cd frontend
$env:PLAYWRIGHT_JSON_OUTPUT_FILE='test-results-e3-contrast-fresh.json'
npx playwright test e2e/a11y/contrast.spec.js --project=chromium --reporter=list,json --output=test-results-e3-contrast-fresh
Remove-Item Env:PLAYWRIGHT_JSON_OUTPUT_FILE
```

结果：`12 passed, 0 failed`。测试运行同时完成 `npm run build`，生成 `dist/sw.js`。
