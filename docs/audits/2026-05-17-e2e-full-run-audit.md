# E2E 全量实跑审计

**日期：** 2026-05-17
**计划：** `docs/superpowers/plans/2026-05-17-completion-finalize.md` E2
**范围：** Playwright Chromium 全量项目 + Mobile 项目

## 结论

E2 已完成 A/C 处理并达到验收线。计划中记录为 35 个 spec；当前仓库实测为 33 个 spec、Chromium 项目 115 个测试用例。

| 阶段 | Project | Passed | Failed | Skipped | 说明 |
| --- | --- | ---: | ---: | ---: | --- |
| Baseline | chromium | 21 | 79 | 3 | 首轮全量实跑，失败进入 A/B/C 分类 |
| Final | chromium | 112 | 0 | 3 | A 类测试老化已修复；B 类列入 E4 并已进入针对性回归 |
| Final | mobile | 21 | 0 | 0 | Mobile project 仅运行移动端相关 spec |

最终绿灯比例：Chromium `(112 + 3) / 115 = 100%` 非失败；Mobile `21 / 21 = 100%`。

## 验收命令

```powershell
cd frontend
$env:PLAYWRIGHT_JSON_OUTPUT_FILE='test-results-e2-chromium-fresh.json'
npx playwright test --project=chromium --reporter=list,json --output=test-results-e2-chromium-fresh
Remove-Item Env:PLAYWRIGHT_JSON_OUTPUT_FILE
```

结果：`112 passed, 3 skipped, 0 failed`。

```powershell
cd frontend
$env:PLAYWRIGHT_JSON_OUTPUT_FILE='test-results-e2-mobile-fresh.json'
npx playwright test --project=mobile --reporter=list,json --output=test-results-e2-mobile-fresh
Remove-Item Env:PLAYWRIGHT_JSON_OUTPUT_FILE
```

结果：`21 passed, 0 failed`。

## A 类：测试老化，已在 E2 修复

| 文件 | 分类原因 | 处理 |
| --- | --- | --- |
| `frontend/e2e/helpers/mock-login.js` | storageState 与手动登录测试互相污染 | 新增 `clearAuthStorage(page)`，手动登录前清理认证缓存 |
| `frontend/e2e/compose-smoke.spec.js` | 手动登录受既有 storageState 影响 | 登录前调用 `clearAuthStorage(page)` |
| `frontend/e2e/login-delivery-smoke.spec.js` | 手动登录受既有 storageState 影响 | 登录前调用 `clearAuthStorage(page)` |
| `frontend/e2e/login-query-branches.spec.js` | query 分支测试受既有 storageState 影响 | 每组登录入口测试前清理认证缓存 |
| `frontend/e2e/mobile-entry-smoke.spec.js` | 管理员移动端入口与当前路由策略不一致 | 允许 `/entry` 或桌面管理落点，并校验空任务态 |
| `frontend/e2e/dashboard-factory.spec.js` | 路由、KPI 文案、日期选择器选择器已更新 | 改为 `/manage/factory`、`今日产量` 和当前日期选择器 |
| `frontend/e2e/dashboard-workshop.spec.js` | 页面根节点测试 id 已更新 | 改用 `workshop-dashboard` |
| `frontend/e2e/review-home-redesign.spec.js` | 看板卡片、KPI 文案、产品标题选择器已更新 | 改用当前 `delivery-ready-card`、`今日产量`、heading 定位 |
| `frontend/e2e/review-runtime.spec.js` | 产品标题 strict locator 与 AI 接口路径已更新 | 改用 heading；补齐 AI assistant mocks |
| `frontend/e2e/manage-shell.spec.js` | 搜索快捷键和 Element Plus overlay DOM 行为变化 | 点击搜索按钮打开；关闭断言改为 hidden |
| `frontend/e2e/helpers/review-mocks.js` | 多个 dashboard / AI / MES / master API mock 路径缺失 | 补齐当前前端访问的 mock 路径 |
| `frontend/playwright.config.js` | Mobile 项目跑到桌面 spec，Pixel 视口被移动端入口策略重定向 | Mobile project 限定移动端相关 spec |

## B 类：真实产品缺陷，列入 E4

| 缺陷 | 现象 | 观测页面 | E4 建议 |
| --- | --- | --- | --- |
| `XtErrorPanel` 对后端 404 payload 不稳健 | `Cannot read properties of undefined (reading 'toLocaleString')` | `/manage/contracts`、`/manage/inventory` | 让错误面板兼容缺少时间戳或非标准错误结构的响应 |
| Element Plus table 数据形态不稳健 | `e is not iterable`、`reduce is not a function` | `/manage/quality`、`/manage/reports` | 在页面适配层把分页 envelope 归一成数组，再交给 table |

这些问题来自前端运行时 telemetry，不再作为 E2 测试老化处理；E4 会按真实缺陷修复。

## C 类：环境问题

未新增 C 类 skip。当前 3 个 skipped 均为既有 owner-only / 凭据类用例，不属于本轮新增环境问题。

## 产物

- 测试修复：见 E2 相关 spec 与 helper 变更。
- 审计文档：`docs/audits/2026-05-17-e2e-full-run-audit.md`。
- B 类输入：本文件 “B 类：真实产品缺陷，列入 E4”。
