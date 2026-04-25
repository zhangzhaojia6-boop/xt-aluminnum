# 高清目标图基线

## 目录

- 高清目标图目录：`docs/ui-reference/highres/`
- 当前优先页面：`/review/reports`
- 本轮使用图：`08-reports-delivery.png`

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
| 12 | `12-ops-observability.png` | 系统运维与观测 |
| 13 | `13-governance.png` | 权限与治理中心 |
| 14 | `14-master-template.png` | 主数据与模板中心 |
| 15 | `15-entry-responsive.png` | 响应式录入体验 |

## 08 视觉审计摘要

- 布局：顶部大号编号与中文标题，右侧业务日期控件；中部为高密 KPI、日量趋势图和交付清单；底部为导出与发送操作区。
- 视觉：白底 / 浅灰蓝背景，细边框卡片，大号蓝色编号，深色数字，绿色增长状态，表格与清单保持紧凑密度。
- 业务元素：日产、订单达成率、综合成品率、计划交付、已交付、待分发、PDF / Excel 导出、发送 / 交付、阻塞项和 auto_confirmed 口径。
- 转译组件：`CenterPageShell`、`KpiStrip`、`SectionCard`、`DataTableShell`、`StatusBadge`、`SourceBadge`、`MockDataNotice`。

## 设计约束

- 参考图是视觉与信息架构基线，不作为静态截图嵌入产品。
- 不把图中装饰元素机械照搬，不使用纯展示型大屏语汇覆盖生产协同边界。
- 必须转译成可运行 Web 组件，保持 `/entry`、`/review`、`/admin` 三端边界。
- `/review/reports` 是日报生成、导出与交付状态读面，不承接生产事实写入。
