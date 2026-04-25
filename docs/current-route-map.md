# 当前路由地图（2026-04-24）

## 入口层

- `/login`：账号登录 + 钉钉免登 code 兼容（`frontend/src/reference-command/pages/CommandLogin.vue`）
- `/entry/*`：录入端主入口；`/mobile/*` 仅保留兼容重定向
- `/review/*`：审阅端主入口，覆盖总览、工厂/车间看板、审阅、日报、质量、差异、成本、AI 总控
- `/admin/*`：管理端主入口，覆盖数据接入、主数据、模板、用户、治理、运维
- `/`（desktop 壳）+ `/master/*` 等：历史配置/兼容后台，继续 redirect 或降级保留

## 正式中心导航（现状）

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

## 移动填报链路（现状）

- `/entry` -> `mobile-entry` -> `CommandEntryHome.vue`
- `/entry/report/:businessDate/:shiftId` -> `mobile-report-form` -> `ShiftReportForm.vue`
- `/entry/advanced/:businessDate/:shiftId` -> `mobile-report-form-advanced` -> `DynamicEntryForm.vue`
- `/entry/ocr/:businessDate/:shiftId` -> `mobile-ocr-capture` -> `OCRCapture.vue`
- `/entry/attendance` -> `mobile-attendance-confirm` -> `AttendanceConfirm.vue`
- `/entry/history` -> `mobile-report-history` -> `ShiftReportHistory.vue`
- `/entry/drafts` -> `entry-drafts` -> `EntryDrafts.vue`
- `/mobile/*` -> `/entry/*` 兼容重定向

## 审阅/管理链路（现状）

- `/review/overview` -> `review-overview-home` -> `CommandOverview.vue`，正式中心：系统总览主视图。
- `/review/tasks` -> `review-task-center` -> `CommandReviewTasks.vue`，正式中心：审阅中心。
- `/review/reports` -> `review-report-center` -> `CommandModulePage.vue`，正式中心：日报与交付中心；当前按高清目标图 `08-reports-delivery.png` 对齐，使用 fallback 读面数据、`auto_confirmed` / 已自动确认口径，导出 PDF、导出 Excel、发送/交付、重新生成在无真实接口时禁用，本页不承接生产事实写入。
- `/review/cost-accounting` -> `review-cost-accounting` -> `CommandModulePage.vue`，正式中心：成本核算与效益中心。
- `/review/quality` -> `review-quality-center` -> `CommandModulePage.vue`，正式中心：质量与告警中心。
- `/review/reconciliation` -> `review-reconciliation-center` -> [ReconciliationCenter.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/reconciliation/ReconciliationCenter.vue)
- `/review/factory` -> `factory-dashboard` -> `CommandModulePage.vue`，正式中心：工厂作业看板。
- `/review/workshop` -> `workshop-dashboard` -> `WorkshopDirector.vue`，作为车间看板兼容保留。
- `/review/brain` -> `review-brain-center` -> `CommandModulePage.vue`，正式中心：AI 总控中心。
- `/review/roadmap` -> `/review/overview`，路线图入口隔离。
- `/review/ingestion`、`/review/ops-reliability`、`/review/governance`、`/review/template-center` -> `/admin/*`，管理能力不再挂在审阅端。
- `/admin` -> `admin-overview` -> `CommandModulePage.vue`，管理端默认落点。
- `/admin/ingestion` -> `admin-ingestion-center` -> `CommandModulePage.vue`，正式中心：数据接入与字段映射中心。
- `/admin/governance` -> `admin-governance-center` -> `CommandModulePage.vue`，正式中心：权限与治理中心。
- `/admin/ops` -> `admin-ops-reliability` -> `CommandModulePage.vue`，正式中心：系统运维与观测。
- `/admin/master`、`/admin/master/templates`：正式中心：主数据与模板中心。

## Desktop 兼容链路（现状）

- `imports/*`, `energy/*`, `attendance/*`, `shift/*`, `reports/*`, `reconciliation/*`, `quality/*`, `master/*`
- 核心壳层与权限： [Layout.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/Layout.vue) + [index.js](/D:/zzj Claude code/aluminum-bypass/frontend/src/router/index.js)

## 权限与落点（现状）

- 核心实现： [auth.js](/D:/zzj Claude code/aluminum-bypass/frontend/src/stores/auth.js) + [index.js](/D:/zzj Claude code/aluminum-bypass/frontend/src/router/index.js)
- `defaultLanding / reviewLanding / configLanding / prefersMobileSurface` 已实现
- `beforeEach` 已按 `zone + access` 守卫

## 核心链路与 legacy 划分

- 核心链路：
  - 登录（账号/钉钉）
  - 录入端（主操 + owner）
  - 系统总览、工厂/车间看板、审阅中心、日报交付、质量告警、差异核对、成本核算、AI 总控
  - 数据接入、主数据模板、用户权限、治理与运维
- legacy/兼容入口：
  - `/worker` -> 重定向到 `/entry`
  - `/dashboard/*` 的旧路径保留为 redirect
  - `/factory` `/workshop` 等历史路径保留 redirect
  - `/review/roadmap` 只作为兼容重定向，不再作为正式中心
