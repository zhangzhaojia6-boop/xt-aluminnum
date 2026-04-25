# 高清目标图基线

## 目录

- 高清目标图目录：`docs/ui-reference/highres/`
- 当前优先页面：`/admin/master`
- 本轮使用图：`14-master-template.png`

## 文件与中心映射

| 中心编号 | 文件名 | 页面 / 中心 |
| --- | --- | --- |
| 01 | `01-overview.png` | 系统总览主视图 |
| 02 | `02-login.png` | 登录与角色入口 |
| 03 | `03-entry-home.png` | 独立填报端首页 |
| 04 | `04-entry-flow.png` | 填报流程页 |
| 05 | `05-factory-board.png` | 工厂作业看板 |
| 06 | `06-ingestion-mapping.png` | 数据接入与字段映射中心 |
| 07 | `07-review-tasks.png` | 审阅中心 |
| 08 | `08-reports-delivery.png` | 日报与交付中心 |
| 09 | `09-quality-alerts.png` | 质量与告警中心 |
| 10 | `10-cost-benefit.png` | 成本核算与效益中心 |
| 11 | `11-ai-control.png` | AI 总控中心 |
| 12 | `12-ops-observability.png` | 系统运维与可观测 |
| 13 | `13-governance.png` | 权限与治理中心 |
| 14 | `14-master-template.png` | 主数据与模板中心 |
| 15 | `15-entry-responsive.png` | 响应式录入体验 |

## 06 视觉审计摘要

- 布局：顶部大号编号与中文标题；主体为数据源状态、字段映射表和导入概览三栏；底部为导入历史、错误 / 失败说明、操作区和口径说明。
- 视觉：白底 / 浅灰蓝背景，细边框卡片，大号蓝色编号，高密表格，绿色 / 红色 / 橙色表达校验、失败和待处理状态。
- 业务元素：MES、PLC、质检系统、能耗系统、ERP、手工录入、字段名称、字段类型、数据源字段、映射方式、校验状态、导入历史、成功率和失败记录。
- 转译组件：`CenterPageShell`、`KpiStrip`、`SectionCard`、`DataTableShell`、`StatusBadge`、`SourceBadge`、`MockDataNotice`。

## 08 视觉审计摘要

- 布局：顶部大号编号与中文标题，右侧业务日期控件；中部为高密 KPI、日量趋势图和交付清单；底部为导出与发送操作区。
- 视觉：白底 / 浅灰蓝背景，细边框卡片，大号蓝色编号，深色数字，绿色增长状态，表格与清单保持紧凑密度。
- 业务元素：日产、订单达成率、综合成品率、计划交付、已交付、待分发、PDF / Excel 导出、发送 / 交付、阻塞项和 auto_confirmed 口径。
- 转译组件：`CenterPageShell`、`KpiStrip`、`SectionCard`、`DataTableShell`、`StatusBadge`、`SourceBadge`、`MockDataNotice`。

## 09 视觉审计摘要

- 布局：顶部大号编号与中文标题；主体左侧为高密告警列表，右侧为质量处置流程；补充 KPI、AI 辅助分诊、阻塞风险和口径说明。
- 视觉：白底 / 浅灰蓝背景，细边框卡片，大号蓝色编号，紧凑表格，红 / 橙 / 绿状态色表达高、中、低风险与处理状态。
- 业务元素：质量告警、告警来源、严重度、处理状态、质检补录、日报交付影响、AI 关注点、处置、追溯和查看历史。
- 转译组件：`CenterPageShell`、`KpiStrip`、`SectionCard`、`DataTableShell`、`StatusBadge`、`SourceBadge`、`MockDataNotice`。

## 10 视觉审计摘要

- 布局：顶部大号编号与中文标题；右侧为产量口径 / 通货口径切换；主体包含车间 tab、KPI、成本构成趋势、累计构成、操作区、风险摘要和口径说明。
- 视觉：白底 / 浅灰蓝背景，细边框卡片，大号蓝色编号，蓝色主按钮，蓝 / 绿 / 青 / 紫 / 橙 / 灰表示成本构成。
- 业务元素：吨铝成本、人工、电耗、天然气、辅材 / 损耗、产量口径、通货口径、累计构成、调整方案、查看口径、导出和经营风险。
- 转译组件：`CenterPageShell`、`KpiStrip`、`SectionCard`、`DataTableShell`、`StatusBadge`、`SourceBadge`、`MockDataNotice`。

## 11 视觉审计摘要

- 布局：顶部大号编号与中文标题；主体为今日摘要 / KPI、风险事件 Top5、智能助手追问入口；补充多专题 AI 卡片、证据链 / 数据来源、建议动作和口径说明。
- 视觉：白底 / 浅灰蓝背景，细边框卡片，大号蓝色编号，深色数字，红 / 橙 / 绿状态色表达高风险、中风险与正常提示，蓝色按钮用于查看证据和中心跳转。
- 业务元素：今日摘要、风险事件、日报交付阻塞、质量关注、成本解释、数据接入 fallback / mixed、AI 辅助建议、证据来源和追问入口。
- 转译组件：`CenterPageShell`、`KpiStrip`、`SectionCard`、`DataTableShell`、`StatusBadge`、`SourceBadge`、`MockDataNotice`。

## 12 视觉审计摘要

- 布局：顶部大号编号与中文标题，右侧版本信息；主体左侧为系统健康 KPI，右侧为关键服务实时监控；下方为部署与告警时间线，并扩展为服务探针矩阵、趋势、版本部署、操作区、风险与日志摘要。
- 视觉：白底 / 浅灰蓝背景，细边框卡片，大号蓝色编号，深色大数字，绿色 / 红色 / 橙色表达健康、错误率、阻塞和 warning，趋势图与时间线保持轻量。
- 业务元素：healthz、readyz、hard_gate_passed、frontend、backend、database、gateway / nginx、scheduler / jobs、message / push、AI probe、report pipeline、version、build time、error rate、latency、recent failures、go-live gate 和 rollback readiness。
- 转译组件：`CenterPageShell`、`KpiStrip`、`SectionCard`、`DataTableShell`、`StatusBadge`、`SourceBadge`、`MockDataNotice`。

## 13 视觉审计摘要

- 布局：顶部大号编号与“权限与治理中心”标题；主体左侧为角色权限矩阵，右侧为最近审计日志与审计完整性摘要；落地扩展为权限 KPI、数据权限边界、风险异常、系统设置、操作区和口径说明。
- 视觉：白底 / 浅灰蓝背景，细边框卡片，大号蓝色编号，粗体标题，高密度权限矩阵，绿色勾选、红色叉号和灰色禁用态表达权限边界。
- 业务元素：admin、manager、reviewer、operator、owner-only、fill-only、Entry / Review / Admin、数据范围、审计日志、登录记录、权限变更记录、风险账号和系统设置。
- 转译组件：`CenterPageShell`、`KpiStrip`、`SectionCard`、`DataTableShell`、`StatusBadge`、`SourceBadge`、`MockDataNotice`。

## 14 视觉审计摘要

- 布局：顶部大号编号与“主数据与模板中心”标题；目标图主体为主数据、模板配置、枚举配置、别名管理 tab 与主数据卡片网格；落地扩展为 KPI、主数据分类表、模板配置表、字段规则 / owner 表、数据缺口 / 风险、操作区和口径说明。
- 视觉：白底 / 浅灰蓝背景，细边框卡片，大号蓝色编号，蓝色线性图标语汇，高密表格补足配置细节，绿 / 橙 / 红 / 灰表达启用、待完善、高风险和禁用态。
- 业务元素：车间、班组、员工、机台、用户、班次、别名、字典、模板、字段规则、owner 字段、必填项、校验规则、启用状态和主数据缺口。
- 转译组件：`CenterPageShell`、`KpiStrip`、`SectionCard`、`DataTableShell`、`StatusBadge`、`SourceBadge`、`MockDataNotice`。

## 设计约束

- 参考图是视觉与信息架构基线，不作为静态截图嵌入产品。
- 不把图中装饰元素机械照搬，不使用纯展示型大屏语汇覆盖生产协同边界。
- 必须转译成可运行 Web 组件，保持 `/entry`、`/review`、`/admin` 三端边界。
- `/review/reports` 是日报生成、导出与交付状态读面，不承接生产事实写入。
- `/review/quality` 是质量告警与处置状态读面，当前为 fallback 数据；AI 仅作辅助分诊，处置写动作在无真实接口时禁用，不承接生产事实写入。
- `/review/cost-accounting` 是经营估算 / 策略口径读面，当前为 fallback 数据；调整方案与导出在无真实接口时禁用，不承接生产事实写入，不作为财务结算依据。
- `/review/brain` 是审阅端 AI 总控中心，当前为 fallback / mixed 证据读面；AI 仅作辅助解释与建议，生成与追问在无真实接口时禁用，不自动执行质量、成本、排产或交付动作。
- `/admin/ops` 是管理端运维观测面，当前为 fallback / mixed 只读观测数据；刷新、readiness、健康检查和上线闸门仅做只读状态查看，回滚预检、导出诊断和查看日志在无真实接口时禁用，不执行部署、回滚、重启或自动修复，不伪造 health / ready / AI probe 成功。
- `/admin/governance` 是管理端权限治理面，当前为 fallback / mixed 只读治理数据；查看审计、角色矩阵、风险账号和相关中心跳转仅做只读/导航动作，导出审计与保存策略在无真实接口时禁用，不绕过后端权限模型，不直接修改生产事实或真实授权策略。
- `/admin/master` 是管理端主数据配置面，当前为 fallback / mixed 只读配置底座数据；查看、筛选、跳转和刷新仅做只读/导航动作，导出配置、发布模板和保存字段规则在无真实接口时禁用，不绕过后端主数据与权限模型，不直接修改生产事实或真实模板发布。
