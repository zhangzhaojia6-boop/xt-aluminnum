# 测试体系与 QA 验收门禁审计

日期：2026-06-11

范围：后端 pytest、前端 node test、Playwright e2e、CI、核心业务链路验收门禁。

## 1. 小白版结论

这个项目不是“没测试”，而是测试很多，但需要按业务上线门禁重新组织。以后不要只说“测试通过”，要说清楚：

1. 哪个业务页面被测了。
2. 哪个接口字段被测了。
3. 哪个数据口径被测了。
4. 哪个角色权限被测了。
5. 哪个浏览器页面被实际打开验证了。

这样才能避免“代码测试绿了，但用户页面还是显示 0、空白、timeout、network error”的问题。

## 2. 当前测试体系证据

### 2.1 后端测试

CodeGraph 只读统计显示：`backend/tests` 下有 214 个测试文件。

代表性测试：

| 领域 | 测试文件 |
| --- | --- |
| 实时聚合 | `test_realtime_service.py`、`test_realtime_routes.py`、`test_realtime_service_contract.py`、`test_aggregation_api_contract.py` |
| 能耗 | `test_energy_summary.py`、`test_energy_import.py` |
| MES 同步 | `test_mes_sync_service.py`、`test_mes_sync_lag.py`、`test_mes_sqlserver_*` |
| MES 补录 | `test_mes_supplement_readiness_service.py`、`test_mobile_mes_pending_supplements.py` |
| MES 机列匹配 | `test_mes_machine_match_service.py` |
| 工厂指挥/卷级 | `test_factory_command_service.py`、`test_factory_command_routes.py` |
| 手机填报 | `test_mobile_routes.py`、`test_mobile_shift_report_machine_binding.py`、`test_mobile_submit_with_locked_fields.py` |
| 日报 | `test_daily_overview_mes_packaging.py`、`test_report_generation.py`、`test_report_publish_flow.py` |
| 用户权限 | `test_users_routes.py`、`test_reviewer_scope_permissions.py`、`test_work_order_permissions.py` |
| 安全 | `test_ops_security_contracts.py`、`test_secret_redaction.py`、`test_rate_limit.py` |

后端默认测试配置：

| 文件 | 说明 |
| --- | --- |
| `backend/pytest.ini` | 默认跑 `tests`，排除 `frontend_contract` 标记 |
| `backend/requirements.txt` | 包含 `pytest`、`pymssql`、`fastapi`、`sqlalchemy` 等依赖 |

### 2.2 前端单元测试

CodeGraph 只读统计显示：`frontend/tests` 下有 81 个测试文件。

代表性测试：

| 领域 | 测试文件 |
| --- | --- |
| 实时大屏 | `manageLivePhase2.test.js` |
| 日报 | `manageTodayPage.test.js`、`manageTodayCockpit.test.js` |
| 生产页 | `manageProductionPage.test.js` |
| 能耗页 | `energyCenterDesign.test.js` |
| 填报明细 | `manageFillDetailsAudit.test.js` |
| 异常页 | `manageAlertsPage.test.js`、`manageAlertsTimeline.test.js` |
| 设置页 | `systemSettingsPage.test.js` |
| 导航路由 | `manageNavigationSkeleton.test.js`、`manageRouteRedirects.test.js` |
| 合同/库存 | `contractsCenterDesign.test.js`、`inventoryCenterDesign.test.js` |
| 手机按卷填报 | `coilEntryWorkbench.scan.test.js`、`coilEntryValidation.test.js` |

前端命令：

| 命令 | 作用 |
| --- | --- |
| `npm run test` | 跑 `frontend/tests/*.test.js` |
| `npm run build` | 前端构建 |
| `npm run audit` | 依赖安全审计 |

### 2.3 Playwright e2e

CodeGraph 只读统计显示：`frontend/e2e` 下有 52 个 e2e 文件。

代表性测试：

| 领域 | 测试文件 |
| --- | --- |
| 管理端壳 | `manage-shell.spec.js`、`manage-shell-hud.spec.js` |
| 日报/生产 | `manage-today-production.spec.js` |
| 能耗 | `manage-energy.spec.js` |
| 异常 | `manage-alerts-timeline.spec.js` |
| 合同/库存 | `contracts-center.spec.js`、`inventory-center.spec.js` |
| 手机填报 | `mobile-entry-smoke.spec.js`、`mobile-shift-report.spec.js`、`mobile-scan-entry.spec.js` |
| 登录 | `login-delivery-smoke.spec.js`、`login-query-branches.spec.js` |
| 可访问性 | `a11y/contrast.spec.js` |

Playwright 配置：

| 文件 | 重点 |
| --- | --- |
| `frontend/playwright.config.js` | 默认启动后端和前端 |
| `PLAYWRIGHT_BASE_URL` | 可指定前端地址 |
| `PLAYWRIGHT_BACKEND_URL` | 可指定后端地址 |
| `PLAYWRIGHT_SKIP_WEB_SERVER=1` | 可跳过本地服务，连已有环境 |

### 2.4 CI 现状

`.github/workflows/ci.yml` 包含：

1. 后端测试：`python -m pytest`
2. 前端依赖安装：`npm ci`
3. 前端安全审计：`npm run audit`
4. 前端构建：`npm run build`
5. Docker compose 烟测
6. `/healthz`、`/readyz` 检查
7. 登录接口检查
8. Playwright smoke：`npm run e2e:smoke`

说明：CI 有基础，但还没有把“卷级线索页、状态语言、页面合并”作为独立门禁。

## 3. 当前主要测试缺口

### P1：缺 `/manage/coils` 正式页面测试

现状：后端有 `/factory-command/coils` 和 `/factory-command/coils/{coil_key}/flow`，前端 API 有 `fetchFactoryCommandCoils`，但没有正式 `/manage/coils` 页面，自然也没有页面测试。

需要新增：

1. 后端字段契约测试：卷列表必须返回随行卡、批号、当前车间、当前工艺、机列匹配来源、补录状态、异常状态。
2. 前端单测：页面能搜索、列表能渲染、详情抽屉能展示时间线。
3. e2e：管理员能从导航进入 `/manage/coils` 并搜索一卷。

### P1：缺跨页面状态语言测试

现状：各页面已有测试，但没有统一验证 `真实 0 / 未同步 / 加载中 / 异常隔离 / 无产量分母`。

需要新增：

1. 实时页不能把接口缺字段显示成真实 0。
2. 能耗页有能耗但无产量分母时显示“无产量分母”。
3. 日报页异常废料/成品率进入“待核”或“异常隔离”。
4. 生产页无数据时显示“待同步”或“暂无可信数据”，不能混用。

### P1：缺 PC/WAN 终端绑定验收链路

现状：后端有 `test_mes_machine_match_service.py` 保护 `PC` 不乱匹配，但还没有终端绑定表和绑定后完整链路测试。

需要新增：

1. `PC + MES车间 + MES工艺` 命中绑定机列。
2. 同名 PC 在不同车间不串线。
3. 无绑定时进入待归属。
4. 设置页展示待绑定终端清单。
5. 手机端 MES 待补录能看到待确认/待绑定状态。

### P2：合同/库存页面降级前缺回归门禁

现状：合同和库存页面已有测试，但如果后续合并或隐藏，需要证明旧入口不会坏。

需要新增：

1. 旧路由跳转或二级入口可达。
2. 导出功能如果保留，接口仍可用。
3. 主导航不再暴露时，用户仍能从正确上下文找到。

### P2：实际浏览器验收不能只等 networkidle

原因：实时页有 SSE 长连接，`networkidle` 不适合判断页面完成。

建议验收方式：

1. 等 `data-testid` 或页面标题出现。
2. 等核心 KPI 卡片有稳定文本。
3. 等关键接口返回或页面状态从“加载中”退出。
4. 对 SSE 页面允许请求持续存在。

## 4. 推荐 QA 门禁

### 4.1 每次后端口径改动

必须跑：

```powershell
cd backend
python -m pytest tests/test_aggregation_api_contract.py tests/test_realtime_service_contract.py tests/test_energy_summary.py tests/test_factory_command_routes.py tests/test_mes_supplement_readiness_service.py
```

适用场景：

1. 改日报、实时、生产、能耗、MES、卷级接口。
2. 改业务时间口径。
3. 改包装产量、成品率、废料、吨耗。

### 4.2 每次管理端页面改动

必须跑：

```powershell
cd frontend
npm run test -- manageLivePhase2.test.js manageTodayPage.test.js manageProductionPage.test.js energyCenterDesign.test.js manageFillDetailsAudit.test.js manageNavigationSkeleton.test.js
```

适用场景：

1. 改 `/manage/live`
2. 改 `/manage/today`
3. 改 `/manage/production`
4. 改 `/manage/energy`
5. 改导航或主视觉

### 4.3 每次手机填报改动

必须跑：

```powershell
cd backend
python -m pytest tests/test_mobile_mes_pending_supplements.py tests/test_mobile_shift_report_machine_binding.py tests/test_mobile_submit_with_locked_fields.py
cd ..\frontend
npm run test -- coilEntryWorkbench.scan.test.js coilEntryValidation.test.js
```

适用场景：

1. 改扫码。
2. 改按卷补录。
3. 改 MES 自动带出字段。
4. 改字段可编辑/锁定逻辑。

### 4.4 每次要上线前

必须跑：

```powershell
cd backend
python -m pytest
cd ..\frontend
npm run test
npm run build
npm run e2e:smoke
```

如果改了关键 UI 或导航，再补：

```powershell
cd frontend
npm run e2e -- manage-today-production.spec.js manage-energy.spec.js manage-shell.spec.js
```

## 5. 五视角评分

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 能把“测试很多”转成“业务上线有门禁” |
| 工程 | 9.8 | 现有测试资源充足，缺的是按业务链路组织 |
| 设计 | 9.6 | 浏览器验收方式更贴近真实用户，不再只看接口绿 |
| 安全 | 9.7 | CI 已有登录、健康、审计，后续权限测试要继续补 |
| 真实用户 | 9.7 | 能减少页面空、显示 0、timeout、network error 这类体验问题 |

综合：9.7/10。

## 6. 下一步

最推荐下一轮进入 TDD 准备：

1. 先写 `/factory-command/coils` 字段契约测试。
2. 再写 `/manage/coils` 前端页面测试。
3. 再实现 `/manage/coils` 最小可用页。
4. 同时新增跨页面状态语言测试。

这样后续做视觉重构、页面合并、实时大屏升级时，业务数字不容易被改乱。
