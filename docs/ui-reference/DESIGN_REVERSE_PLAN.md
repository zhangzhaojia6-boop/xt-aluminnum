# 设计稿反推落地计划

> 本计划只覆盖“由 image-2 理想设计稿反推到可运行项目”的路径。业务链路修复和真实数据入库继续按独立闭环推进。

## 成功标准

- `docs/ui-reference/highres/` 与 `IMAGE2_PROMPTS.md` 能覆盖主要产品页面。
- 前端路由、导航、组件和 token 能对应设计稿，不靠静态截图撑页面。
- 管理端关键数值有单位、来源、新鲜度和口径说明。
- 填报端上传、外部生产系统线索、数据库事实和管理端展示之间能形成可追溯链路。
- 每轮改动后有对应测试、浏览器自测和文档回写。

## 当前状态

- 技术栈：Vue 3、Vite、Element Plus、Pinia、ECharts、Three.js。
- 页面壳层：`frontend/src/layout/ManageShell.vue`、`EntryShell.vue` 已存在。
- 管理端路由：`/manage/overview`、`/manage/factory/*`、`/manage/reports`、`/manage/quality`、`/manage/ingestion`、`/manage/ai-assistant`、`/manage/admin/*` 已存在。
- 设计 token：`frontend/src/design/xt-tokens.css` 已有冷白工业底色和工业蓝体系。
- 目标图：`docs/ui-reference/highres/01-overview.png` 到 `15-entry-responsive.png` 已存在。
- 当前脏改动：移动端锁定字段等价校验相关文件正在修改中，本计划不得覆盖。

## 阶段 1：设计稿与目标规范

- 新增并维护 `docs/ui-reference/IMAGE2_PROMPTS.md`。
- 新增并维护 `docs/ui-reference/UI_TARGET_SPEC.md`。
- 新增并维护 `docs/ui-reference/DESIGN_REVERSE_PLAN.md`。
- 每次新增目标图后更新 `docs/ui-reference/REFERENCE_MANIFEST.md` 的页面映射、尺寸和视觉审计摘要。
- 对每张目标图记录：页面、路由、核心模块、核心字段、单位、数据来源、可复用组件。

验证：

```powershell
Get-ChildItem docs\ui-reference
Get-ChildItem docs\ui-reference\highres
```

## 阶段 2：路由与信息架构对齐

- 对齐 `frontend/src/router/index.js` 与目标模块。
- 对齐 `frontend/src/config/manage-navigation.js`，补齐经营、报表、数据、AI、管理分组。
- 保留现有 `/entry`、`/manage`、`/team-lead` 边界。
- 不删除旧路由，先用 redirect 或导航收敛保护兼容性。

验证：

```powershell
Set-Location frontend
npm run test:unit
npm run build
```

## 阶段 3：设计系统落地

- 在 `frontend/src/design/xt-tokens.css` 增补缺失 token：图表色、单位标记、数据来源、freshness、异常等级。
- 在 `frontend/src/design/xt-base.css` 和 `industrial.css` 中统一表格、筛选、图表容器、状态胶囊和移动卡片。
- 扩展 `frontend/src/components/xt/`：
  - `XtKpi`：数值、单位、来源、新鲜度。
  - `XtTable`：密集表格、单位列、状态列。
  - `XtStatus`：审核、绑定、异常、来源状态。
  - `XtPageHeader`：业务日期、班次、来源、刷新。
  - `XtFactoryMap`：工厂流转示意。
  - `XtEvidenceRail`：证据链与口径。

验证：

```powershell
Set-Location frontend
npm run build
```

## 阶段 4：核心页面还原

优先顺序：

1. `/manage/overview`：总览驾驶舱，先解决离谱产量、单位和来源可见性。
2. `/manage/factory/machine-lines`：机列视图，打通填报端实时上传与外部生产系统线索绑定。
3. `/manage/entry-center`：审核中心，突出待归属、锁定字段冲突、补录缺口。
4. `/manage/ingestion`：数据接入，展示导入批次、字段映射、dry-run/staging 状态。
5. `/manage/reports`：日报交付，展示阻塞项、审核状态和导出。
6. `/entry/fill`：移动录入，强化扫码锁定字段、草稿、失败重试。

每个页面落地时必须把业务逻辑拆到 composables、services、mappers 或 utils，页面只做组合和呈现。

验证：

```powershell
Set-Location frontend
npm run build
npm run e2e:smoke
```

## 阶段 5：数据链路修复

链路拆解：

```text
移动填报端
  -> frontend/src/api/mobile.js
  -> backend mobile/report routers and services
  -> database production / entry / assignment records
  -> backend realtime / factory command APIs
  -> frontend stores and management pages
  -> chart and report view models
```

重点核查：

- 扫码锁定字段：卷号、合金、规格、机列、班次。
- 表单字段：投料、产出、废料、去向、异常、备注。
- 单位换算：移动端 kg 与管理端吨。
- 日期口径：business_date、班次、日累计、月累计。
- 权限：fill-only、operator、review、admin。
- 缓存：前端 store、API freshness、后端聚合缓存。
- 离谱数据：种子数据、测试数据、月累计误当日累计、kg/吨误换算。

验证：

```powershell
python -m pytest backend/tests -q
Set-Location frontend
npm run test:unit
npm run build
```

## 阶段 6：真实报表入库策略

- `daily_production_report`、`energy_usage_report`、`gas_usage_report` 已具备优先入库价值。
- `contract_report`、`yield_rate_matrix`、`utility_power_report`、`park_cutting_transfer_report` 需要字段级 dry-run。
- `consumable_usage_report` 先做 parser + staging，不直接写正式事实表，直到业务角色确认。
- `shipping_image_capture` 需要 OCR 或人工结构化，不自动当结构化事实写入。

每个真实报表类型必须先满足：

- 可读文件样本。
- 字段映射表。
- 单位归一。
- dry-run 输出。
- row-level validation。
- 测试覆盖。
- 备份与回滚路径。

## 阶段 7：视觉验收

每个关键页面至少验收：

- 桌面：`1440 x 900`、`1672 x 941`。
- 移动：`375 x 667`、`390 x 844`、`414 x 896`、`768 x 1024`。
- 文本不溢出。
- 图表不空白。
- 单位可见。
- 空态、加载态、错误态可读。
- 移动端没有管理端信息泄漏。

## 阶段 8：部署与环境

- 核查 `.env.example` 与服务器 `.env` 的缺口。
- 不猜密钥和账号；缺失项形成清单。
- 验证 backend readyz、frontend build、systemd/nginx、数据库连接、导入脚本环境。
- 部署前备份数据库，部署后验证真实接口和关键页面。

## 回滚策略

- 文档和前端视觉改动可用 git revert 回退。
- 数据入库前必须创建数据库备份。
- staging 导入优先于正式事实表写入。
- 未确认口径的数据只读展示，不参与正式汇总。

## 高清图到 Vue 落点校准

以下矩阵用于把 `docs/ui-reference/highres/*.png`、`UI_TARGET_SPEC.md` 与实际前端代码路径对齐。状态与差距以 `GAP_MATRIX.md` 为准；若路径不存在，必须写 `TODO`，不得把未落地页面写成已实现。

| 图号 | 中心名 | 路由 | Vue 组件落点 | 当前判断 | 下一步反推动作 |
|---|---|---|---|---|---|
| 01 | 系统总览主视图 | `/manage/overview` | `frontend/src/views/factory-command/FactoryOverview.vue` | 收敛中 | 用 `XtKpi`、`XtFactoryMap` 和 `XtTable` 替换局部自绘表格；补 `GET /dashboard/delivery-status` 的交付阻塞条；统一 ECharts `xt-hud` 主题。 |
| 02 | 登录与角色入口 | `/login` | `frontend/src/views/Login.vue` | 收敛中 | 保留 `XtFactoryMap` 与 `ParticleField`；补 `GET /dashboard/external-readiness` 的三项状态行；压缩左侧说明文案到 0 段。 |
| 03 | 独立填报端首页 | `/entry` | `frontend/src/views/mobile/MobileEntry.vue` | 半成品 | 补 2x2 主操作网格、离线重试状态和草稿入口；把触控目标统一到 `44px`；确保无管理端指标泄漏。 |
| 04 | 填报流程页 | `/entry/fill` | `frontend/src/views/mobile/UnifiedEntryForm.vue` | 收敛中 | 强化锁定字段视觉和 mismatch 状态；把投料/产出/废料/去向/异常/照片分组映射到 `EntryFieldInput`；补底部 `64px` 操作条防遮挡。 |
| 05 | 工厂作业看板 | `/manage/factory`、`/manage/factory/machine-lines` | `frontend/src/views/dashboard/FactoryDirector.vue`、`frontend/src/views/factory-command/MachineLineScreen.vue` | 半成品 | 合并机列卡、绑定表、外部生产系统线索；补待归属热力和差异瀑布；所有重量列统一 `吨`。 |
| 06 | 数据接入与字段映射中心 | `/manage/ingestion` | `frontend/src/views/review/IngestionCenter.vue` | 半成品 | 把来源泳道、字段映射表和批次时间线落到 `20:55:25`；补 `GET /imports/daily-production/mapping-preview` 的单位和校验列。 |
| 07 | 审阅中心 | `/manage/entry-center` | `frontend/src/views/review/ReviewTaskCenter.vue` | 收敛中 | 保留 `ReferenceDataTable`；补证据抽屉 `30%`、锁定字段冲突队列和 owner 缺口队列；AI 仅给建议不自动通过。 |
| 08 | 日报与交付中心 | `/manage/reports` | `frontend/src/views/reports/ReportList.vue` | 半成品 | 补 6 KPI、趋势图和交付清单；把 `GET /dashboard/delivery-status` 的阻塞项固定在右栏；导出走 `GET /reports/{report_id}/export`。 |
| 09 | 质量与告警中心 | `/manage/quality` | `frontend/src/views/quality/QualityCenter.vue` | 半成品 | 补 Pareto、异常趋势、未解决老化；右栏落 AI 分诊和处置时间线；处置按钮在无接口时禁用。 |
| 10 | 成本核算与效益中心 | `/manage/factory/cost` | `frontend/src/views/factory-command/CostBenefitScreen.vue` | 半成品 | 当前仅 3 个估算卡；需补 5 KPI、成本构成堆叠图、能耗趋势、车间贡献表和口径缺口 rail。 |
| 11 | AI 助手 | `/manage/ai-assistant` | `frontend/src/views/ai/AiWorkstation.vue` | 收敛中 | 已有会话、briefing、watchlist；补证据 chips、工具调用时间线、审批要求和右栏数据新鲜度。 |
| 12 | 系统运维与可观测 | `/manage/admin/settings` | `frontend/src/views/reports/LiveDashboard.vue` | 半成品 | 现页面偏实时生产；需补服务矩阵、readyz/healthz、版本、失败作业和探针未知态；严禁伪造全绿。 |
| 13 | 权限与治理中心 | `/manage/admin/governance` | `frontend/src/views/review/GovernanceCenter.vue` | 半成品 | 现有权限表较薄；需补角色矩阵、数据边界、审计日志、风险账号和治理 KPI。 |
| 14 | 主数据与模板中心 | `/manage/master` | `frontend/src/views/master/Workshop.vue` | 半成品 | 现为车间表；需扩展主数据卡片网格、模板配置表、枚举/别名 tab、字段规则和 owner 表。 |
| 15 | 响应式录入体验 | `/entry`、`/entry/fill` | `frontend/src/views/mobile/MobileEntry.vue`、`frontend/src/views/mobile/UnifiedEntryForm.vue` | 收敛中 | 把 390px 手机壳、桌面审阅预览、草稿/历史恢复和底部导航冲突纳入视觉验收。 |
| 16 | 库存与出入库中心 | `/manage/factory/destinations` | `frontend/src/views/factory-command/DestinationScreen.vue` | 未开工 | `docs/ui-reference/highres/16-*.png` 缺失；先生成高清图，再落卷级流向表、库存结构和待去向队列。 |
| 17 | 合同与订单中心 | TODO `/manage/contracts` | TODO `frontend/src/views/contracts/ContractOrderCenter.vue` | 未开工 | `docs/ui-reference/highres/17-*.png`、路由和组件均缺失；先补 contract dry-run endpoint 与设计基线。 |
| 18 | 能源中心 | `/energy/center` | `frontend/src/views/energy/EnergyCenter.vue` | 未开工 | `docs/ui-reference/highres/18-*.png` 缺失；页面存在但不在高清基线；补能耗趋势、天然气、导入批次和口径缺口。 |
| 19 | 班长一屏 | `/team-lead` | `frontend/src/views/team/TeamLeadShell.vue` | 未开工 | `docs/ui-reference/highres/19-*.png` 缺失；补班组进度、人员状态、机台任务和考勤异常确认图。 |
| 20 | 统计中心 | `/manage/statistics` | `frontend/src/views/dashboard/Statistics.vue` | 未开工 | `docs/ui-reference/highres/20-*.png` 缺失；补统计 KPI、多维趋势、筛选口径和导出边界。 |
| 21 | 文件导入中心 | `/imports/files` | `frontend/src/views/imports/FileImport.vue` | 未开工 | `docs/ui-reference/highres/21-*.png` 缺失；补 dry-run 上传、批次历史、映射预览和行级校验失败。 |
