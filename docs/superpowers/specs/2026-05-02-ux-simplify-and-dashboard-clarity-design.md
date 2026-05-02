# 填报端 UX 精简 + 管理端层级清晰化

> 两个独立方向，可并行执行。填报端改动影响一线工人每班操作，优先级最高。

## 方向 A：填报端 UX 精简

### 目标

主操按卷录入时，屏幕上只出现必须手动填的字段。零冗余、零认知负担。

### A1. 合金牌号 → 全局下拉框

**现状**：所有车间的 `alloy_grade` 字段类型为 `text`，工人手动输入"5052"等字符串，容易拼错、格式不一致。

**改动**：

后端：
- 新增全局配置表 `global_config`（key-value），存储 `alloy_grades` 列表
- 新增 `GET /api/config/alloy-grades` 接口，返回 `["1060", "3003", "3A21", "5052", "5083", "6061", "6063", "8011"]`
- 所有车间模板中 `alloy_grade` 字段类型从 `text` 改为 `select`
- 字段定义新增 `options_source: "alloy_grades"` 标记，前端据此从接口拉取选项

前端（EntryFieldInput.vue）：
- 新增 `select` 类型渲染分支：使用 `el-select` + `filterable` 属性
- 支持搜索过滤（牌号多时快速定位）
- 保留手动输入能力（`allow-create`），防止新牌号无法录入

前端（UnifiedEntryForm.vue）：
- 已有 `select` 类型渲染，但 options 是静态的。改为支持 `options_source` 动态拉取。

### A2. 废料重量、成品率 → 完全隐藏

**现状**：`readonly_fields` 中的 `scrap_weight` 和 `yield_rate` 在前端"自动计算"区域展示。工人不需要看这些数字。

**改动**：

后端：
- 模板中 `readonly_fields` 保留定义（后端计算存库需要 compute 表达式）
- 新增字段属性 `hidden: true`，标记不需要前端展示的 readonly 字段
- 在 `createCoilEntry` / `saveMobileReport` 保存时，自动计算 scrap_weight 和 yield_rate 并写入数据库

前端：
- `DynamicEntryForm`：`readonlyDisplayItems` 过滤掉 `hidden: true` 的字段
- `UnifiedEntryForm`：`readonlyFields` 过滤掉 `hidden: true` 的字段
- 当过滤后 `readonlyFields` 为空时，不渲染"自动计算"区域

### A3. 上机时间、下机时间 → 确认移除

**现状**：`on_machine_time` / `off_machine_time` 在字段权限系统中存在，但所有车间模板的 `entry_fields` 中均未包含。主操看不到这两个字段。

**改动**：无需改动。确认当前状态正确。后端 `created_at` 自动记录填报时间，卷次由 `coilSeq` 自增。

### A4. 规格字段三框输入 → DynamicEntryForm 对齐

**现状**：
- `UnifiedEntryForm` 已实现三框拆分（厚×宽×长），用户不需要输入乘号
- `DynamicEntryForm` 的 `EntryFieldInput` 组件对 `spec` 类型字段渲染为普通文本输入

**改动**：

`EntryFieldInput.vue`：
- 新增 `spec` 类型渲染分支：三个 `el-input` + "×" 分隔符
- 复用 UnifiedEntryForm 的 `syncSpec` 逻辑：三个 part 拼接为 `p0×p1×p2`
- 第三个框根据 `field.spec_suffix` 决定是否固定（如矫直车间的 "C"）
- 每个框的 placeholder：厚、宽、长/C
- inputmode="decimal" 用于厚和宽

### A5. material_state → 下拉框

**现状**：`material_state`（状态，如 O、H14、T4）是自由文本。常用状态有限。

**改动**：
- 后端：字段类型改为 `select`，`options_source: "material_states"`
- 全局配置新增 `material_states` 列表：`["O", "H12", "H14", "H16", "H18", "H22", "H24", "H26", "H32", "T4", "T6"]`
- 前端：复用 A1 的 select 渲染逻辑

---

## 方向 B：管理端仪表盘层级清晰化

### 目标

每个仪表盘有明确的视觉层级：第一眼 → 关键指标 → 详情。信息量不减，但主次分明。

### B1. FactoryDirector 信息层级重构

**现状问题**：
- 战争室可视化（XtFactoryMap + XtExecutionRail）占据大量首屏空间，信息密度低
- 6张 hero 卡片 + 8张详情卡片 + 4个标签页，层级扁平
- 工作坊色带（workshop ribbon）在大屏上卡片过宽

**改动**：

第一层（首屏，一眼扫完）：
- 保留 hero 区域，但精简为 **3张核心卡片**：今日产量、缺报班次、异常数
- 每张卡片：一个大数字 + 一行趋势对比（vs 昨日）
- 移除战争室可视化（XtFactoryMap、XtExecutionRail）——这些信息在车间端更有价值
- 移除"数据留存"卡片（运维指标，不属于厂长关注范围）

第二层（关键运营指标）：
- 交付进度、单吨能耗、月累计产量 → 3张次级卡片
- 视觉上比第一层小一号（字体、间距递减）

第三层（详情，默认折叠）：
- 保留 4 个标签页（上报、关注、趋势、归档）
- 上报标签页的表格保持不变
- 8张详情卡片 → 收入"关注"标签页内

### B2. Statistics 分组收纳

**现状问题**：
- 15张指标卡片平铺，首屏信息过载
- 多张表格紧密排列，无视觉呼吸

**改动**：

首屏（5张核心指标）：
- 待处理班次、手机上报率、未报班次、未处理差异、交付状态
- 其余 10 张卡片收入"更多指标"折叠区

表格区：
- 每张表格独立为可折叠面板
- 默认只展开"待处理班次"表
- 其余表格（提醒汇总、MES 同步、成品率矩阵、合同泳道）默认折叠

### B3. 三端视觉统一

**改动**：
- 统一 stat-card 组件：所有仪表盘使用同一个 `<StatCard>` 组件
- 统一表格样式：提取 `.dashboard-table` 公共类
- 统一折叠/展开交互：所有详情区域使用 `el-collapse`
- 统一响应式断点：900px（单列）、1200px（双列）、1600px+（满列）

---

## 分工

| 任务 | 执行者 | 依赖 |
|------|--------|------|
| A1 后端：全局配置表 + alloy-grades 接口 | Codex | 无 |
| A2 后端：readonly_fields hidden 标记 + 保存时自动计算 | Codex | 无 |
| A5 后端：material_states 全局配置 | Codex | A1 |
| A1 前端：EntryFieldInput select 渲染 | Claude Code | A1 后端 |
| A2 前端：隐藏 readonly 字段 | Claude Code | A2 后端 |
| A4 前端：EntryFieldInput spec 三框 | Claude Code | 无 |
| B1 前端：FactoryDirector 层级重构 | Claude Code | 无 |
| B2 前端：Statistics 分组收纳 | Claude Code | 无 |
| B3 前端：StatCard 组件统一 | Claude Code | B1, B2 |

## 验收标准

- 主操录入一卷数据：只看到必填字段，合金牌号下拉选择，规格三框输入，无废料/成品率显示
- FactoryDirector 首屏：3张核心卡片，一眼看到今日产量、缺报、异常
- Statistics 首屏：5张核心指标，其余折叠
- 三个仪表盘切换时视觉语言一致
