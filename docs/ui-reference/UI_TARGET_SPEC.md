# 鑫泰铝业 数据中枢 UI 目标规范

## 目标

把现有 `Vue 3 + Vite + Element Plus + ECharts + Three.js` 前端收敛成可试用、可展示、可继续接真实数据上线迭代的工业 AI 协同平台。设计稿追求理想态，但落地必须服从真实业务闭环：填报端上传、外部生产系统线索、数据库事实、管理端图表和审核报表要能互相解释。

## 产品边界

- 产品名称：`鑫泰铝业 数据中枢`。
- 外部生产系统：只作为数据源、字段对照、只读同步或人工核对边界。
- 填报端：一线人员按机列、班次、卷号录入，强调低负担、锁定字段可信、离线/草稿可恢复。
- 管理端：领导、审核员、管理员看真实生产状态、异常、成本、质量、库存、报表和系统健康。
- AI：只做分析、解释、建议、证据汇总和操作前辅助判断，不自动替代审核、财务结算或生产授权。

## 信息架构

### 一级导航

- 总览：经营与生产状态首屏。
- 工厂：生产流转、机列、卷级追踪、库存去向、异常地图。
- 经营：成本效益、合同订单、加工费。
- 质量：质量异常、差异核对、审核处置。
- 报表：日报、月报、交付、导出。
- 数据：接入、字段映射、导入历史。
- AI：分析工作台、证据链、建议动作。
- 管理：主数据、权限组织、系统配置、运维告警。

### 移动端入口

- 填报首页：角色、班次、机列、今日任务。
- 扫码录入：卷号、锁定字段、投料/产出/废料/去向。
- 草稿与历史：最近提交、失败重试、异常补录。
- 我的：账号、角色、机列绑定、退出。

## 视觉系统

### 色彩

- 页面背景：冷白与浅灰蓝，避免深色大屏。
- 主色：工业蓝，用于主动作、关键线索、当前状态。
- 成功：低饱和绿色，用于已入账、已审核、服务正常。
- 警告：琥珀色，用于待审核、缺字段、口径未确认。
- 危险：克制红色，用于异常、锁定字段不一致、离谱数据。
- 文本：深蓝灰，数字使用等宽或 DIN 风格。

### 布局

- 桌面端使用固定侧栏 + 顶部工具条 + 内容工作区。
- 页面内容优先表格、图表和事实链，不使用营销式 hero。
- 卡片只用于独立信息块，不做卡片套卡片。
- 图表必须绑定业务问题：产量、能耗、质量、成本、库存、订单、异常、审核。
- 所有数值必须显示单位；没有可信单位时显示数据缺口，不猜。

### 动效

- 只使用克制状态动效：数据流、审核推进、AI 读取/核对/生成。
- 禁用持续抢眼动画和 `transition: all`。
- 必须支持 `prefers-reduced-motion`。

## 核心页面标准

### 总览驾驶舱

- 必须展示日/月累计、产量、能耗、质量、成本、效益、库存、出入库、合同订单、异常、审核、告警和 AI 建议。
- 首屏 KPI 必须能解释“今天做了多少、谁做的、去哪了、还有什么没确认”。
- 管理端不得再出现约 `10w` 这类脱离实际的产量；异常值必须定位来源并标注口径。

### 生产与机列

- 以车间 -> 机列 -> 班次 -> 卷号 -> 去向为主链。
- 填报端上传数据和外部生产系统线索要并列显示，明确哪些已绑定、待归属、冲突。
- 图表至少包括机列产量排行、待归属热力、差异瀑布、卷流向。

### 数据中心

- 文件导入、填报端、外部生产系统、主数据、手工补录都要有来源、批次、时间、新鲜度和单位。
- 未确认业务角色的真实报表只能先做 dry-run 或 staging，不直接写正式事实表。
- 每个字段映射要保留原字段、规范字段、单位、转换规则和验证状态。

### 报表中心

- 日报/月报必须从事实数据或明确标注的 staged 数据生成。
- 报表交付要显示阻塞项、数据缺口、审核状态和导出状态。

### AI 工作台

- AI 输出必须带证据来源、计算口径和建议动作。
- 没有接口或授权时，只展示建议，不展示可执行按钮。

## 数据口径

- `吨`：管理端产量、投料、出库、库存的主显示单位。
- `kg`：移动填报端可输入重量，入库和管理端展示时统一换算并标注。
- `kWh`：电耗。
- `m3`：天然气。
- `%`：成品率、订单达成、缺陷占比。
- `元/吨`、`万元`：经营估算，不作为财务结算。

## 当前可复用资产

- `frontend/src/design/xt-tokens.css`：已有工业蓝、冷白面、字号、圆角、阴影 token。
- `frontend/src/layout/ManageShell.vue`：已有管理端侧栏、搜索、AI 抽屉入口。
- `frontend/src/components/xt/*`：已有 XT 组件族，可继续扩展，不必重建组件库。
- `frontend/src/components/charts/*`：已有产量排行、废料率、差异瀑布、待归属热力图。
- `docs/ui-reference/highres/*.png`：已有 15 张高清目标图，可作为第一批视觉基准。

## 不做

- 不把产品命名为外部生产系统。
- 不为了视觉效果引入假数据、假字段、假成功状态。
- 不新增前端技术栈迁移，除非现有 Vue 架构无法承载具体页面。
- 不把复杂业务算法硬编码在页面组件里。
- 不将未经确认的真实报表直接写入正式事实表。

## 高清图逐页校准

以下小节按 `docs/ui-reference/highres/` 与 `GAP_MATRIX.md` 对齐。01-15 为当前已存在高清图，16-21 为矩阵保留的待补高清图槽位；读者按任一小节应能还原首屏 wireframe、组件组合、数据源边界和空态。

### 01 系统总览主视图

- 首屏布局：`224px` 固定侧栏 + `64px` 顶栏 + 内容区 `7:3`；主区为 `6 KPI + 2x2 图表网格`，右栏为 AI 建议与异常队列。
- 组件清单：`xt-layout/ManageShell`、`xt-layout/XtPageHeader`、`xt-data/XtKpi`、`xt-data/XtTable`、`xt-chart/XtFactoryMap`、`xt-chart/WorkshopOutputRanking`、`xt-chart/PendingAssignmentHeatmap`、`xt-chart/ReconciliationWaterfall`、`xt-form/XtFilter`、`xt-data/XtStatus`。
- 数据源：`GET /factory-command/overview`、`GET /factory-command/workshops`、`GET /factory-command/machine-lines`、`GET /dashboard/delivery-status`、`GET /aggregation/live/pending-assignment`。
- 空态文案：`暂无今日生产快照，请先确认填报端或外部生产系统同步状态`。
- 响应式断点：桌面 `1440+` 保持 `7:3` 双栏；平板 `1024+` 改为 `1fr` 主区 + 右栏下沉；移动 `375+` 只保留 KPI、异常队列和 AI 建议折叠块。
- 性能预算：首屏 KPI API 调用上限 `3` 个；首屏图表按需加载；页面 chunk gzip `<= 80 KB`。

### 02 登录与角色入口

- 首屏布局：内容区 `5:4`；左侧工厂流程预览 `56%`，右侧登录卡 `44%`；环境状态行固定在登录卡底部。
- 组件清单：`xt-layout/PublicShell`、`xt-data/XtLogo`、`xt-chart/XtFactoryMap`、`xt-data/XtStatus`、`xt-form/ElForm`、`xt-form/ElInput`、`xt-form/ElButton`、`xt-data/ParticleField`。
- 数据源：`POST /auth/login`、`POST /dingtalk/login`、`POST /auth/qr-login`、`GET /auth/me`、`GET /dashboard/external-readiness`。
- 空态文案：`服务状态暂不可用，请使用账号密码登录后查看`。
- 响应式断点：桌面 `1440+` 保持 `5:4`；平板 `1024+` 登录卡居右、流程预览降到 `40%`；移动 `375+` 单列，仅显示品牌、表单、角色入口和状态行。
- 性能预算：登录首屏 API 调用上限 `2` 个；粒子背景不阻塞表单；页面 chunk gzip `<= 80 KB`。

### 03 独立填报端首页

- 首屏布局：移动 `390 x 844` 单列；顶部身份区 `128px`，主操作 `2x2` 网格，底部为待办列表与最近提交。
- 组件清单：`xt-layout/EntryShell`、`xt-data/ReferenceKpiTile`、`xt-data/XtStatus`、`xt-form/EntryToolsPanel`、`xt-form/MobileSwipeWorkspace`、`xt-form/ElButton`。
- 数据源：`GET /mobile/bootstrap`、`GET /mobile/current-shift`、`GET /mobile/reminders`、`GET /mobile/report/history`。
- 空态文案：`当前班次暂无待填任务`。
- 响应式断点：桌面 `1440+` 只用于预览壳 `390px` 居中；平板 `1024+` 保持移动壳并增加右侧审阅预览 `3:2`；移动 `375+` 单列，触控目标 `>=44px`。
- 性能预算：首屏 KPI API 调用上限 `3` 个；离线草稿从本地缓存读取；页面 chunk gzip `<= 80 KB`。

### 04 填报流程页

- 首屏布局：移动单列；随行卡锁定区 `112px` + 表单分组纵向堆叠；底部固定操作条 `64px`。
- 组件清单：`xt-layout/EntryShell`、`xt-form/EntryFieldInput`、`xt-form/XtFieldGroup`、`xt-form/ElInputNumber`、`xt-form/ElUpload`、`xt-data/XtStatus`、`xt-form/ElButton`。
- 数据源：`GET /mobile/scan-lookup`、`GET /mobile/entry-fields`、`GET /mobile/coil-list/{business_date}/{shift_id}`、`POST /mobile/coil-entry`、`POST /mobile/report/upload-photo`。
- 空态文案：`扫码后带出卷号、合金、规格和机列`。
- 响应式断点：桌面 `1440+` 预览壳 `390px` + 审核证据栏 `1fr`；平板 `1024+` 表单与证据栏 `6:4`；移动 `375+` 单列并固定提交按钮。
- 性能预算：首屏 KPI API 调用上限 `3` 个；扫码 lookup 超时 `3s`；页面 chunk gzip `<= 80 KB`。

### 05 工厂作业看板

- 首屏布局：固定侧栏 + 顶部筛选；内容区 `7:3`，左侧机列卡与绑定表，右侧新鲜度、异常和外部线索。
- 组件清单：`xt-layout/ManageShell`、`xt-layout/FactoryCommandShell`、`xt-data/XtKpi`、`xt-data/XtTable`、`xt-chart/WorkshopOutputRanking`、`xt-chart/PendingAssignmentHeatmap`、`xt-chart/ReconciliationWaterfall`、`xt-form/XtFilter`、`xt-data/XtStatus`。
- 数据源：`GET /factory-command/overview`、`GET /factory-command/machine-lines`、`GET /factory-command/coils`、`GET /mes/sync-status`、`GET /aggregation/live/pending-assignment`。
- 空态文案：`暂无机列绑定数据，请检查填报端提交或外部生产系统同步`。
- 响应式断点：桌面 `1440+` 使用 `7:3`；平板 `1024+` 机列卡改 `2` 列；移动 `375+` 仅保留筛选、机列摘要和异常列表。
- 性能预算：首屏 KPI API 调用上限 `3` 个；ECharts 首屏实例 `<=3` 个；页面 chunk gzip `<= 80 KB`。

### 06 数据接入与字段映射中心

- 首屏布局：来源泳道 `20%` + 字段映射表 `55%` + 批次抽屉 `25%`；底部导入历史横跨主区。
- 组件清单：`xt-layout/ManageShell`、`xt-data/XtKpi`、`xt-data/XtTable`、`xt-data/XtStatus`、`xt-form/XtFilter`、`xt-form/ElUpload`、`xt-data/SourceBadge`。
- 数据源：`GET /imports/history`、`GET /imports/daily-production/mapping-preview`、`POST /imports/upload`、`GET /mes/sync-status`、`GET /mes/sync-runs`。
- 空态文案：`暂无导入批次，请上传日报文件或查看外部生产系统同步`。
- 响应式断点：桌面 `1440+` 保持 `20:55:25`；平板 `1024+` 右侧批次抽屉下沉；移动 `375+` 来源泳道改横向滚动，表格保留 4 个核心列。
- 性能预算：首屏 KPI API 调用上限 `3` 个；表格首屏渲染 `<=80` 行；页面 chunk gzip `<= 80 KB`。

### 07 审阅中心

- 首屏布局：KPI 条 `4` 项 + 审阅队列表 `70%` + 证据抽屉 `30%`；风险筛选固定在表头。
- 组件清单：`xt-layout/ManageShell`、`xt-data/ReferenceKpiTile`、`xt-data/ReferenceDataTable`、`xt-data/ReferenceStatusTag`、`xt-data/XtExecutionRail`、`xt-form/XtFilter`、`xt-data/XtStatus`。
- 数据源：`GET /dashboard/factory-director`、`GET /production/shift-data`、`GET /production/exceptions`、`GET /reconciliation/items`、`POST /production/shift-data/{shift_data_id}/review`。
- 空态文案：`当前没有待审阅任务`。
- 响应式断点：桌面 `1440+` 表格 + 抽屉 `7:3`；平板 `1024+` 抽屉变右侧覆盖层；移动 `375+` 队列卡片化并隐藏批量操作。
- 性能预算：首屏 KPI API 调用上限 `3` 个；证据抽屉懒加载；页面 chunk gzip `<= 80 KB`。

### 08 日报与交付中心

- 首屏布局：KPI `6` 项横排 + 报表列表 `60%` + 交付清单 `40%`；阻塞项固定在右栏顶部。
- 组件清单：`xt-layout/ManageShell`、`xt-data/ReferenceDataTable`、`xt-data/ReferenceStatusTag`、`xt-data/XtKpi`、`xt-chart/ShiftOutputTrend`、`xt-form/XtFilter`、`xt-data/XtExport`。
- 数据源：`GET /reports`、`POST /reports/generate`、`POST /reports/run-daily-pipeline`、`GET /reports/{report_id}/export`、`GET /dashboard/delivery-status`。
- 空态文案：`暂无可交付日报，请先生成或运行日报流水线`。
- 响应式断点：桌面 `1440+` 使用 `60:40`；平板 `1024+` 交付清单下沉；移动 `375+` 只显示状态、阻塞项和导出入口。
- 性能预算：首屏 KPI API 调用上限 `3` 个；报表预览不进入首屏 chunk；页面 chunk gzip `<= 80 KB`。

### 09 质量与告警中心

- 首屏布局：质量 KPI `4` 项 + 告警表 `65%` + AI 分诊与处置时间线 `35%`；异常地图占第二行。
- 组件清单：`xt-layout/ManageShell`、`xt-data/ReferenceDataTable`、`xt-data/ReferenceStatusTag`、`xt-data/XtKpi`、`xt-chart/ParetoChart`、`xt-chart/AnomalyTrend`、`xt-form/XtFilter`、`xt-data/XtStatus`。
- 数据源：`GET /quality/issues`、`POST /quality/run-checks`、`POST /quality/issues/{issue_id}/resolve`、`POST /quality/issues/{issue_id}/ignore`、`GET /reconciliation/items`。
- 空态文案：`当前没有质量告警`。
- 响应式断点：桌面 `1440+` 使用 `65:35`；平板 `1024+` AI 分诊下沉；移动 `375+` 告警表改为卡片列表并保留严重度筛选。
- 性能预算：首屏 KPI API 调用上限 `3` 个；告警图表首屏 `<=2` 个；页面 chunk gzip `<= 80 KB`。

### 10 成本核算与效益中心

- 首屏布局：车间 tab + KPI `5` 项 + 趋势图 `7:3`；右栏为口径缺口、风险和 AI 解释。
- 组件清单：`xt-layout/ManageShell`、`xt-layout/FactoryCommandShell`、`xt-data/XtKpi`、`xt-chart/CostStackedBar`、`xt-chart/EnergyPerTonLine`、`xt-data/XtTable`、`xt-form/XtFilter`、`xt-data/XtAiActionCard`。
- 数据源：`GET /factory-command/cost-benefit`、`GET /energy/summary`、`GET /executive/dashboard`、`GET /executive/machine-ranking`、`POST /ai/assistant/ask`。
- 空态文案：`成本口径缺少能耗、天然气或辅材输入`。
- 响应式断点：桌面 `1440+` 使用 `7:3`；平板 `1024+` 图表单列；移动 `375+` 仅显示 KPI、口径缺口和风险表。
- 性能预算：首屏 KPI API 调用上限 `3` 个；成本图表异步加载；页面 chunk gzip `<= 80 KB`。

### 11 AI 助手

- 首屏布局：会话列表 `280px` + 对话主区 `1fr` + briefing/watchlist 右栏 `360px`；工具调用时间线嵌在主区上方。
- 组件清单：`xt-layout/ManageShell`、`xt-data/AiConversationList`、`xt-data/AiChatMessage`、`xt-data/AiBriefingInbox`、`xt-data/AiWatchlistPanel`、`xt-data/XtAiThinking`、`xt-data/XtAiActionCard`。
- 数据源：`GET /ai/assistant/conversations`、`POST /ai/assistant/conversations`、`GET /ai/assistant/conversations/{conversation_id}/messages`、`POST /ai/assistant/conversations/{conversation_id}/messages`、`GET /ai/briefings`、`GET /ai/watchlist`。
- 空态文案：`选择一个生产、质量、成本或交付主题开始追问`。
- 响应式断点：桌面 `1440+` 使用 `280px/1fr/360px`；平板 `1024+` 会话列表收为左抽屉；移动 `375+` 单列对话，briefing 与 watchlist 变 tabs。
- 性能预算：首屏 KPI API 调用上限 `3` 个；消息流首屏 `<=30` 条；页面 chunk gzip `<= 80 KB`。

### 12 系统运维与可观测

- 首屏布局：健康 KPI `4` 项 + 服务矩阵 `60%` + 事件时间线 `40%`；版本与 readyz 固定在页头右侧。
- 组件清单：`xt-layout/ManageShell`、`xt-data/XtKpi`、`xt-data/XtTable`、`xt-data/XtStatus`、`xt-chart/LatencyTrend`、`xt-chart/ErrorRateTrend`、`xt-form/XtFilter`、`xt-data/XtExecutionRail`。
- 数据源：`GET /dashboard/external-readiness`、`GET /mes/sync-status`、`GET /mes/sync-runs`、`GET /assistant/live-probe`、`GET /aggregation/live/active-date`。
- 空态文案：`暂无服务探针结果，请刷新只读健康检查`。
- 响应式断点：桌面 `1440+` 使用 `60:40`；平板 `1024+` 服务矩阵改 `2` 列；移动 `375+` 只显示服务状态、失败作业和版本。
- 性能预算：首屏 KPI API 调用上限 `3` 个；探针轮询间隔 `>=30s`；页面 chunk gzip `<= 80 KB`。

### 13 权限与治理中心

- 首屏布局：权限 KPI `4` 项 + 角色矩阵 `60%` + 审计日志 `40%`；数据边界表在第二行。
- 组件清单：`xt-layout/ManageShell`、`xt-data/XtKpi`、`xt-data/XtTable`、`xt-data/XtStatus`、`xt-form/XtFilter`、`xt-data/ReferenceStatusTag`、`xt-data/XtExecutionRail`。
- 数据源：`GET /auth/me`、`GET /master/workshops`、`GET /master/teams`、`GET /master/employees`、`GET /master/equipment`、`GET /dashboard/external-readiness`。
- 空态文案：`暂无权限矩阵数据，请确认当前账号具备治理查看权限`。
- 响应式断点：桌面 `1440+` 使用 `60:40`；平板 `1024+` 审计日志下沉；移动 `375+` 角色矩阵改为按角色分组列表。
- 性能预算：首屏 KPI API 调用上限 `3` 个；权限矩阵首屏列数 `<=8`；页面 chunk gzip `<= 80 KB`。

### 14 主数据与模板中心

- 首屏布局：tab 栏 + 主数据卡片网格 `4` 列 + 配置表；详情抽屉占右侧 `360px`。
- 组件清单：`xt-layout/ManageShell`、`xt-data/XtWorkshopGlyph`、`xt-data/ReferenceDataTable`、`xt-data/ReferenceStatusTag`、`xt-data/XtKpi`、`xt-form/XtFilter`、`xt-form/XtFieldGroup`。
- 数据源：`GET /master/workshops`、`GET /master/teams`、`GET /master/employees`、`GET /master/equipment`、`GET /master/workshop-templates/{template_key}`、`GET /rule-configs`。
- 空态文案：`暂无主数据记录，请先配置车间、班组或机台`。
- 响应式断点：桌面 `1440+` 卡片 `4` 列；平板 `1024+` 卡片 `2` 列；移动 `375+` tab 横向滚动、表格改摘要卡。
- 性能预算：首屏 KPI API 调用上限 `3` 个；主数据列表分页 `limit<=50`；页面 chunk gzip `<= 80 KB`。

### 15 响应式录入体验

- 首屏布局：桌面预览为 `390px` 手机壳 + 右侧审阅预览 `1fr`；移动为单列录入工作台；底部导航固定 `56px`。
- 组件清单：`xt-layout/EntryShell`、`xt-form/MobileSwipeWorkspace`、`xt-form/EntryToolsPanel`、`xt-form/EntryFieldInput`、`xt-data/XtStatus`、`xt-form/ElButton`。
- 数据源：`GET /mobile/bootstrap`、`GET /mobile/current-shift`、`GET /mobile/entry-fields`、`GET /mobile/report/history`、`POST /mobile/report/save`、`POST /mobile/report/submit`。
- 空态文案：`暂无草稿或历史记录`。
- 响应式断点：桌面 `1440+` 使用 `390px/1fr`；平板 `1024+` 手机壳居中并显示历史栏；移动 `375+` 单列，底部导航和提交按钮不重叠。
- 性能预算：首屏 KPI API 调用上限 `3` 个；草稿保存防抖 `800ms`；页面 chunk gzip `<= 80 KB`。

### 16 库存与出入库中心

- 首屏布局：流向表 `65%` + 库存结构与待去向队列 `35%`；卷级详情抽屉 `420px`。
- 组件清单：`xt-layout/ManageShell`、`xt-layout/FactoryCommandShell`、`xt-data/XtKpi`、`xt-data/XtTable`、`xt-chart/InventoryAgingBuckets`、`xt-chart/OutboundTrend`、`xt-form/XtFilter`、`xt-data/XtStatus`。
- 数据源：`GET /factory-command/destinations`、`GET /factory-command/coils`、`GET /factory-command/coils/{coil_key}/flow`、`GET /aggregation/live/detail`。
- 空态文案：`暂无库存去向记录，请先同步卷级流转或填报去向`。
- 响应式断点：桌面 `1440+` 使用 `65:35`；平板 `1024+` 右栏下沉；移动 `375+` 只保留卷级流向列表和待去向队列。
- 性能预算：首屏 KPI API 调用上限 `3` 个；卷级详情懒加载；页面 chunk gzip `<= 80 KB`。

### 17 合同与订单中心

- 首屏布局：订单 KPI `5` 项 + 合同列表 `60%` + 交付日历 `40%`；生产匹配抽屉 `420px`。
- 组件清单：`xt-layout/ManageShell`、`xt-data/XtKpi`、`xt-data/XtTable`、`xt-chart/DeliveryCalendar`、`xt-chart/FulfillmentTrend`、`xt-form/XtFilter`、`xt-data/XtStatus`。
- 数据源：`TODO GET /contracts/orders`、`TODO GET /contracts/import-batches`、`GET /dashboard/delivery-status`、`GET /factory-command/coils`。
- 空态文案：`暂无合同订单数据，请先完成合同表 dry-run 导入`。
- 响应式断点：桌面 `1440+` 使用 `60:40`；平板 `1024+` 日历下沉；移动 `375+` 合同列表卡片化，仅保留交付风险。
- 性能预算：首屏 KPI API 调用上限 `3` 个；订单列表分页 `limit<=50`；页面 chunk gzip `<= 80 KB`。

### 18 能源中心

- 首屏布局：能源 KPI `5` 项 + 能耗趋势 `7:3`；右栏为电耗、天然气和缺口校验。
- 组件清单：`xt-layout/ManageShell`、`xt-data/XtKpi`、`xt-data/XtTable`、`xt-chart/EnergyPerTonLine`、`xt-chart/EnergyWorkshopStack`、`xt-form/XtFilter`、`xt-data/XtStatus`。
- 数据源：`GET /energy/summary`、`POST /energy/import`、`GET /factory-command/cost-benefit`、`GET /imports/history`。
- 空态文案：`暂无能源数据，请导入电耗或天然气报表`。
- 响应式断点：桌面 `1440+` 使用 `7:3`；平板 `1024+` 趋势图单列；移动 `375+` 只显示 KPI、缺口和导入批次。
- 性能预算：首屏 KPI API 调用上限 `3` 个；趋势图点数首屏 `<=90`；页面 chunk gzip `<= 80 KB`。

### 19 班长一屏

- 首屏布局：班组进度 `55%` + 人员/机台状态 `45%`；异常确认固定在首屏底部。
- 组件清单：`xt-layout/TeamLeadShell`、`xt-data/XtKpi`、`xt-data/XtTable`、`xt-data/XtStatus`、`xt-form/XtFilter`、`xt-form/ElButton`。
- 数据源：`GET /team-lead/overview`、`GET /team-lead/workers`、`GET /attendance/draft`、`POST /attendance/confirm`。
- 空态文案：`当前班组暂无待确认事项`。
- 响应式断点：桌面 `1440+` 使用 `55:45`；平板 `1024+` 人员状态下沉；移动 `375+` 单列并固定确认按钮。
- 性能预算：首屏 KPI API 调用上限 `3` 个；人员列表分页 `limit<=60`；页面 chunk gzip `<= 80 KB`。

### 20 统计中心

- 首屏布局：统计 KPI `6` 项 + 多维趋势 `70%` + 筛选/口径栏 `30%`；导出操作放右上。
- 组件清单：`xt-layout/ManageShell`、`xt-data/XtKpi`、`xt-data/XtTable`、`xt-chart/ShiftOutputTrend`、`xt-chart/WorkshopScrapRate`、`xt-form/XtFilter`、`xt-data/XtExport`。
- 数据源：`GET /dashboard/statistics`、`GET /dashboard/factory-director`、`GET /production/shift-data`、`POST /export/{module}`。
- 空态文案：`暂无统计数据，请选择已有填报日期或同步生产数据`。
- 响应式断点：桌面 `1440+` 使用 `70:30`；平板 `1024+` 筛选栏置顶；移动 `375+` 统计卡片化并隐藏多维表。
- 性能预算：首屏 KPI API 调用上限 `3` 个；图表首屏实例 `<=3` 个；页面 chunk gzip `<= 80 KB`。

### 21 文件导入中心

- 首屏布局：上传区 `30%` + 批次历史 `70%`；映射预览抽屉 `420px`。
- 组件清单：`xt-layout/ManageShell`、`xt-form/ElUpload`、`xt-data/XtTable`、`xt-data/XtStatus`、`xt-data/SourceBadge`、`xt-form/XtFilter`。
- 数据源：`POST /imports/upload`、`GET /imports/history`、`GET /imports/history/{batch_id}`、`GET /imports/daily-production/mapping-preview`。
- 空态文案：`暂无导入历史，请上传 Excel 或 CSV 文件进行 dry-run`。
- 响应式断点：桌面 `1440+` 使用 `30:70`；平板 `1024+` 上传区置顶；移动 `375+` 只保留上传按钮、批次状态和错误摘要。
- 性能预算：首屏 KPI API 调用上限 `3` 个；上传组件独立 chunk；页面 chunk gzip `<= 80 KB`。
