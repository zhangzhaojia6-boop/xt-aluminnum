# 代码库审计记录

## 本轮发现

- `frontend/src/components/app/KpiCard.vue` 与 `frontend/src/components/cards/KpiCard.vue` 同名，触发 Vite 自动组件导入冲突。
- `frontend/src/views/review/RoadmapCenter.vue` 已从正式路由隔离并删除，但工作区仍有上一轮遗留的 staged/unstaged 混合状态。
- `frontend/src/reference-command/components/CommandPage.vue` 承载多个中心页，短期继续保留，避免本轮扩成多页面重写。
- 多个中心页仍使用 fallback/mock 数据，需要持续显式展示 `MockDataNotice` 或 source 标识。
- 成本中心定位为经营估算 / 策略口径，不是财务结算。
- 数据接入中心正式落到 `/manage/ingestion`，`/admin/ingestion` 与 `/review/ingestion` 只做 legacy redirect。
- 高清目标图已切换为 `docs/ui-reference/highres/` 基线，文件名按 01-15 中心编号规整；`/review/reports` 对齐 `08-reports-delivery.png`。
- `/review/reports` 已收口到 `/manage/reports` 的 `ReportList.vue`，通过 `frontend/src/api/reports.js` 读取日报、详情、审核、发布、最终版和导出接口。
- `/review/quality` 已收口到 `/manage/quality` 的 `QualityCenter.vue`，通过 `frontend/src/api/quality.js` 执行质量检查、问题列表、解决和忽略。
- `/review/cost-accounting` 已作为 legacy redirect 收口到 `/manage/factory/cost`，由 `CostBenefitScreen.vue` 通过 `/api/v1/factory-command/cost-benefit` 展示经营估算，不作为财务结算或月度入账依据。`/manage/factory/cost/accounting` 已挂载 `CostAccountingCenter.vue` 作为策略核算工作台，承接 `frontend/src/services/costing/*` 的表模型快照和 admin-only “保存快照”动作；该入口仍不等同于人工复核或正式月结。
- `/admin/ingestion` 已收口到 `/manage/ingestion` 的 `IngestionCenter.vue`，调用导入历史和各类导入接口；本页不表示外部 MES/ERP 已正式联通。
- `/review/brain` 已收口到 `/manage/ai-assistant` 的 `AiWorkstation.vue`，通过 AI chat store 接会话、消息、主动汇报和关注列表；AI 仅作为辅助解释与建议，不自动执行生产、质量、成本、排产或交付动作。
- `/admin/ops` 已收口到 `/manage/admin/settings` 的 `LiveDashboard.vue`，展示 dashboard、factory-command 与管理概览数据；不执行部署、回滚、重启或自动修复。
- `/admin/governance` 已收口到 `/manage/admin/governance` 的 `GovernanceCenter.vue`，基于 auth store 和用户接口展示权限边界与角色分布，不绕过后端权限模型，不直接修改生产事实或真实授权策略。
- `/admin/master` 当前重定向到 `/manage/master`，由 `Workshop.vue` 直接调用 `/api/v1/master/workshops` 真实接口承接车间主数据的查看、新增、编辑和删除；`/admin/master/templates` 独立进入 `WorkshopTemplateConfig.vue`。本页属于管理端主数据配置面，不绕过后端主数据与权限模型，不直接修改生产事实。

## 本轮处理方向

- 将 app KPI 组件重命名为 `AppKpiCard`，消除自动导入冲突。
- 增强通用组件契约：状态、来源、表格 loading/empty、fallback 类型。
- 只深改 6 个指定页面，其余页面做轻量一致性检查。
- 新增 route contract e2e，锁定 `/entry`、`/review`、`/admin` 与 legacy redirect。
- 本轮 reports route smoke 增加标题、编号、交付清单、导出按钮、口径、source 标识与 fill-only 访问边界断言。
- 本轮 quality route smoke 增加标题、编号、告警列表、严重度、处置状态、source 标识、AI 辅助分诊、只读边界与 fill-only 访问边界断言。
- 本轮 cost route smoke 增加标题、编号、经营估算 / 策略口径、吨铝成本、电耗、天然气、口径切换、source 标识、只读边界与 fill-only 访问边界断言。
- 本轮 ingestion route smoke 增加标题、编号、数据源、字段映射、导入历史、成功率、source 标识、只读边界与非 admin 访问边界断言。
- 本轮 brain route smoke 增加标题、编号、辅助建议 / 系统提示、今日摘要、风险事件、证据链 / 数据来源、source 标识、禁止伪造自动决策文案、禁止生产事实写入按钮与 fill-only 访问边界断言。
- 本轮 ops route smoke 增加标题、编号、healthz、readyz、hard gate、错误率、响应时间、fallback/source 标识、禁用回滚/导出/日志操作、禁止伪造自动修复/真实回滚/部署成功文案与非 admin 访问边界断言。
- 本轮 governance route smoke 增加标题、编号、角色矩阵、审计日志、数据权限、高风险账号 / 治理风险、fallback/source 标识、禁用导出审计与保存策略、禁止伪造权限保存/安全策略生效/审计清理文案、禁止生产事实写入按钮与非 admin 访问边界断言。
- 本轮 master route smoke 增加标题、编号、车间、班组、机台、模板配置、字段规则 / 字段 owner、fallback/source 标识、禁用导出配置/发布模板/保存字段规则、禁止伪造主数据保存/模板发布/字段同步文案、禁止生产事实写入按钮与三端边界断言。
