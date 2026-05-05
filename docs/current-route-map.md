# 当前路由地图（2026-05-05）

## 入口层

- `/login`：账号登录 + 钉钉免登 code 兼容（`frontend/src/views/Login.vue`）
- `/entry/*`：录入端主入口；`/mobile/*` 仅保留兼容重定向
- `/review/*`：审阅端兼容入口，正式审阅/管理页面统一落到 `/manage/*`
- `/admin/*`：管理端兼容入口，正式管理页面统一落到 `/manage/*`
- `/`（desktop 壳）+ `/master/*` 等：历史配置/兼容后台，继续 redirect 或降级保留
- `frontend/src/reference-command/pages/*`：历史参考原型，不作为当前生产路由页面；运行时以 `frontend/src/views/*` 与 `frontend/src/layout/*` 为准

## 正式中心导航（现状）

- 01 系统总览主视图：`/manage/overview`
- 03 独立填报端首页：`/entry`
- 05 工厂作业看板：`/manage/factory`
- 06 数据接入与字段映射中心：`/manage/ingestion`
- 07 审阅中心：`/manage/entry-center`
- 08 日报与交付中心：`/manage/reports`
- 09 质量与告警中心：`/manage/quality`
- 10 经营效益：`/manage/factory/cost`
- 11 AI 助手：`/manage/ai-assistant`
- 12 系统运维与可观测：`/manage/admin/settings`
- 13 权限与治理中心：`/manage/admin/governance`
- 14 主数据与模板中心：`/manage/master`

## 移动填报链路（现状）

- `/entry` -> `mobile-entry` -> `MobileEntry.vue`
- `/entry/report/:businessDate/:shiftId` -> `mobile-report-form` -> `ShiftReportForm.vue`
- `/entry/advanced/:businessDate/:shiftId` -> `mobile-report-form-advanced` -> `DynamicEntryForm.vue`
- `/entry/ocr/:businessDate/:shiftId` -> `mobile-ocr-capture` -> `OCRCapture.vue`
- `/entry/attendance` -> `mobile-attendance-confirm` -> `AttendanceConfirm.vue`
- `/entry/history` -> `mobile-report-history` -> `ShiftReportHistory.vue`
- `/entry/drafts` -> `entry-drafts` -> `EntryDrafts.vue`
- `/mobile/*` -> `/entry/*` 兼容重定向

## 审阅/管理链路（现状）

- `/review/overview` -> `/manage/overview` -> `review-overview-home` -> `FactoryOverview.vue`，正式中心：系统总览主视图。
- `/review/tasks` -> `/manage/entry-center` -> `review-task-center` -> `ReviewTaskCenter.vue`，正式中心：审阅中心。
- `/review/reports` -> `/manage/reports` -> `review-report-center` -> `ReportList.vue`，正式中心：日报与交付中心；当前通过 `frontend/src/api/reports.js` 调用 `/api/v1/reports`、详情、审核、发布、最终版和导出接口，不再走读面 mock。
- `/review/cost-accounting`、`/review/cost`、`/manage/cost` -> `/manage/factory/cost` -> `factory-command-cost` -> `CostBenefitScreen.vue`，正式中心：经营效益；当前通过 factory-command store 调用 `/api/v1/factory-command/cost-benefit`，展示经营估算、毛差估算和待补口径，不作为财务结算依据。`CostAccountingCenter.vue` 和 `frontend/src/services/costing/*` 保留为历史参考契约，不是 `/manage/factory/cost` 的运行时页面。
- `/review/quality` -> `/manage/quality` -> `review-quality-center` -> `QualityCenter.vue`，正式中心：质量与告警中心；当前通过 `frontend/src/api/quality.js` 调用质量检查、问题列表、解决和忽略接口，本页不承接生产事实写入。
- `/review/reconciliation` -> `/manage/reconciliation` -> `review-reconciliation-center` -> [ReconciliationCenter.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/reconciliation/ReconciliationCenter.vue)
- `/review/factory` -> `/manage/factory` -> `factory-dashboard` -> `FactoryDirector.vue`，正式中心：工厂作业看板。
- `/review/workshop` -> `/manage/workshop` -> `workshop-dashboard` -> `WorkshopDirector.vue`，作为车间看板兼容保留。
- `/review/brain` -> `/manage/ai-assistant` -> `factory-ai-assistant` -> `AiWorkstation.vue`，正式中心：AI 助手；当前通过 `useAiChatStore` 接会话、消息、主动汇报和关注列表，不使用前端读面 mock。后端是否 live 由 assistant 能力与模型配置决定，AI 仅提供辅助解释与建议，不自动执行质量、成本、排产或交付动作。
- `/review/roadmap` -> `/manage/overview`，路线图入口隔离。
- `/review/ingestion`、`/review/ops-reliability`、`/review/governance`、`/review/template-center` -> 对应 `/manage/*` 管理路由，管理能力不再挂在审阅端。
- `/admin` -> `/manage/admin/settings` -> `admin-ops-reliability` -> `LiveDashboard.vue`，管理端默认落点。
- `/admin/ingestion` -> `/manage/ingestion` -> `admin-ingestion-center` -> `IngestionCenter.vue`，正式中心：数据接入与字段映射中心；当前调用导入历史、排班、打卡、生产、能源、MES 导出与通用导入接口。本页不表示外部 MES/ERP 已正式联通。
- `/admin/governance` -> `/manage/admin/governance` -> `admin-governance-center` -> `GovernanceCenter.vue`，正式中心：权限与治理中心；当前基于 auth store 展示权限边界，管理员可通过用户接口读取角色分布。本页不绕过后端权限模型，不直接修改生产事实或真实授权策略。
- `/admin/ops` -> `/manage/admin/settings` -> `admin-ops-reliability` -> `LiveDashboard.vue`，正式中心：系统设置 / 运维状态入口；当前调用 dashboard、factory-command 与管理概览数据展示 ready/freshness/机列填报状态。本页不执行部署、回滚、重启或自动修复。
- `/admin/master` -> `/manage/master` -> `admin-master-workshop` -> `Workshop.vue`，正式中心：主数据与模板中心；车间清单、新增、编辑、删除已走 `frontend/src/api/master.js` 的 `/api/v1/master/workshops` 真实接口，页面不再依赖 `CommandModulePage.vue` 读面 mock。`/admin/master/templates` -> `/manage/admin/templates` -> `WorkshopTemplateConfig.vue`，模板中心仍独立承接字段模板配置。本页属于管理端主数据配置面，不绕过后端主数据与权限模型，不直接修改生产事实。

## Desktop 兼容链路（现状）

- `imports/*`, `energy/*`, `attendance/*`, `shift/*`, `reports/*`, `reconciliation/*`, `quality/*`, `master/*`
- `/master/team`、`/master/employee`、`/master/equipment`、`/master/shift-config` -> `/manage/master`
- `/master/alias` -> `/manage/alias`
- `/master/workshop-template`、`/master/workshop-templates`、`/master/yield-rate-map` -> `/manage/admin/templates`
- `/master/rules` -> `/manage/admin/rules`
- 核心壳层与权限： [Layout.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/Layout.vue) + [index.js](/D:/zzj Claude code/aluminum-bypass/frontend/src/router/index.js)

## 权限与落点（现状）

- 核心实现： [auth.js](/D:/zzj Claude code/aluminum-bypass/frontend/src/stores/auth.js) + [index.js](/D:/zzj Claude code/aluminum-bypass/frontend/src/router/index.js)
- `defaultLanding / reviewLanding / configLanding / prefersMobileSurface` 已实现
- `beforeEach` 已按 `zone + access` 守卫

## 核心链路与 legacy 划分

- 核心链路：
  - 登录（账号/钉钉）
  - 录入端（主操 + owner）
  - 系统总览、工厂/车间看板、审阅中心、日报交付、质量告警、差异核对、经营效益、AI 助手
  - 数据接入、主数据模板、用户权限、治理与运维
- legacy/兼容入口：
  - `/worker` -> 重定向到 `/entry`
  - `/dashboard/*` 的旧路径保留为 redirect
  - `/factory` `/workshop` 等历史路径保留 redirect
  - `/review/roadmap` 只作为兼容重定向，不再作为正式中心
