# E5 系统级冒烟审计

**日期**：2026-05-18
**计划**：`docs/superpowers/plans/2026-05-17-completion-finalize.md` E5
**结论**：通过。生产形态后端、前端 preview、核心用户路径、健康检查、遥测入口和关键页面访问均为绿；无 P0/P1 残留。

## 启动形态

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 后端 | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` | `127.0.0.1:8000` 正在监听 |
| 前端 | `npm run build && npm run preview -- --host 127.0.0.1 --port 4173` | `127.0.0.1:4173` 正在监听，`dist/sw.js` 已生成 |

## Playwright 冒烟

```powershell
cd frontend
$env:PLAYWRIGHT_REUSE_SERVERS='1'
$env:PLAYWRIGHT_JSON_OUTPUT_FILE='test-results-e5-smoke-fresh.json'
npx playwright test e2e/compose-smoke.spec.js e2e/zd1-machine-smoke.spec.js e2e/mobile-entry-smoke.spec.js --project=chromium --reporter=list,json --output=test-results-e5-smoke-fresh
```

结果：`13 passed`，`0 failed`，`0 skipped`，耗时约 `27.5s`。

| Spec | 结果 |
| --- | --- |
| `e2e/compose-smoke.spec.js` | 1/1 passed |
| `e2e/zd1-machine-smoke.spec.js` | 1/1 passed |
| `e2e/mobile-entry-smoke.spec.js` | 11/11 passed |

## 手动 HTTP 验证

| 检查 | 结果 |
| --- | --- |
| `GET http://127.0.0.1:8000/healthz` | HTTP 200，`status=ok` |
| `GET http://127.0.0.1:8000/readyz` | HTTP 200，`status=ready` |
| `POST http://127.0.0.1:8000/api/v1/auth/login` | HTTP 200，`access_token` 与 `refresh_token` 均存在，用户角色 `admin` |
| `POST http://127.0.0.1:8000/api/v1/telemetry/errors` | HTTP 200，payload 含 `url`，`received=true` |
| `POST http://127.0.0.1:8000/api/v1/telemetry/perf` | HTTP 200，payload 含 `metric/value`，`received=true` |
| `GET http://127.0.0.1:4173/` | HTTP 200，`text/html` |
| `GET http://127.0.0.1:4173/login` | HTTP 200，`text/html` |
| `GET http://127.0.0.1:4173/dashboard/executive` | HTTP 200，`text/html` |

## 浏览器验证

| 页面 | 最终 URL | HTTP | Console errors | Page errors | 截图 |
| --- | --- | --- | --- | --- | --- |
| `/` | `/login?redirect=/manage/overview` | 200 | 0 | 0 | `docs/audits/evidence/2026-05-17-system-smoke/root.png` |
| `/login` | `/login` | 200 | 0 | 0 | `docs/audits/evidence/2026-05-17-system-smoke/login.png` |
| `/dashboard/executive` | `/manage/executive`（真实 UI 登录后访问） | 200 | 0 | 0 | `docs/audits/evidence/2026-05-17-system-smoke/dashboard-executive.png` |

## 发现与处置

| 项目 | 分类 | 处置 |
| --- | --- | --- |
| `mobile-entry-smoke.spec.js` 的 admin 入口只接受空任务态 | 测试老化 | 生产形态数据库中 admin 可拿到当前班次，测试已改为接受“空任务态”或“当前班次态”两种合法入口，同时保留 admin 不出现审阅端按钮/小队文案的断言 |
| `/dashboard/executive` 旧路径落到总览页 | 兼容缺口 | 已补 `/dashboard/executive -> /manage/executive` 路由重定向，并用 `tests/factoryCommandNavigation.test.js` 锁定 |
| 生产 build 不读取 Playwright localStorage 登录态 | 预期行为 | 浏览器手动验证改为真实 UI 登录后进入 `/dashboard/executive`，不把测试专用 storageState 当生产 session |

## 验收

- [x] audit 文档存在
- [x] 所有冒烟项绿
- [x] 无 P0/P1 残留
