# 鑫泰铝业 MES 全量平台升级设计

> 日期：2026-04-27
> 范围：视觉 + 组件 + 功能 + 交互 + 导航 — 一次性全量替换
> 约束：前后端均可改动

---

## 1. 设计系统基础

### 1.1 Token 体系

废弃现有三套并存的 token（`tokens.css`、`command-tokens.css`、`tokens.js`），建立单一 CSS Custom Properties 体系。

命名规范：`--xt-{category}-{name}`（xt = 鑫泰）

**色彩：**
- 主色：`--xt-primary: #0071e3`
- 工业灰阶梯度：`--xt-gray-50: #f9fafb` → `--xt-gray-100: #f3f4f6` → `--xt-gray-200: #e5e7eb` → `--xt-gray-300: #d1d5db` → `--xt-gray-400: #9ca3af` → `--xt-gray-500: #6b7280` → `--xt-gray-600: #4b5563` → `--xt-gray-700: #374151` → `--xt-gray-800: #1f2937` → `--xt-gray-900: #111827`
- 语义色（饱和度降低，适合工业场景）：
  - `--xt-success: #22c55e`
  - `--xt-warning: #f59e0b`
  - `--xt-danger: #ef4444`
  - `--xt-info: #3b82f6`

**字体：**
- 数字：`--xt-font-number: 'DIN Alternate', 'Barlow Condensed', 'SF Pro Display', monospace`
- 正文：`--xt-font-body: 'MiSans', -apple-system, 'Segoe UI', sans-serif`
- 标题：`--xt-font-heading: 'MiSans', -apple-system, 'Segoe UI', sans-serif`

**间距（8px 基准网格）：**
`--xt-space-1: 4px` / `--xt-space-2: 8px` / `--xt-space-3: 12px` / `--xt-space-4: 16px` / `--xt-space-6: 24px` / `--xt-space-8: 32px` / `--xt-space-12: 48px`

**圆角：**
- `--xt-radius-sm: 4px`（输入框、小元素）
- `--xt-radius-md: 6px`（按钮）
- `--xt-radius-lg: 8px`（卡片）
- `--xt-radius-xl: 12px`（弹窗、大容器）

**阴影（去掉蓝色调）：**
- `--xt-shadow-sm: 0 1px 2px rgba(0,0,0,0.05)`
- `--xt-shadow-md: 0 4px 12px rgba(0,0,0,0.08)`

### 1.2 Logo

重新设计鑫泰 logo，现代工业风：
- SVG 实现，支持单色/彩色两个版本
- 图形：铝材/金属质感的抽象几何图形 + "鑫泰" 中文字标 + "XINTAI" 英文辅助
- 三种尺寸变体：
  - 完整版（图形 + 中英文）：侧边栏展开态、登录页
  - 紧凑版（图形 + 中文）：顶栏
  - 图标版（仅图形）：侧边栏折叠态、favicon

### 1.3 背景 & 装饰层

废弃 `ambient.css` 的 orbs、dot grid、neural accents。

新装饰层 `industrial.css`：
- 极淡蓝图网格线（`rgba(0,113,227,0.03)`），仅大面积空白区域可见
- 页面顶部微妙技术感渐变条（主色到透明，高度 2-3px）
- 登录页：深色工业氛围背景（微妙金属纹理 + 蓝图线条）
- 其他页面：`--xt-bg-page: #f5f7fa` 浅灰背景，装饰极度克制

### 1.4 动效体系

三个时间档：
- `--xt-motion-fast: 120ms`
- `--xt-motion-normal: 200ms`
- `--xt-motion-slow: 350ms`

统一缓动：`--xt-ease: cubic-bezier(0.25, 0.1, 0.25, 1)`

动效清单：
- 页面切换：淡入淡出 200ms
- 卡片入场：`translateY(8px)` + opacity 渐入，交错延迟 50ms
- KPI 数字：countUp 滚动动画
- 状态变化：颜色过渡 200ms
- 骨架屏：shimmer 加载态
- 废弃：弹簧动画、pulse、breathing glow、flow node 动画

---

## 2. 导航体系重设计

### 2.1 架构重组

**entry 表面（操作员端）— 保持独立：**
- 轻量 shell，移动端优先
- 底部 tab 导航：首页 / 录入 / 草稿 / 我的
- 无侧边栏，全屏内容区
- 路由前缀：`/entry/*`

**管理端（review + admin 合并）：**
- 单一 `ManageShell`，权限控制菜单可见性
- 路由前缀：`/manage/*`
- 旧 `/review/*` 和 `/admin/*` 做 301 重定向

### 2.2 ManageShell 布局

左侧边栏导航，分组折叠式：
- **总览**（Overview）
- **生产管理**：录入中心、班次中心、对账中心
- **质量管控**：异常审核、质量预警
- **数据分析**：统计中心、成本效益、报表交付
- **基础数据**：主数据、别名映射、导入历史
- **AI 工作台**
- **系统管理**（原 admin 内容，仅管理员可见）

顶栏：logo + 全局搜索框 + 通知图标 + 用户头像下拉

响应式：
- `>1024px`：侧边栏展开（240px）
- `768-1024px`：侧边栏折叠为 icon-only（64px）
- `<768px`：侧边栏隐藏 + 汉堡菜单

侧边栏折叠状态记忆到 localStorage。内容区最大宽度 1400px，居中。

### 2.3 EntryShell 重写

- 底部 tab bar + 顶部状态栏（当前班次、用户名）
- safe area 适配（iOS bottom bar）
- 微信内嵌适配

### 2.4 路由表

```
/login                    — 登录页
/entry/*                  — 操作员端
  /entry                  — 首页
  /entry/report/:batch    — 录入流程
  /entry/advanced/:batch  — 高级录入
  /entry/drafts           — 草稿箱
  /entry/profile          — 我的
/manage/*                 — 管理端
  /manage/overview        — 总览
  /manage/entry-center    — 录入中心
  /manage/shift           — 班次中心
  /manage/reconciliation  — 对账中心
  /manage/anomaly         — 异常审核
  /manage/quality         — 质量预警
  /manage/statistics      — 统计中心
  /manage/cost            — 成本效益
  /manage/reports         — 报表交付
  /manage/master          — 主数据
  /manage/alias           — 别名映射
  /manage/imports         — 导入历史
  /manage/ai              — AI 工作台
  /manage/admin/*         — 系统管理（权限门控）
```

旧路由（`/review/*`、`/admin/*`、`/mobile/*`、`/dashboard/*`）全部 redirect 到新路径。

---

## 3. 全新组件体系（`src/components/xt/`）

### 3.1 布局组件

**XtPageHeader** — 页面标题区：
- 左侧：模块编号（大号蓝色）+ 中文标题 + 英文副标题
- 右侧：工具按钮插槽（筛选、导出、刷新等）
- 底部可选：面包屑导航

**XtCard** — 基础卡片：
- 白底、8px 圆角、sm 阴影
- props：`title`、`padding`（默认 16px）、`hoverable`
- 插槽：header、default、footer

**XtGrid** — 响应式网格：
- CSS Grid 实现，props 控制列数和间距
- 自动响应式：移动端单列，平板双列，桌面按 props

### 3.2 数据展示组件

**XtKpi** — KPI 卡片：
- 大数字（DIN 字体）+ 标签 + 可选趋势箭头/百分比
- countUp 入场动画
- 支持 loading 骨架态

**XtTable** — 数据表格：
- 封装 el-table，统一行高、字号、斑马纹、hover 样式
- 内置：空状态、loading 骨架、分页
- 列配置支持 status 渲染（自动用 XtStatus）

**XtStatus** — 状态标签：
- pill 形态，映射业务状态到语义色
- props：`status`（normal/pending/risk/blocked/done）
- 紧凑尺寸，适合表格内使用

**XtTrend** — 趋势迷你图：
- 基于 Canvas 的 sparkline
- 极简实现，不引入图表库

### 3.3 交互组件

**XtActionBar** — 操作栏：
- 固定底部或页面内，主按钮 + 次要按钮布局
- 移动端 safe area 适配

**XtSearch** — 全局搜索/命令面板：
- Cmd+K / Ctrl+K 唤起
- 搜索范围：页面导航、最近记录、批次号、操作指令
- 键盘导航，模糊匹配，结果分组展示

**XtFilter** — 高级筛选面板：
- 可展开/收起的筛选条件区
- 支持：日期范围、下拉选择、文本搜索、状态多选
- 筛选条件以 tag 形式展示，可单独移除
- URL query 同步，支持分享筛选链接

**XtBatchAction** — 批量操作栏：
- 表格多选时浮出
- 显示已选数量 + 批量操作按钮

**XtExport** — 数据导出：
- 按钮触发，支持 CSV/Excel
- 可选导出当前页或全部数据

### 3.4 反馈组件

**XtSkeleton** — 骨架屏：
- 预设模板：table、kpi-strip、card、page
- shimmer 动画

**XtEmpty** — 空状态：
- 简洁插画 + 文案 + 可选操作按钮
- 预设场景：无数据、无搜索结果、无权限

**XtNotification** — 通知提示：
- 右上角通知铃铛 + 下拉面板
- 分类：异常提醒、审批待办、系统通知
- 未读计数 badge

### 3.5 AI 组件

**XtChat** — AI 对话组件：
- 消息流渲染（用户消息、AI 消息、工具调用卡片、思考过程）
- Markdown 渲染支持
- 流式输出显示

**XtToolCall** — 工具调用卡片：
- 折叠式，显示工具名 + 参数摘要
- 可展开查看完整参数和结果

---

## 4. AI 工作台（`/manage/ai`）

### 4.1 整体架构

独立全宽页面，不受 1400px 内容区限制。两栏布局：
- 左侧：对话列表侧边栏（240px，可折叠）
- 右侧：主对话区

后端通过 MCP（Model Context Protocol）连接 AI 模型，AI 可调用系统内部工具。

### 4.2 对话列表侧边栏

- 新建对话按钮
- 历史对话列表，按日期分组（今天 / 最近 7 天 / 更早）
- 每条显示：标题（自动从首条消息生成）+ 时间
- 支持重命名、删除
- 底部：对话设置（模型选择、系统提示词配置）

### 4.3 主对话区

顶部：当前对话标题 + 模型标识

消息流：
- 用户消息：右对齐，主色背景，白色文字
- AI 消息：左对齐，白色卡片，Markdown 渲染
- 工具调用：折叠式卡片（工具名 + 参数 + 结果摘要，可展开）
- 思考过程：可折叠淡色区域

输入区：
- 多行文本框，Shift+Enter 换行，Enter 发送
- 附件按钮（上传图片/文件）
- 发送/停止按钮

### 4.4 MCP 工具集（后端）

AI 可调用的系统工具：
- `query_production` — 查询生产数据（按批次、日期、产线）
- `query_anomaly` — 查询异常记录
- `query_shift` — 查询班次报表
- `query_statistics` — 查询统计汇总
- `export_report` — 生成并导出报表
- `create_entry` — 创建录入草稿（需人工确认）
- `search_master` — 搜索主数据

安全边界：
- 所有写操作只创建草稿，不直接提交
- 工具调用结果对用户透明可见
- 权限继承当前登录用户的角色权限

### 4.5 后端 API

```
POST   /api/ai/chat                    — 发送消息（SSE 流式返回）
GET    /api/ai/conversations            — 对话列表
GET    /api/ai/conversations/:id        — 对话详情
DELETE /api/ai/conversations/:id        — 删除对话
PATCH  /api/ai/conversations/:id        — 重命名
POST   /api/ai/conversations/:id/stop   — 停止生成
```

MCP 连接在后端管理，前端不直接接触模型 API。

---

## 5. 效率工具集

### 5.1 全局搜索（XtSearch）

- Cmd+K / Ctrl+K 唤起，覆盖全应用
- 搜索源：页面导航、批次号、主数据记录、最近操作
- 后端新增 `GET /api/search?q=xxx` 统一搜索接口
- 结果分组：导航 / 生产记录 / 主数据
- 键盘上下选择，回车跳转

### 5.2 数据导出（XtExport）

- 所有表格页面右上角统一导出按钮
- 支持 CSV 和 Excel（.xlsx），后端用 openpyxl 生成
- 导出当前筛选条件下的数据，非仅当前页
- 后端新增 `POST /api/export/{module}` 接口，返回文件下载链接

### 5.3 批量操作（XtBatchAction）

- 表格多选 checkbox
- 选中后底部浮出操作栏：已选 N 条 + 批量审批 / 批量导出 / 批量删除
- 适用页面：异常审核、录入中心、导入历史

### 5.4 高级筛选（XtFilter）

- 每个列表页顶部统一筛选区
- 常用筛选项直接展示，更多条件点击展开
- 筛选条件以 tag 展示，可单独清除
- URL query 同步，支持分享筛选链接

---

## 6. 各页面升级策略

所有页面统一用新组件体系重写，逻辑层（store、API 调用、表单绑定）尽量复用。

### 6.1 登录页 `/login`

- 深色工业氛围背景（蓝图纹理 + 微妙金属质感）
- 居中大尺寸鑫泰 logo
- 白色登录卡片，简洁表单
- 保留钉钉 SSO 和 QR 机台登录

### 6.2 操作员端 `/entry/*`

- 底部 tab 导航重写
- 首页：当前班次 + KPI 条 + 批次号输入 + 快捷操作
- 录入流程：步骤条优化，每步一屏，底部固定操作栏
- 移动端优先，375px 起适配

### 6.3 管理端各中心（统一模式）

每个中心页面遵循统一结构：
1. `XtPageHeader`（编号 + 标题 + 工具按钮）
2. `XtKpi` 条（3-5 个关键指标）
3. `XtFilter` 筛选区
4. `XtTable` 主数据表

各中心的 KPI 和表格列配置沿用现有 `moduleCatalog.js`，迁移到新组件。

**具体中心：**
- **总览**：KPI 大盘 + 产线状态可视化 + 快捷入口
- **录入中心**：录入记录表 + 状态筛选 + 批量审批
- **班次中心**：班次报表列表 + 日期筛选
- **对账中心**：对账明细表 + 差异高亮
- **异常审核**：异常列表 + 批量处理 + 状态流转
- **统计中心**：图表 + 数据表切换视图
- **主数据 / 别名映射 / 导入历史**：标准 CRUD 列表页
- **报表交付**：报表列表 + 下载/预览
- **成本效益 / 质量预警**：KPI + 趋势图 + 明细表

---

## 7. 旧代码清理

全量替换完成后删除：
- `src/components/app/` — 全部旧组件
- `src/reference-command/` — 全部 command-* 组件和样式
- `src/design/ambient.css` — 旧装饰层
- `src/design/tokens.js` — JS token（统一用 CSS）
- `src/design/centerTheme.js` — 旧主题
- `AppShell.vue`、`ReviewShell.vue`、`AdminShell.vue` — 旧 shell 组件

---

## 8. 后端新增接口汇总

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/search` | GET | 全局搜索 |
| `/api/export/{module}` | POST | 数据导出 |
| `/api/ai/chat` | POST | AI 对话（SSE） |
| `/api/ai/conversations` | GET | 对话列表 |
| `/api/ai/conversations/:id` | GET/PATCH/DELETE | 对话 CRUD |
| `/api/ai/conversations/:id/stop` | POST | 停止生成 |
| `/api/notifications` | GET | 通知列表（轮询，30s 间隔） |
| `/api/notifications/:id/read` | POST | 标记已读 |
| `/api/notifications/unread-count` | GET | 未读计数（轮询，30s 间隔） |

---

## 9. 响应式断点

| 断点 | 场景 | 布局 |
|------|------|------|
| `<375px` | 小屏手机 | 单列，紧凑间距 |
| `375-767px` | 手机/微信 | 单列，标准间距 |
| `768-1023px` | 平板 | 双列，侧边栏折叠 |
| `1024-1439px` | 小桌面 | 多列，侧边栏展开 |
| `≥1440px` | 大桌面 | 多列，内容区 1400px 居中 |

---

## 10. 测试策略

- E2E 覆盖所有页面的基本渲染和导航
- 移动端视口测试（375px、768px）
- 登录流程全路径测试
- AI 工作台：对话创建、消息发送、工具调用展示
- 旧路由重定向验证
- 权限门控验证（操作员不可访问管理端，非管理员不可访问系统管理）
