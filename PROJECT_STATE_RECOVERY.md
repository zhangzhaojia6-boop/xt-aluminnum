# Project State Recovery

生成时间：2026-04-24

## 当前系统实际状态报告

### 1. 当前项目是什么

本项目是 `Aluminum Bypass`，一个面向铝业生产现场的生产填报、自动校验汇总、审阅处置、日报交付和管理配置系统。

从 `README.md`、后端 `app/main.py`、前端路由和现有文档看，当前业务主线是：

- 班长/岗位用户通过录入端提交班次生产数据、补录异常、上传图片或 OCR 辅助录入。
- 后端通过 FastAPI 提供认证、主数据、移动填报、生产、考勤、质量、差异核对、日报、MES、实时事件、模板、钉钉等接口。
- 后端定时任务执行自动汇总、日报生成、催报扫描和可选 MES 同步。
- 审阅端面向管理/审阅角色查看总览、工厂/车间看板、审阅任务、日报交付、质量告警、差异核对、成本核算与 AI 总控。
- 管理端面向管理员/经理维护数据接入、字段映射、主数据、模板、用户、权限治理和运维探针。

当前前端技术栈为 Vue 3 + Vue Router + Pinia + Element Plus + Vite；后端技术栈为 FastAPI + SQLAlchemy + Alembic + pytest。

### 2. 已存在页面/模块

前端存在三类入口和大量兼容路由：

- 公共入口：`/login`，当前指向 `frontend/src/reference-command/pages/CommandLogin.vue`。
- 录入端：`/entry` 及其子路由，包含今日任务、快速填报、高项填报、OCR、异常补录、历史、草稿；旧 `/mobile/*` 重定向到 `/entry/*`。
- 审阅端：`/review/overview`、`/review/factory`、`/review/workshop`、`/review/tasks`、`/review/reports`、`/review/quality`、`/review/reconciliation`、`/review/cost-accounting`、`/review/brain`。
- 管理端：`/admin`、`/admin/ingestion`、`/admin/ops`、`/admin/governance`、`/admin/master`、`/admin/master/templates`、`/admin/users`。
- 兼容入口：`/mobile/*`、`/dashboard/*`、`/master/*`、`/factory`、`/workshop` 等仍保留重定向或 legacy route。

前端模块形态同时存在：

- 旧业务页面：`frontend/src/views/*`，覆盖 mobile、dashboard、imports、quality、reports、reconciliation、master、review 等。
- 新参考指挥中心页面：`frontend/src/reference-command/*`，定义 01-15 编号中心模块、统一组件和样式。
- 新壳层与配置：`frontend/src/layout/AppShell.vue`、`EntryShell.vue`、`AdminShell.vue`，以及未跟踪的 `ReviewShell.vue`。
- 新设计与通用组件：未跟踪的 `frontend/src/design/*`、`frontend/src/components/app/*`。
- 成本策略前端服务：`frontend/src/services/costing/*` 已存在。

后端模块覆盖：

- 路由：auth、users、master、imports、assistant、command、dashboard、attendance、production、mobile、ocr、reports、mes、reconciliation、energy、quality、realtime、templates、dingtalk、work_orders。
- 服务：mobile report/reminder、assistant、command、MES sync、report、quality、reconciliation、work orders、cost/management estimate 相关服务等。
- Agent：aggregator、reporter、reminder、validator、reconciler。
- 聚合接口：`/api/v1/command/surface/{surface}` 和 `/api/v1/admin/*-overview` 已存在，但当前 `command_service.py` 大量返回静态/样例聚合数据。

### 3. 已存在但混乱/重复/偏离中心的部分

- 文档和代码状态不完全一致：`docs/launch-readiness-checklist.md` 标记多项前端重构已完成，但工作树仍有大量未提交、未跟踪和部分 staged 改动。
- 请求中提到的 `docs/recovery` 目录不存在；`codex-recovery-diff.patch`、`codex-recovery-diff-stat.txt`、`codex-untracked-files.txt` 未在根目录、`docs`、`frontend`、`backend`、`tmp`、`scripts` 可访问范围内找到。
- 前端存在两套页面体系：旧 `views/*` 业务页与新 `reference-command/*` 指挥中心页并存；部分路由已切到新页，部分仍指向旧页，部分只是 redirect。
- `CommandPage.vue` 内含大量硬编码静态数据、兼容 test id、mock notice 和模块条件分支，已经承担过多页面职责。
- `moduleCatalog.js` 保留 01-15 模块编号；第一轮收敛已移除后端 `command_service.py` 返回的 `module_id='16'` 路线图模块。
- `moduleAdapters.js` 和 `command_service.py` 都存在静态 fallback 数据，真实数据来源和 mock 数据边界不清。
- 管理端和审阅端边界正在重排：例如 `/review/ingestion`、`/review/ops-reliability`、`/review/governance` 被转到 `/admin/*`，这是合理方向，但会影响旧 E2E 和用户习惯。
- 前端有新 `components/app/*`、`design/*`、`mocks/*` 未跟踪，说明设计系统和 mock 体系尚未稳定纳入版本控制。
- `git diff --stat` 显示 20 个已跟踪文件发生 732 行新增、709 行删除；同时还有 16 个未跟踪文件。

### 4. 未提交改动清单

当前 `git status --porcelain=v1`：

- `MM backend/tests/test_reference_command_center_spec.py`
- `M docs/ui-replica-spec.md`
- `M frontend/e2e/admin-surface.spec.js`
- `M frontend/e2e/login-delivery-smoke.spec.js`
- `M frontend/e2e/review-runtime.spec.js`
- `M frontend/src/config/navigation.js`
- `M frontend/src/layout/AdminShell.vue`
- `M frontend/src/layout/AppShell.vue`
- `M frontend/src/layout/EntryShell.vue`
- `M frontend/src/main.js`
- `A frontend/src/reference-command/assets/review-center-panel.png`
- `MM frontend/src/reference-command/components/CommandPage.vue`
- `M frontend/src/reference-command/data/moduleAdapters.js`
- `M frontend/src/reference-command/data/moduleCatalog.js`
- `M frontend/src/reference-command/pages/CommandEntryFlow.vue`
- `M frontend/src/reference-command/pages/CommandEntryHome.vue`
- `M frontend/src/reference-command/pages/CommandLogin.vue`
- `M frontend/src/reference-command/pages/CommandOverview.vue`
- `M frontend/src/reference-command/styles/command-layout.css`
- `M frontend/src/router/index.js`
- `MM frontend/tmp_visual_audit.cjs`

当前未跟踪文件：

- `backend/tests/test_frontend_refactor_blueprint.py`
- `frontend/src/components/app/ActionTile.vue`
- `frontend/src/components/app/CenterPageShell.vue`
- `frontend/src/components/app/DataTableShell.vue`
- `frontend/src/components/app/FixedActionBar.vue`
- `frontend/src/components/app/KpiCard.vue`
- `frontend/src/components/app/KpiStrip.vue`
- `frontend/src/components/app/MockDataNotice.vue`
- `frontend/src/components/app/SectionCard.vue`
- `frontend/src/components/app/SourceBadge.vue`
- `frontend/src/components/app/StatusBadge.vue`
- `frontend/src/design/centerTheme.js`
- `frontend/src/design/status.js`
- `frontend/src/design/tokens.css`
- `frontend/src/layout/ReviewShell.vue`
- `frontend/src/mocks/centerMockData.js`
- `frontend/src/reference-command/pages/CommandReviewTasks.vue`

当前 staged 改动：

- `backend/tests/test_reference_command_center_spec.py`
- `frontend/src/reference-command/assets/review-center-panel.png`
- `frontend/src/reference-command/components/CommandPage.vue`
- `frontend/tmp_visual_audit.cjs`

### 5. 不应继续扩张的功能

下一轮不应继续新增中心页、AI 专题、成本策略、路线图模块或视觉资产。当前更需要收口：

- 不继续新增 `reference-command` 模块编号。
- 不继续扩张 `CommandPage.vue` 的条件分支。
- 不继续堆 mock 数据、fallback 文案和测试兼容标记。
- 不继续改动 CI/CD、部署脚本或生产配置。
- 不继续把审阅端、管理端、录入端功能交叉放置。
- 不继续新增成本后端表或月结流程，除非先完成现有前端/后端 contract 对齐。

## 下一步最小重构计划

### 6. 下一轮应该优先修复的 3 个点

1. 先收口路由与三端边界。
   - 核对 `frontend/src/router/index.js`、`frontend/src/config/navigation.js`、`docs/current-route-map.md`、`docs/ui-replica-spec.md` 是否一致。
   - 明确 `/entry`、`/review/*`、`/admin/*` 为主入口，legacy 只做 redirect。
   - 验证 fill-only、review、admin 三类角色的默认落点和越权回跳。

2. 再收口指挥中心模块数据边界。
   - 对齐 `moduleCatalog.js` 与 `backend/app/services/command_service.py` 的模块编号，处理后端 `16` 模块和前端 01-15 编号不一致问题。
   - 标明哪些页面用真实接口，哪些只允许临时 fallback。
   - 将 `CommandPage.vue` 中明显重复的静态 mock 和页面分支拆回更小的现有组件或删除未用分支，但仅在测试保护下进行。

3. 最后整理未提交改动为可验证批次。
   - 先决定未跟踪的 `components/app/*`、`design/*`、`mocks/*`、`ReviewShell.vue`、`CommandReviewTasks.vue` 是否纳入本次前端重构。
   - 已 staged 与 unstaged 混合的文件需要恢复为单一清晰 diff，再运行相关测试。
   - 将文档中的“已完成”结论改为基于实际测试结果，而不是基于意图。

### 7. 验收标准

下一轮恢复/重构完成后，至少满足：

- `git status` 中只剩本轮有意保留的文件，且 staged/unstaged 状态清晰。
- `docs/current-route-map.md`、`docs/ui-replica-spec.md`、`frontend/src/router/index.js`、`frontend/src/config/navigation.js` 对三端入口说法一致。
- `moduleCatalog.js` 和 `command_service.py` 的模块编号一致，或文档明确说明不一致的兼容原因。
- 未跟踪文件要么被纳入版本控制，要么被明确删除/移动；不能继续处于未知状态。
- 前端构建通过：`npm --prefix frontend run build`。
- 路由/权限相关 E2E 通过当前约定子集，至少覆盖 `/login`、`/entry`、`/review/overview`、`/review/tasks`、`/admin`、`/admin/ops`。
- 后端相关测试通过，至少覆盖 `backend/tests/test_reference_command_center_spec.py` 和 `backend/tests/test_command_routes.py`；若只做前端文件调整，应说明未跑全量后端测试的原因。

## 本次恢复操作说明

本次只读取仓库文件、git 状态、diff 统计、docs 和前后端目录结构，并新增本恢复报告。未修改业务代码，未运行测试。

## 第一轮收敛记录（2026-04-24）

正式中心按 15 中心 Web 中台蓝图收敛，其中 02/04/15 不进入业务侧边导航：

- 01 系统总览主视图：`/review/overview`
- 03 独立填报端首页：`/entry`
- 05 工厂作业看板：`/review/factory`
- 06 数据接入与字段映射中心：`/admin/ingestion`
- 07 审阅中心：`/review/tasks`
- 08 日报与交付中心：`/review/reports`
- 09 质量与告警中心：`/review/quality`
- 10 成本核算与效益中心：`/review/cost-accounting`
- 11 AI 总控中心：`/review/brain`
- 12 系统运维与观测：`/admin/ops`
- 13 权限与治理中心：`/admin/governance`
- 14 主数据与模板中心：`/admin/master`

已隔离的入口：

- `/review/roadmap` -> `/review/overview`
- `/review/ingestion`、`/review/ops-reliability`、`/review/governance`、`/review/template-center` -> 对应 `/admin/*`

后端聚合接口不再返回 `module_id='16'`；`/review/brain` 保留为正式 AI 总控中心，AI 建议必须按辅助建议和 mock/live 来源展示。
