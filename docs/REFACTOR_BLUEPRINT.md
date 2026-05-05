# 前端重构蓝图

本蓝图约束当前前端重构只做三端收敛、视觉对齐和路由稳定，不扩新业务功能。

## 信息架构

### 公共入口

- `/login`：登录与角色入口。

### 录入端 Entry

- `/entry`
- `/entry/report/:businessDate/:shiftId`
- `/entry/advanced/:businessDate/:shiftId`
- `/entry/attendance`
- `/entry/history`
- `/entry/drafts`

### 审阅端 Review

- `/manage/overview`
- `/manage/factory`
- `/manage/workshop`
- `/manage/entry-center`
- `/manage/reports`
- `/manage/quality`
- `/manage/reconciliation`
- `/manage/factory/cost`
- `/manage/ai-assistant`

### 管理端 Admin

- `/manage/ingestion`
- `/manage/admin/settings`
- `/manage/admin/governance`
- `/manage/master`
- `/manage/admin/templates`
- `/manage/admin/users`
- `/manage/admin/rules`

## 中心页列表

- 01 系统总览主视图：`/manage/overview`
- 03 独立填报端首页：`/entry`
- 05 工厂作业看板：`/manage/factory`
- 06 数据接入与字段映射中心：`/manage/ingestion`
- 07 异常与补录：`/manage/entry-center`
- 08 日报与交付中心：`/manage/reports`
- 09 质量与告警中心：`/manage/quality`
- 10 成本核算与效益中心：`/manage/factory/cost`
- 11 AI 助手：`/manage/ai-assistant`
- 12 系统运维与可观测：`/manage/admin/settings`
- 13 权限与治理中心：`/manage/admin/governance`
- 14 主数据与模板中心：`/manage/master`

02 登录、04 填报流程、15 响应式录入体验不是业务侧边导航中心。

## Legacy Redirect

- `/mobile/*` -> `/entry/*`
- `/dashboard/*` -> `/manage/*`
- `/master/*` -> `/manage/*`
- `/review/*` 和 `/admin/*` -> `/manage/*`
- `/review/roadmap` -> `/manage/overview`
