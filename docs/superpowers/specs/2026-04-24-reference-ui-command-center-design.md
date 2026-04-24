# 参考图级生产指挥中心设计规格

## Goal

把 aluminum-bypass 从当前“可用但视觉松散”的状态，升级为参考图级的浅色高密生产指挥中心。目标不是单纯换皮，而是同步重排功能、页面颗粒度、三端边界、响应式规则、UI 图形语言、前端构建规则和后端数据适配规则。

参考图的核心特征：

- 16 个编号中心模块，蓝色编号醒目。
- 浅蓝灰背景、白底卡片、细边框、轻阴影。
- 高密 KPI、紧凑表格、迷你趋势图、环形/柱状图。
- 页面信息密度高但分区规整，不出现大段解释性文案。
- 登录、录入、审阅、日报、成本、AI、运维、治理、主数据、路线图都在同一功能与视觉系统下。
- 整体要有高科技感，但不是黑底炫技；科技感来自数据流、状态流、图形化模块、精确排版和可解释交互。

本轮明确取消“移动端预览”作为独立展示模块。移动能力通过真实录入端和全局响应式实现，不再做单独的手机壳预览中心。

## Three Surface Model

### Entry Terminal

录入端只负责录入。

路径范围：

- `/entry`
- `/entry/report/:businessDate/:shiftId`
- `/entry/advanced/:businessDate/:shiftId`
- `/entry/ocr/:businessDate/:shiftId`
- `/entry/attendance`
- `/entry/history`
- `/entry/drafts`

允许能力：

- 今日班次。
- 待填报任务。
- 快速填报。
- 高级填报。
- OCR 录入。
- 草稿箱。
- 历史记录。
- 异常补录。
- 提交结果反馈。
- 录入端智能提示。

禁止能力：

- 厂级看板。
- 车间看板。
- 审阅任务。
- 成本中心。
- AI 总大脑工作台。
- 运维中心。
- 权限治理。
- 主数据配置。

壳层：

- 使用 `EntryShell`。
- 不复用审阅端侧栏。
- 移动优先，大按钮、大输入区、步骤化表单。
- 桌面访问时仍显示录入端布局，不夹带管理能力。

### Review Command

审阅端只负责看数、审阅、处置和交付。

路径范围：

- `/review/overview`
- `/review/factory`
- `/review/workshop`
- `/review/tasks`
- `/review/reports`
- `/review/quality`
- `/review/reconciliation`
- `/review/cost-accounting`
- `/review/brain`
- `/review/roadmap`

允许能力：

- 系统总览。
- 厂级/车间看板。
- 待审、已审、驳回。
- 日报与交付。
- 质量告警与处置。
- 差异治理。
- 成本核算与效益解释。
- AI 生产摘要、风险摘要、审阅建议、成本解释。
- 路线图业务视角。

禁止能力：

- 用户管理。
- 角色权限配置。
- 主数据维护。
- 模板字段配置。
- 系统发布回滚配置。

壳层：

- 新建或重构为 `ReviewShell`，从现有 `ReviewLayout + AppShell` 演进。
- 视觉贴近参考图：浅色工作区、编号模块、紧凑表格、高密 KPI。
- 不再在审阅导航中出现“移动填报”和管理配置入口。

### Admin Console

管理端只负责配置、治理、主数据和运维。

路径范围：

- `/admin`
- `/admin/ingestion`
- `/admin/field-mapping`
- `/admin/ops`
- `/admin/governance`
- `/admin/master`
- `/admin/templates`
- `/admin/users`
- `/admin/roadmap`

允许能力：

- 数据接入与字段映射。
- 导入历史与接入质量。
- 系统运维与可观测。
- AI live probe 与调用状态。
- 权限治理、角色矩阵、审计日志。
- 车间、班组、员工、机台、用户、班次、别名。
- 模板字段配置。
- 路线图管理视角。

禁止能力：

- 现场填报。
- 日常审阅任务处理。
- 填报表单提交。

壳层：

- 新建 `AdminShell`。
- 使用同一视觉基线，但导航、标题和操作聚焦配置治理。
- 可以从 super admin 顶栏切换到审阅端或录入端，但切换后进入对应端壳层。

## Route And Permission Plan

### Surface Policy

把当前散落的 `canAccessFillSurface / canAccessReviewSurface / canAccessDesktopConfig` 升级为显式 surface policy。

建议前端 store 暴露：

- `entrySurface`
- `reviewSurface`
- `adminSurface`
- `superAdminSurface`
- `defaultSurface`

规则：

- fill-only 用户登录后只能进入 `/entry`。
- fill-only 用户访问 `/review/*`、`/admin/*`、`/command` 中非录入模块时，回跳 `/entry`。
- review 用户默认进入 `/review/overview`。
- admin 用户默认进入 `/admin` 或 `/command` 管理模块。
- super admin 可以切换三端，但每个端仍使用独立 shell。

### Compatibility

必须保留兼容层：

- `/mobile/*` redirect 到 `/entry/*`。
- 旧 `/dashboard/*` redirect 到 `/review/*`。
- 旧 `/master/*` redirect 或兼容到 `/admin/*`。
- 现有 route name 必须保留兼容，新增 alias 或 redirect，不直接删除。
- 任何路由重整不得破坏现有 `router.push({ name })`、E2E、移动二维码入口和上线闸门。
- 旧 URL 可降权，但必须可达或可预测跳转。

## Reference Module Mapping

参考图 16 模块映射如下。

1. 系统总览主视图：`/review/overview`
2. 登录与角色入口：`/login`
3. 独立填报终端首页：`/entry`
4. 填报流程页：`/entry/report/*` 与 `/entry/advanced/*`
5. 工厂作业看板：`/review/factory`
6. 数据接入与字段映射中心：`/admin/ingestion`
7. 审阅中心：`/review/tasks`
8. 日报与交付中心：`/review/reports`
9. 质量与告警中心：`/review/quality`
10. 成本核算与效益中心：`/review/cost-accounting`
11. AI 总大脑中心：`/review/brain`
12. 系统运维与可观测：`/admin/ops`
13. 权限治理中心：`/admin/governance`
14. 主数据与模板中心：`/admin/master`
15. 响应式录入体验：不做独立手机预览模块，作为全局响应式验收项覆盖 `/entry` 全链路
16. 路线图与下一步：`/review/roadmap` 与 `/admin/roadmap`

## Visual System

### Layout

- 全局背景使用极浅蓝灰。
- 页面外框采用 12 列或 16 模块网格。
- 每个中心页标题左侧显示蓝色编号。
- 标题只使用中文，不使用英文小字副标题。
- 编号 + 中文主标题 + 必要业务标签构成标题区，例如 `01 系统总览主视图`、`07 审阅中心`。
- 首页总览可采用 16 宫格缩略地图，点击进入中心页面。

### Cards

- 白底。
- 1px 蓝灰边框。
- 12-16px 圆角，避免过大圆角。
- 轻阴影，不使用厚重玻璃拟态。
- 卡片内信息采用标题、KPI、表格、趋势图组合。

### KPI

- 小图标圆片。
- 大数字。
- 单位小字。
- 绿色/红色趋势。
- 状态色只用于信息表达，不做装饰滥用。

### Tables

- 紧凑行高。
- 浅蓝灰表头。
- 状态 tag 小而清楚。
- 表格优先承载真实业务字段，不塞解释文案。

### Graphics

允许新增 UI 图形，但必须服务业务理解：

- 抽象产线示意图。
- 工序流向连接线。
- 环形完成率。
- 迷你折线趋势。
- 成本堆叠柱。
- 风险 Top list。
- 系统时间线。

### Motion

允许复杂动画，但必须克制且可降级：

- 页面模块 stagger 入场。
- KPI 数字轻量滚动。
- 产线流向线缓慢流动。
- 异常点轻脉冲。
- AI 卡片结果出现动画。

禁止：

- 大面积持续闪烁。
- 干扰表单输入的动画。
- 移动端强动画。
- 影响性能的 canvas 背景常驻动画。

## Frontend Construction Rules

前端实现必须按参考图的页面组织方式构建，而不是在旧页面上零散加样式。

### Component System

新增或强化以下组件层：

- `ReferencePageFrame`：中心页统一外框，负责编号标题、顶部工具区、主网格。
- `ReferenceModuleCard`：参考图式白底细边框模块卡。
- `ReferenceKpiTile`：图标圆片、大数字、单位、趋势。
- `ReferenceStatusTag`：统一红/绿/蓝/橙状态标签。
- `ReferenceDataTable`：紧凑表格，统一表头、行高、状态列。
- `ReferenceMiniTrend`：迷你折线、环形进度、堆叠柱图的轻量封装。
- `ReferenceFlowGraphic`：产线示意、流程连接线、数据流动线。

组件不使用 `description / explanation / helperText / tooltip / note / rationale` 作为 props 名，避免和项目现有前端规则冲突。说明性内容必须变成业务字段、状态标签或操作入口。

### Page Construction

每个页面必须按参考图结构实现：

- 顶部编号标题区。
- KPI 摘要区。
- 主表格或主图形区。
- 右侧或底部摘要/风险/趋势区。
- 操作区固定在表格上方或卡片底部，不散落。

页面不得只放静态卡片。每个中心页至少要接入一个真实数据来源、一个状态判断和一个可执行动作或跳转。

### Copy And Field Cleanup

- 清理旧前端残余设计中的解释性长文案、软萌文案、演示稿文案和重复提示。
- 必要说明必须转化为清晰字段、状态标签、步骤标题、操作按钮或数据缺口提示。
- 不允许页面出现大段解释文本来撑版面。
- 字段命名和展示顺序要贴近参考图：先 KPI，再表格/图形，再操作。
- 所有空态、错态、加载态都要贴近参考图的卡片密度，不出现孤立大块空白。

### Visual Fidelity Rules

- 所有中心页面编号必须与映射表一致。
- 白底卡片边框、圆角、内距、表格行高必须由 token 控制。
- 图标统一使用蓝色线性/圆片风格，不能混用大色块插画。
- 装饰图必须是业务图形：产线、数据流、工序流、设备轮廓、状态雷达，不放无意义背景纹理。
- 动画必须服务数据状态：入场、流转、异常、刷新、AI 生成结果。
- 全站保留高科技感：蓝色数据线、微弱流光、状态脉冲、精确网格、数字化图形。

### Responsive Build Rules

- 桌面优先复刻参考图密度。
- 平板改为 2-3 列模块卡。
- 手机端进入端内专属布局，优先保证录入端可用。
- 审阅端和管理端手机布局只保留摘要、Top 风险和关键动作。
- 不再做“移动端预览”展示模块，真实响应式页面就是移动验收对象。

### Visual Verification

视觉审计脚本需要升级：

- 覆盖 `/login`、`/entry`、`/review/overview`、`/review/tasks`、`/review/cost-accounting`、`/admin`、`/admin/ops`。
- 检查编号标题存在。
- 检查核心卡片数量。
- 检查表格/图形区域可见。
- 检查 fill-only 无法看到 review/admin 导航。
- 输出截图和 JSON 报告。
- 新增人工/脚本双轨参考图颗粒度对照清单：模块编号、标题、卡片比例、KPI 密度、表格密度、图形位置、操作区位置、状态色使用。
- 每轮视觉改动后都要与目标图逐项对比；低于既定贴合度时继续迭代，不以“功能可用”替代“视觉达标”。
- 不同 Web 页面宽度下只能重排，不能改变核心视觉语言；桌面、平板、手机都必须保持编号、卡片、KPI、状态标签风格一致。

## Functional Fit Rules

功能设计也必须贴合参考图，而不是只视觉接近。

### Login And Role Handoff

- 登录页保留三角色入口：录入端、审阅端、管理端。
- 三角色入口不是装饰卡，必须影响登录后默认落点和可见端。
- 登录后根据 surface policy 进入对应端。
- super admin 可切换端，但切换后进入对应端壳层。

### Entry Terminal

- 参考图 03/04 的逻辑必须真实落地。
- 首页展示今日班次、待填任务、已提交、异常补卡、最近状态、快捷操作。
- 填报页展示步骤条、当前步骤表单、本步要点、AI 提示。
- 录入端不出现任何审阅/管理数据入口。

### Review Command

- 参考图 01/05/07/08/09/10/11/16 的业务审阅逻辑必须真实落地。
- 审阅中心必须是任务表，不是按钮页。
- 每条审阅任务包含来源、班次、异常类型、风险等级、AI 建议、操作。
- 日报交付必须有交付状态、导出、发送或交付动作。
- 成本中心必须保留策略引擎、成本拆解、价格快照和校差记录。
- AI 总大脑必须贯穿总览、审阅、成本、接入、运维。

### Admin Console

- 参考图 06/12/13/14 的管理逻辑必须真实落地。
- 数据接入中心展示数据源状态、字段映射、导入历史、成功率/错误率。
- 运维中心展示健康、ready、AI probe、版本、错误率、响应时间。
- 权限治理展示角色矩阵、审计日志、数据权限。
- 主数据模板展示车间、班组、员工、机台、用户、班次、别名、模板入口。

## API And View Model Plan

保留现有 `/api/v1/*` 核心接口，新增 command/admin 聚合接口，降低前端页面拼接口复杂度。

建议新增：

- `GET /api/v1/command/overview`
- `GET /api/v1/command/review-center`
- `GET /api/v1/command/entry-terminal`
- `GET /api/v1/command/cost-center`
- `GET /api/v1/admin/ops-overview`
- `GET /api/v1/admin/governance-overview`
- `GET /api/v1/admin/master-overview`

第一轮可用前端 adapter mock 兼容，第二轮补后端聚合。

## Backend Adaptation Rules

后端改进必须服务参考图的功能结构，输出页面友好的 view model，而不是让前端继续到处拼装。

### Aggregation Contracts

新增聚合接口要按页面模块组织：

- 每个聚合接口返回 `module_id`、`title`、`kpis`、`status_summary`、`primary_rows`、`trend_series`、`actions`。
- KPI 必须带 `label`、`value`、`unit`、`trend`、`status`、`icon_key`。
- 表格行必须带稳定 `id`、`source_label`、`status_label`、`status_variant`。
- 图表数据必须后端预聚合到页面可直接渲染的粒度。
- 所有聚合接口必须带 `freshness` 或 `updated_at`，让页面显示数据时效。

### Surface-Aware Responses

接口需适配三端：

- entry surface 只返回填报任务和录入辅助信息。
- review surface 返回审阅、风险、交付、成本、AI 摘要。
- admin surface 返回配置、治理、运维、主数据。
- 同一用户拥有多端权限时，仍按当前访问 surface 裁剪响应。

### Permission And Route Adaptation

- 后端权限模型需要承认 `entry / review / admin` 三类 surface。
- 新接口必须按 surface 校验，不只按 role 粗放判断。
- 旧接口保留，新增接口优先服务新页面。
- 对旧路由兼容期内的数据写入，不改变现有核心业务表含义。

### High-Tech Data Support

为高科技感 UI 提供数据基础：

- 产线图需要节点、连接线、状态和当前流转阶段。
- 风险脉冲需要风险等级、风险原因和处置状态。
- KPI 数字动画需要上一值、当前值和趋势方向。
- 成本图需要分项、占比、趋势和归因。
- AI 卡片需要摘要、建议、证据来源和 mock/live 标记。

### Testing Requirements

- 每个新增聚合接口必须有 schema 测试。
- surface 裁剪必须有权限测试。
- 旧接口兼容必须有回归测试。
- 前端静态契约测试需锁定关键页面编号、三端导航边界和参考图模块映射。

## Responsive Rules

全局响应式替代“移动端预览模块”。

断点：

- `>= 1280px`：参考图高密桌面布局。
- `900-1279px`：两列/三列卡片布局，侧栏可收缩。
- `< 900px`：三端进入移动布局，Entry 端优先；Review/Admin 只保留可读卡片与关键表格。

录入端移动规则：

- 步骤条横向简化。
- 一屏只处理一个任务。
- 表单字段大输入、大按钮。
- 图片/OCR/异常说明靠近提交动作。

审阅端移动规则：

- 只展示摘要、待审 Top、异常 Top。
- 表格转卡片列表。
- 批量操作降级为单项操作。

管理端移动规则：

- 只允许轻量查看和少量开关。
- 大规模配置建议桌面处理。

响应式一致性规则：

- 桌面、平板、手机使用同一 token、同一状态色、同一编号体系。
- 页面宽度变化时允许列数变化、侧栏折叠、表格转卡片，但不允许视觉风格漂移。
- 核心模块顺序在不同宽度下保持稳定，避免用户换设备后找不到功能。
- 参考图的卡片比例在宽屏下优先保真，窄屏下按模块纵向堆叠。

## Implementation Phases

### Phase 1: Surface Separation

- 新建 `AdminShell`。
- Review 导航移除填报和管理项。
- Admin 导航承接运维、治理、主数据、模板、接入。
- 强化 router guard 和 surface policy。
- 补权限边界测试。

### Phase 2: Reference Visual Baseline

- 更新 tokens/theme。
- 统一编号标题、卡片、KPI、状态 tag、紧凑表格。
- 改造 Login、Entry 首页、Review Overview、Admin 首页。
- 建立 reference card components。

### Phase 3: 16 Module Mapping

- `/review/overview` 做 16 模块总览地图。
- 各中心页按参考图模块布局重排。
- 移动端预览模块取消，改为响应式验收清单。

### Phase 4: UI Graphics And Motion

- 产线示意图。
- 流程连接线。
- KPI 数字动效。
- 异常轻脉冲。
- 成本堆叠图。

### Phase 5: Aggregated View Models

- 先前端 adapter。
- 再后端聚合接口。
- 旧接口继续兼容。

### Phase 6: Verification

- `npm --prefix frontend run build`
- `npm --prefix frontend run e2e`
- `python -m pytest backend/tests -q`
- 视觉审计覆盖三端和核心 16 模块。
- go-live gate 仍需通过。

## Acceptance Criteria

- 录入端只负责录入，fill-only 不能进入审阅/管理。
- 审阅端不出现主数据配置和填报入口。
- 管理端不出现现场填报和日常审阅任务处理。
- 参考图 16 模块中除移动端预览外均有清晰映射。
- 移动端能力通过真实响应式录入端覆盖。
- 视觉和功能设计都贴合参考图：浅底、高密、蓝色编号、紧凑卡片、表格/图形并重，且每个模块有真实功能承载。
- UI 高科技感可见：数据流线、状态脉冲、产线图形、数字化 KPI、AI 结果动效。
- UI 不使用英文小字副标题，中心标题统一为编号 + 中文标题。
- 新增前端组件遵守参考图构建规则。
- 后端新增聚合接口遵守 surface-aware view model 规则。
- 旧 URL 和 route name 必须保持兼容。
- 旧前端残余设计被清理：无大段解释文案、无软萌残留、无不一致卡片风格、无不美观大空白。
- 完成后必须反复与目标图做颗粒度对照，覆盖模块编号、卡片比例、KPI、表格、图形、操作区和响应式一致性。
- 页面在不同 Web 宽度下只发生布局重排，不出现视觉语言明显变化。
- 构建、E2E、后端测试、视觉审计、上线闸门通过。
