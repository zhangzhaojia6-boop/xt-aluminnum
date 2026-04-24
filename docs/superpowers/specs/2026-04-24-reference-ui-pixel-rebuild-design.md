# 参考图像素级生产指挥中心大重构设计

## 决策

采用方案 C：前端页面层重建，后端/API/权限/route name 兼容保留。

本设计取代“在旧页面上继续美化”的推进方式。旧前端页面只能作为业务逻辑、接口调用和字段语义参考，不再决定布局、视觉、交互层级或功能颗粒度。目标是把系统重构为参考图级的 16 模块生产指挥中心，而不是把旧页面贴成蓝白色。

## 目标

- 视觉上接近目标图：4x4 模块画布、蓝色编号、浅蓝灰背景、白底细边框卡片、高密 KPI、紧凑表格、业务图形、轻科技感。
- 功能上接近目标图：登录、录入、审阅、日报、质量、成本、AI、运维、治理、主数据、路线图都按 16 模块粒度落地。
- 结构上摆脱旧前端残余：不再让旧页面的大段说明、暖色背景、大圆角、松散卡片、散落按钮决定 UI。
- 工程上保留兼容：旧 URL、route name、权限判断、二维码入口、核心后端接口和 E2E 主链路必须保持可达。
- 验收上可量化：目标图、16 面板映射、截图、JSON 审计、E2E、构建、后端测试全部进入门禁。

## 非目标

- 不重写后端核心业务表。
- 不删除旧接口。
- 不为了视觉复刻牺牲录入端可用性。
- 不引入大型可视化依赖或 canvas 常驻背景。
- 不在本轮做通用低代码平台；模块 schema 只服务本项目 16 个生产协同模块。

## 新前端边界

新增 `frontend/src/reference-command/` 作为目标图级 UI 系统根目录。

建议结构：

```text
frontend/src/reference-command/
  assets/
    logo.js
    industry-graphics.js
  data/
    moduleCatalog.js
    moduleAdapters.js
  components/
    CommandCanvas.vue
    CommandPanel.vue
    CommandPage.vue
    CommandKpi.vue
    CommandTable.vue
    CommandTrend.vue
    CommandFlowMap.vue
    CommandActionBar.vue
    CommandStatus.vue
  shells/
    CommandReviewShell.vue
    CommandAdminShell.vue
    CommandEntryShell.vue
  pages/
    CommandLogin.vue
    CommandOverview.vue
    CommandEntryHome.vue
    CommandEntryFlow.vue
    CommandModulePage.vue
  styles/
    command-tokens.css
    command-layout.css
    command-motion.css
```

旧目录中的页面组件逐步降级：

- `frontend/src/views/review/*`：不再直接决定 UI，可保留为迁移期间的 adapter 来源。
- `frontend/src/views/dashboard/*`：迁移到 `CommandModulePage` 后只保留数据调用或删除。
- `frontend/src/views/master/*`：迁移到 admin module schema 后只保留表单逻辑或删除。
- `frontend/src/styles.css` 和 `frontend/src/design/theme.css`：清理旧暖色 token 和重复 shell 样式，统一转为 command token。

## 视觉系统

### Logo

使用目标图式系统 Logo，而不是当前单个“鑫”大色块。

Logo 规则：

- 左侧使用蓝色圆角编号/工厂抽象 mark。
- 主标题使用中文：`鑫泰铝业生产协同系统`。
- 不使用英文小字副标题。
- 登录页可显示产品代号，但不能变成英文装饰。

### 字体

全站字体栈统一：

```css
font-family:
  "DIN Alternate",
  "Barlow Condensed",
  "MiSans",
  "HarmonyOS Sans SC",
  "Microsoft YaHei",
  sans-serif;
```

规则：

- 数字 KPI 使用更紧凑的数字字体优先级。
- 中文标题使用 14-16px 紧凑层级，不做营销大标题。
- 禁止英文副标题，例如 `(Hero Overview)`、`(Review Center)`。
- 表格字号 12-13px，行高紧凑。

### 背景

背景必须接近目标图的浅蓝灰科技工作台：

- 页面底色：`#f4f7fb`。
- 背景图案：极淡网格、蓝色数据流线、局部设备轮廓。
- 禁止暖米色、橙色大面积渐变、厚重玻璃拟态。
- 背景图案必须服务生产协同语义：产线、工序、数据流、设备轮廓。

### 卡片

统一卡片 token：

- 白底 `#ffffff`。
- 边框 `1px solid #e5edf7`。
- 圆角 10-14px。
- 阴影极轻。
- 内距 10-14px。
- 卡片标题行高度固定，操作区固定。

### 图案

允许并鼓励使用业务图形：

- 抽象产线图。
- 数据流节点连接线。
- 设备线框图。
- 环形完成率。
- 迷你折线。
- 堆叠柱。
- 风险脉冲。

禁止：

- 无意义插画。
- 大色块 icon 混用。
- 随机背景纹理。
- 和生产数据无关的装饰图。

## 16 模块页面语法

每个模块使用同一页面语法：

1. 模块编号标题区。
2. KPI 摘要区。
3. 主表格或主图形区。
4. 右侧摘要/风险/趋势区。
5. 固定操作区。

模块 schema 示例：

```js
{
  moduleId: '07',
  title: '审阅中心',
  surface: 'review',
  routeName: 'review-task-center',
  routePath: '/review/tasks',
  layout: 'table-with-side-risk',
  kpiKeys: ['pending', 'approved', 'rejected'],
  primary: { type: 'table', source: 'reviewTasks' },
  side: { type: 'riskList', source: 'reviewRisks' },
  actions: ['approve', 'reject', 'export']
}
```

`CommandModulePage` 根据 schema 渲染页面。子页只提供数据 adapter 和少量插槽，不再自行写完整布局。

## 三端重构

### 登录入口

重建为目标图 02：

- 三角色入口是真按钮。
- 录入端、审阅端、管理端影响登录后默认落点。
- 登录卡、角色卡、Logo、底部安全信息按目标图排版。
- 删除解释性长文案和英文副标题。

### 录入端

重建为目标图 03/04：

- `CommandEntryShell` 移动优先，但桌面仍保持录入端视觉语言。
- 首页只显示录入相关：今日班次、待填任务、已提交、异常补卡、最近状态、快捷操作。
- 填报页使用步骤条：基础信息、产量录入、能耗/辅项、异常补充、图片上传、提交成功。
- 录入端不出现审阅/管理入口。

### 审阅端

重建为目标图 01/05/07/08/09/10/11/16：

- `/review/overview` 是 4x4 指挥中心画布。
- `/review/factory` 是 05 工厂作业看板。
- `/review/tasks` 是 07 审阅任务表。
- `/review/reports` 是 08 日报交付。
- `/review/quality` 是 09 质量告警。
- `/review/cost-accounting` 是 10 成本核算。
- `/review/brain` 是 11 AI 总大脑。
- `/review/roadmap` 是 16 审阅视角路线图。
- 审阅端导航不出现主数据、模板配置、用户管理。

### 管理端

重建为目标图 06/12/13/14/16：

- `/admin/ingestion` 是 06 数据接入与字段映射。
- `/admin/ops` 是 12 运维与可观测。
- `/admin/governance` 是 13 权限治理。
- `/admin/master` 和 `/admin/templates` 是 14 主数据与模板。
- `/admin/users` 纳入 13 权限治理。
- `/admin/roadmap` 是 16 管理视角路线图。
- 管理端不出现日常审阅任务处理和现场填报业务入口。

## 路由兼容

必须保留：

- `/mobile/*` -> `/entry/*`
- `/dashboard/*` -> `/review/*`
- `/master/*` -> `/admin/*`
- `/ops/reliability` -> `/admin/ops`
- 原 route name 可继续 `router.push({ name })`

新 UI 可以替换 route component，但 route name 不删除。

## 数据流

前端新增 adapter 层：

```text
后端旧接口 / 新聚合接口
  -> moduleAdapters.js
  -> moduleCatalog.js
  -> CommandCanvas / CommandModulePage
```

adapter 负责：

- 把旧接口数据转成 KPI、row、trend、action。
- 把缺失数据转成紧凑缺口状态，不显示大段解释。
- 同一模块在 review/admin 端裁剪不同 action。

优先使用现有接口与已新增聚合接口：

- `/api/v1/command/surface/{surface}`
- `/api/v1/admin/ops-overview`
- `/api/v1/admin/governance-overview`
- `/api/v1/admin/master-overview`
- 现有 dashboard、mobile、reports、quality、templates、users 接口。

## 清理旧前端残余

本轮重构允许删除或退场以下残余：

- 暖色背景与橙色品牌偏置。
- 大圆角厚玻璃卡片。
- 软萌/营销/说明型文案。
- 英文小字副标题。
- 不属于三端职责的导航入口。
- 页面内散落按钮。
- 仅用于撑版面的静态卡片。
- 旧移动端预览模块。

清理原则：

- 先用新页面替换 route component。
- 新页面稳定后删除旧页面 import 和无引用组件。
- 不删除仍被路由或测试依赖的旧 route name。
- 不改业务表含义。

## 测试与验收

### TDD 门禁

每个重构任务先写测试：

- 静态契约测试锁 module schema。
- E2E 锁三端主链路。
- 视觉审计锁目标图颗粒度。
- 后端测试锁聚合接口 schema。

### 视觉审计

`frontend/tmp_visual_audit.cjs` 升级为像素级参考图审计入口：

- 读取目标图 `C:/Users/xt/Downloads/cb3b60f0-1a5d-43e4-94bc-9d4cf4274aa5.png`。
- 校验目标图尺寸 1672x941。
- 对 16 个面板建立 moduleId -> route -> screenshot 映射。
- 检查每页编号、中文标题、卡片密度、KPI 数量、主表/主图、操作区。
- 输出截图和 JSON。
- 记录 `.omx/state/reference-ui-visual-verdict/ralph-progress.json`。

### 功能测试

每轮必须至少运行：

- `python -m pytest backend/tests -q`
- `npm --prefix frontend run build`
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run e2e`
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 node frontend/tmp_visual_audit.cjs`
- `git diff --check`

### 验收标准

- 16 个目标图模块都有新 UI schema 和对应截图。
- `/review/overview` 在 1512px 桌面宽度下呈现近似目标图 4x4 高密指挥中心。
- 登录页三角色入口视觉与功能均贴近目标图。
- 录入端只录入，审阅端只审阅，管理端只管理。
- 所有中心页不使用英文小字副标题。
- 旧 URL 和 route name 兼容。
- 全量 E2E 通过。
- 视觉审计通过且保留报告。

## 风险

- 像素级复刻与现有业务复杂度冲突：以目标图页面语法为准，业务细节折叠进表格/侧栏/动作区。
- 一次性删除旧页面风险高：采用 route component 替换 + adapter 过渡，确认无引用后再删除。
- 数据缺口影响图形完整性：adapter 输出缺口状态，不用长文案撑版面。
- 移动端强行复刻桌面会不可用：桌面像素级靠近，移动端保持同一视觉语言但按录入可用性重排。

## 执行顺序

1. 建立 reference-command 视觉系统与 module schema。
2. 重建登录页和三端 shell。
3. 重建 `/review/overview` 为 4x4 指挥中心。
4. 重建 03/04 录入端。
5. 重建 05/07/08/09/10/11/16 审阅端模块页。
6. 重建 06/12/13/14/16 管理端模块页。
7. 删除旧前端残余与未引用样式。
8. 运行目标图视觉审计和全量功能测试。
