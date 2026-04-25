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
- `/admin/ingestion` 当前使用 `ingestionCenterMock` fallback 管理端配置治理数据，对齐高清目标图 `06-ingestion-mapping.png`；上传文件、配置映射、重新处理、导出错误清单保持 disabled，查看错误、查看口径和相关中心跳转为只读/导航动作。本页不承接生产事实写入，不表示 MES/ERP 正式联通。
- `/review/brain` 当前使用 `brainCenterMock` fallback / mixed 证据读面，对齐高清目标图 `11-ai-control.png`；生成今日摘要与追问在无真实接口时禁用，证据查看、审阅/日报/质量/成本跳转与复制摘要保持只读/导航语义。AI 仅作为辅助解释与建议，不自动执行生产、质量、成本、排产或交付动作。
- `/admin/ops` 当前使用 `opsCenterMock` fallback / mixed 只读观测数据，对齐高清目标图 `12-ops-observability.png`；刷新探针、查看 readiness、查看健康检查、查看上线闸门只做页面状态切换，回滚预检、导出诊断、查看日志保持 disabled。本页属于管理端运维观测面，不执行部署、回滚、重启或自动修复，不伪造 health / ready / AI probe 成功。
- `/admin/governance` 当前使用 `governanceCenterMock` fallback / mixed 只读治理数据，对齐高清目标图 `13-governance.png`；查看审计、查看角色矩阵、查看风险账号、进入主数据、进入运维观测、刷新权限视图为只读/导航动作，导出审计与保存策略保持 disabled。本页属于管理端权限治理面，不绕过后端权限模型，不直接修改生产事实或真实授权策略。

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
