# 当前路由地图（2026-04-23）

## 入口层

- `/login`：账号登录 + 钉钉免登 code 兼容（`frontend/src/views/Login.vue`）
- `/review/*`：审阅端（`frontend/src/views/review/ReviewLayout.vue`）
- `/`（desktop 壳）+ `/master/*` 等：配置/兼容后台（`frontend/src/views/Layout.vue`）
- `/mobile/*`：移动填报（`frontend/src/views/mobile/*`）

## 移动填报链路（现状）

- `/mobile` -> `mobile-entry` -> [MobileEntry.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/mobile/MobileEntry.vue)
- `/mobile/report/:businessDate/:shiftId` -> `mobile-report-form` -> [ShiftReportForm.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/mobile/ShiftReportForm.vue)
- `/mobile/report-advanced/:businessDate/:shiftId` -> `mobile-report-form-advanced` -> [DynamicEntryForm.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/mobile/DynamicEntryForm.vue)
- `/mobile/ocr/:businessDate/:shiftId` -> `mobile-ocr-capture` -> [OCRCapture.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/mobile/OCRCapture.vue)
- `/mobile/attendance` -> `mobile-attendance-confirm` -> [AttendanceConfirm.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/mobile/AttendanceConfirm.vue)
- `/mobile/history` -> `mobile-report-history` -> [ShiftReportHistory.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/mobile/ShiftReportHistory.vue)

## 审阅中心链路（现状）

- `/review/factory` -> `factory-dashboard` -> [FactoryDirector.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/dashboard/FactoryDirector.vue)
- `/review/workshop` -> `workshop-dashboard` -> [WorkshopDirector.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/dashboard/WorkshopDirector.vue)
- `/review/ingestion` -> `review-ingestion-center` -> [FileImport.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/imports/FileImport.vue)
- `/review/reports` -> `review-report-center` -> [ReportList.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/reports/ReportList.vue)
- `/review/quality` -> `review-quality-center` -> [QualityCenter.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/quality/QualityCenter.vue)
- `/review/reconciliation` -> `review-reconciliation-center` -> [ReconciliationCenter.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/reconciliation/ReconciliationCenter.vue)
- `/review/ops-reliability` -> `review-ops-reliability` -> [LiveDashboard.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/reports/LiveDashboard.vue)
- `/review/cost-accounting` -> `review-cost-accounting` -> [CostAccountingCenter.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/review/CostAccountingCenter.vue)
- `/review/governance` -> `review-governance-center` -> [GovernanceCenter.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/review/GovernanceCenter.vue)
- `/review/roadmap` -> `review-roadmap-center` -> [RoadmapCenter.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/review/RoadmapCenter.vue)
- `/review/template-center` -> `review-template-center` -> [WorkshopTemplateConfig.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/master/WorkshopTemplateConfig.vue)

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
  - 移动填报（主操 + owner）
  - 厂级/车间看板
  - 审阅、质量、差异、日报、运维
  - 主数据与模板配置
- legacy/兼容入口：
  - `/worker` -> 重定向到 `/mobile`
  - `/dashboard/*` 的旧路径保留为 redirect
  - `/factory` `/workshop` 等历史路径保留 redirect

