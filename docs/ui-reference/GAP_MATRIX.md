# 高清 UI 差距矩阵

本表是 `docs/ui-reference/highres/`、`UI_TARGET_SPEC.md`、`IMAGE2_PROMPTS.md`、`DESIGN_REVERSE_PLAN.md` 的对齐索引。`01` 到 `15` 已有高清图；`16` 到 `21` 是当前产品版图需要补齐的高清基线槽位，文件名先按目标命名标记为 TODO。

| 图号 | 文件名 | 中心名 | 当前实现路径 | 实现状态 | 三条最大差距 |
|---|---|---|---|---|---|
| 01 | `01-overview.png` | 系统总览主视图 | `frontend/src/views/factory-command/FactoryOverview.vue` | 收敛中 | 缺 KPI 同环比小行；交付阻塞未接 `GET /dashboard/delivery-status`；能耗趋势图缺 ECharts `xt-hud` 主题 |
| 02 | `02-login.png` | 登录与角色入口 | `frontend/src/views/Login.vue` | 收敛中 | 环境状态行未稳定接 `GET /dashboard/external-readiness`；登录页缺清晰粒子降级策略；角色入口与管理/审核/填报权限边界文案仍需压缩 |
| 03 | `03-entry-home.png` | 独立填报端首页 | `frontend/src/views/mobile/MobileEntry.vue` | 半成品 | 缺 2x2 扫码/草稿/已填/异常主操作区；离线重试状态不够显眼；今日任务与最近提交未形成首屏闭环 |
| 04 | `04-entry-flow.png` | 填报流程页 | `frontend/src/views/mobile/UnifiedEntryForm.vue` | 收敛中 | 锁定字段 mismatch 状态还不够强；照片/备注入口与底部操作条容易挤压；投料/产出/废料/去向分组缺稳定 64px 底部安全区 |
| 05 | `05-factory-board.png` | 工厂作业看板 | `frontend/src/views/dashboard/FactoryDirector.vue`、`frontend/src/views/factory-command/MachineLineScreen.vue` | 半成品 | 外部生产系统线索与填报上传未并列表达；待归属热力图缺首屏位置；机列卡缺来源新鲜度和绑定状态小行 |
| 06 | `06-ingestion-mapping.png` | 数据接入与字段映射中心 | `frontend/src/views/review/IngestionCenter.vue` | 半成品 | 来源泳道缺 `20%` 左栏；字段映射表缺单位/转换规则/校验状态列；批次时间线缺 rollback readiness |
| 07 | `07-review-tasks.png` | 审阅中心 | `frontend/src/views/review/ReviewTaskCenter.vue` | 收敛中 | 证据抽屉未按 `30%` 右栏固定；锁定字段冲突队列与 owner 缺口队列需分组；AI 建议缺证据链接和新鲜度 chips |
| 08 | `08-reports-delivery.png` | 日报与交付中心 | `frontend/src/views/reports/ReportList.vue` | 半成品 | 缺 6 KPI 与日产趋势；交付清单未接 `GET /dashboard/delivery-status` 右栏；导出/发送动作缺 fallback 禁用态 |
| 09 | `09-quality-alerts.png` | 质量与告警中心 | `frontend/src/views/quality/QualityCenter.vue` | 半成品 | 缺缺陷 Pareto 和异常趋势；AI 分诊右栏缺证据链；处置时间线与 unresolved aging 未落地 |
| 10 | `10-cost-benefit.png` | 成本核算与效益中心 | `frontend/src/views/factory-command/CostBenefitScreen.vue` | 半成品 | 当前仅 3 个估算卡；缺成本构成堆叠图和能耗趋势；缺车间贡献表与口径缺口 rail |
| 11 | `11-ai-control.png` | AI 助手 | `frontend/src/views/ai/AiWorkstation.vue` | 收敛中 | 工具调用时间线不完整；证据 chips 缺来源/口径/新鲜度三元组；建议动作缺审批要求列 |
| 12 | `12-ops-observability.png` | 系统运维与可观测 | `frontend/src/views/reports/LiveDashboard.vue` | 半成品 | 当前偏生产实时看板；缺 healthz/readyz 服务矩阵；失败作业与版本部署时间线未形成运维首屏 |
| 13 | `13-governance.png` | 权限与治理中心 | `frontend/src/views/review/GovernanceCenter.vue` | 半成品 | 角色权限矩阵列数不足；审计日志缺最近变更和登录记录；风险账号与数据边界未独立成区 |
| 14 | `14-master-template.png` | 主数据与模板中心 | `frontend/src/views/master/Workshop.vue` | 半成品 | 当前只覆盖车间表；模板配置/枚举/别名 tab 未合流；字段规则 owner 表和主数据缺口未落地 |
| 15 | `15-entry-responsive.png` | 响应式录入体验 | `frontend/src/views/mobile/MobileEntry.vue`、`frontend/src/views/mobile/UnifiedEntryForm.vue` | 收敛中 | 桌面 390px 手机壳预览未标准化；草稿/历史恢复缺跨断点一致性；底部导航与提交按钮仍需防重叠验收 |
| 16 | TODO `16-inventory-movement.png` | 库存与出入库中心 | `frontend/src/views/factory-command/DestinationScreen.vue` | 未开工 | 高清图缺失；库存结构图和 aging buckets 未定义；卷级去向详情抽屉缺 endpoint 字段表 |
| 17 | TODO `17-contract-orders.png` | 合同与订单中心 | TODO `frontend/src/views/contracts/ContractOrderCenter.vue` | 未开工 | 高清图缺失；Vue 路由和组件不存在；合同 dry-run endpoint 仍是 `TODO GET /contracts/orders` |
| 18 | TODO `18-energy-center.png` | 能源中心 | `frontend/src/views/energy/EnergyCenter.vue` | 未开工 | 高清图缺失；能耗趋势图缺 ECharts `xt-hud` 主题；电耗/天然气导入批次与成本口径未并列表达 |
| 19 | TODO `19-team-lead-screen.png` | 班长一屏 | `frontend/src/views/team/TeamLeadShell.vue` | 未开工 | 高清图缺失；班组进度与人员状态未形成 `55:45` 首屏；考勤异常确认缺底部固定操作区 |
| 20 | TODO `20-statistics-center.png` | 统计中心 | `frontend/src/views/dashboard/Statistics.vue` | 未开工 | 高清图缺失；多维趋势与统计表缺统一口径栏；导出边界缺只读/禁用状态 |
| 21 | TODO `21-file-import-center.png` | 文件导入中心 | `frontend/src/views/imports/FileImport.vue` | 未开工 | 高清图缺失；dry-run 上传与批次历史未同屏；映射预览抽屉缺行级失败说明 |
