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

- `/review/overview`
- `/review/factory`
- `/review/workshop`
- `/review/tasks`
- `/review/reports`
- `/review/quality`
- `/review/reconciliation`
- `/review/cost-accounting`
- `/review/brain`

### 管理端 Admin

- `/admin`
- `/admin/ingestion`
- `/admin/master`
- `/admin/master/templates`
- `/admin/users`
- `/admin/governance`
- `/admin/ops`

## 中心页列表

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

02 登录、04 填报流程、15 响应式录入体验不是业务侧边导航中心。

## Legacy Redirect

- `/mobile/*` -> `/entry/*`
- `/dashboard/*` -> `/review/*`
- `/master/*` -> `/admin/master/*`
- `/review/ingestion`、`/review/template-center`、`/review/governance`、`/review/ops-reliability` -> `/admin/*`
- `/review/roadmap` -> `/review/overview`
