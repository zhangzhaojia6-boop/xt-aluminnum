# 设计稿反推落地计划

> 本计划只覆盖“由 image-2 理想设计稿反推到可运行项目”的路径。业务链路修复和真实数据入库继续按独立闭环推进。

## 成功标准

- `docs/ui-reference/highres/` 与 `IMAGE2_PROMPTS.md` 能覆盖主要产品页面，并且视觉方向统一为深色工业科技风、蓝黑基底、冷蓝高光。
- 前端路由、导航、组件和 token 能对应设计稿，不靠静态截图撑页面。
- 管理端关键数值有单位、来源、新鲜度和口径说明。
- 填报端上传、外部生产系统线索、数据库事实和管理端展示之间能形成可追溯链路。
- 每轮改动后有对应测试、浏览器自测和文档回写。

## 当前状态

- 技术栈：Vue 3、Vite、Element Plus、Pinia、ECharts、Three.js。
- 页面壳层：`frontend/src/layout/ManageShell.vue`、`EntryShell.vue` 已存在。
- 管理端路由：`/manage/overview`、`/manage/factory/*`、`/manage/reports`、`/manage/quality`、`/manage/ingestion`、`/manage/ai-assistant`、`/manage/admin/*` 已存在。
- 设计 token：`frontend/src/design/xt-tokens.css` 已有工业蓝体系，但仍偏浅色；深色工业中枢 token 需要继续补齐。
- 目标图：`docs/ui-reference/highres/01-overview.png` 到 `15-entry-responsive.png` 已存在，但它们属于旧浅色基线，不能作为最终视觉方向。
- 当前约束：本计划只约束设计反推与页面还原，不覆盖已上线的数据链路、移动填报和 MES 绑定修复。

## 阶段 1：设计稿与目标规范

- 新增并维护 `docs/ui-reference/IMAGE2_PROMPTS.md`。
- 新增并维护 `docs/ui-reference/UI_TARGET_SPEC.md`。
- 新增并维护 `docs/ui-reference/DESIGN_REVERSE_PLAN.md`。
- 每次新增目标图后更新 `docs/ui-reference/REFERENCE_MANIFEST.md` 的页面映射、尺寸和视觉审计摘要。
- 对每张目标图记录：页面、路由、核心模块、核心字段、单位、数据来源、可复用组件。
- 旧浅色目标图必须逐步替换为深色工业科技风目标图；替换前在 manifest 标注为历史基线，不得作为最终验收证据。

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

- 在 `frontend/src/design/xt-tokens.css` 增补缺失 token：蓝黑背景阶梯、冷蓝高光、图表色、单位标记、数据来源、freshness、异常等级。
- 在 `frontend/src/design/xt-base.css` 和 `industrial.css` 中统一深色表格、筛选、图表容器、状态胶囊和移动卡片。
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

### 页面反推矩阵

| 目标页 | 当前路由 / 入口 | 主要代码入口 | 数据 / BFF 口径 | 下一步还原动作 |
| --- | --- | --- | --- | --- |
| 全域工业 AI 生产中枢总览驾驶舱 | `/manage/overview` | `frontend/src/views/factory-command/FactoryOverview.vue` | `factory_command_service.build_overview()`、`realtime_service.build_live_aggregation()` | 用深色中枢首屏重排日/月累计、填报实时性、外部 MES 绑定、异常、AI 摘要 |
| 工厂总览页 | `/manage/factory`、`/manage/factory/flow` | `FactoryDirector.vue`、`ProductionFlowScreen.vue` | `factory_command_service.list_workshops()`、生产流转 view model | 按车间 -> 机列 -> 班次 -> 卷号展示生产流转和来源新鲜度 |
| 经营驾驶舱 | `/manage/executive` | `ExecutiveDashboard.vue` | `dashboard_service`、经营估算 schemas | 补日/月/年累计、利润估算、合同达成、风险动作，不作财务结算 |
| 移动录入端 | `/entry`、`/entry/fill`、`/entry/coil/:businessDate/:shiftId` | `MobileEntry.vue`、`UnifiedEntryForm.vue`、`CoilEntryWorkbench.vue` | `work_orders`、mobile report services、扫码锁定字段 | 深色移动工作台、按卷录入、草稿、异常补录、自动校验 |
| 审核端 | `/manage/entry-center`、`/manage/reconciliation` | `ReviewTaskCenter.vue`、`ReconciliationCenter.vue` | 待补录、差异核对、字段锁定冲突 | 审核队列 + 证据抽屉 + AI 分诊，动作保持人工确认 |
| 数据中心 | `/manage/ingestion`、`/manage/imports` | `IngestionCenter.vue`、`ImportHistory.vue` | import batches、mapping preview、staging/dry-run | 深色字段映射表、来源泳道、批次时间线、row-level 校验 |
| 报表中心 | `/manage/reports` | `ReportList.vue`、`ReportDetail.vue` | report delivery、blocked data、export status | 生成/审核/导出/交付闭环，阻塞项和来源 chip 必须可见 |
| 质量与异常 | `/manage/quality`、`/manage/factory/exceptions` | `QualityCenter.vue`、`ExceptionMap.vue` | quality/reconciliation/anomaly services | 异常地图、质量处置、影响吨数、owner、老化时长 |
| 成本与效益 | `/manage/factory/cost`、`/manage/factory/cost/accounting` | `CostBenefitScreen.vue`、`CostAccountingCenter.vue` | cost snapshot、processing fee、energy/gas cost estimates | 吨铝成本、加工费、能耗、辅材、毛利估算，全部标注经营估算 |
| 库存与出入库 | `/manage/factory/destinations`、`/manage/factory/coils` | `DestinationScreen.vue`、`CoilTrace.vue` | coil flow、destination、warehouse/delivery lanes | 卷去向、库存老化、出库趋势、待确认去向 |
| 能耗与产量 | `/energy/center`、`/manage/statistics` | `EnergyCenter.vue`、`Statistics.vue` | energy entries、daily production、dashboard energy summary | kWh、m3、吨、单耗趋势与产量联动 |
| 合同与订单 | `/manage/executive` 内经营区，后续可拆 `/manage/orders` | `ExecutiveDashboard.vue` | contract progress schemas、contract Excel staging | 合同清单、订单进度、生产匹配、交付风险 |
| 运维与告警 | `/manage/admin/settings` | `LiveDashboard.vue` | readyz、healthz、deploy/version、job status | 服务探针矩阵、部署时间线、告警闭环，只读观测不伪造成功 |
| 权限与组织 | `/manage/admin/users`、`/manage/admin/governance` | `UserManagement.vue`、`GovernanceCenter.vue` | user/role/machine binding、audit logs | 角色矩阵、组织树、机列账号绑定、风险账号 |
| 系统配置 | `/manage/master`、`/manage/admin/templates`、`/manage/admin/rules` | `Workshop.vue`、`WorkshopTemplateConfig.vue`、`RuleConfigCenter.vue` | master data、template/rule configs、alias mapping | 主数据、模板、规则、单位、别名的版本化发布路径 |
| AI 助手 / 摘要 / 洞察 / 预警 / 决策建议 | `/manage/ai-assistant` | `AiWorkstation.vue` | AI conversations、evidence refs、briefings/watchlists | 操作分析员式 AI，证据链、置信度、建议动作和人工审批边界 |

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
