# 代码库审计记录

## 本轮发现

- `frontend/src/components/app/KpiCard.vue` 与 `frontend/src/components/cards/KpiCard.vue` 同名，触发 Vite 自动组件导入冲突。
- `frontend/src/views/review/RoadmapCenter.vue` 已从正式路由隔离并删除，但工作区仍有上一轮遗留的 staged/unstaged 混合状态。
- `frontend/src/reference-command/components/CommandPage.vue` 承载多个中心页，短期继续保留，避免本轮扩成多页面重写。
- 多个中心页仍使用 fallback/mock 数据，需要持续显式展示 `MockDataNotice` 或 source 标识。
- 成本中心定位为经营估算 / 策略口径，不是财务结算。
- 数据接入中心归属 `/admin/ingestion`，`/review/ingestion` 只做 legacy redirect。
- 高清目标图已切换为 `docs/ui-reference/highres/` 基线，文件名按 01-15 中心编号规整；`/review/reports` 对齐 `08-reports-delivery.png`。
- `/review/reports` 当前使用 `reportsCenterMock` fallback 读面数据，口径为 `auto_confirmed` / 已自动确认；导出 PDF、导出 Excel、发送/交付、重新生成均保持 disabled，不写入生产事实。
- `/review/quality` 当前使用 `qualityCenterMock` fallback 读面数据，对齐高清目标图 `09-quality-alerts.png`；标记处理中、关闭、导出告警清单、查看历史等处置动作保持 disabled，AI 仅作为辅助分诊，不自动关闭告警。
- `/review/cost-accounting` 当前使用 `costCenterMock` fallback 经营估算 / 策略口径，对齐高清目标图 `10-cost-benefit.png`；调整方案、导出保持 disabled，查看日报影响、查看质量风险、看工厂看板为跳转动作。本页不承接生产事实写入，不作为财务结算或月度入账依据。

## 本轮处理方向

- 将 app KPI 组件重命名为 `AppKpiCard`，消除自动导入冲突。
- 增强通用组件契约：状态、来源、表格 loading/empty、fallback 类型。
- 只深改 6 个指定页面，其余页面做轻量一致性检查。
- 新增 route contract e2e，锁定 `/entry`、`/review`、`/admin` 与 legacy redirect。
- 本轮 reports route smoke 增加标题、编号、交付清单、导出按钮、口径、source 标识与 fill-only 访问边界断言。
- 本轮 quality route smoke 增加标题、编号、告警列表、严重度、处置状态、source 标识、AI 辅助分诊、只读边界与 fill-only 访问边界断言。
- 本轮 cost route smoke 增加标题、编号、经营估算 / 策略口径、吨铝成本、电耗、天然气、口径切换、source 标识、只读边界与 fill-only 访问边界断言。
