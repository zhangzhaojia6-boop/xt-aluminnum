# Parse 3 Owner Forms And Source Lanes Design

## 背景

parse2 已把机台主操收成更贴现场的“一岗一表”首刀：

- 主路径固定为 `随行卡 / 本卷 / 班末 / 提交`
- 主操只保留逐卷原始值，班末字段已从通用补充字段中拆出
- 机器账号的 E2E 已切到二维码登录，避免密码哈希漂移影响回归稳定性

但专项 owner 这一层还停留在“共享一张补录骨架”的状态：

- `contracts / inventory_keeper / utility_manager` 仍共用 `DynamicEntryForm.vue` 的 owner-only 模式
- 它们虽然字段权限已经拆开，但前端仍主要靠通用 `extra_fields` 渲染
- 审阅端已经能看运行图层和结果图层，但“数据到底来自哪个岗位、经过哪层处理”还不够稳定、可解释

parse3 的目标不是扩业务，而是把专项 owner 的录入与审阅来源图层做实，为后续预测、核算、排产等后端 agent 能力预留稳定挂点。

## 已确认事实

- Phase 2 的双端分离基线已经稳定：`/mobile` 为填报端，`/review/*` 为审阅端
- parse2 的当前验证基线已更新为：
  - `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q` → `34 passed`
  - `docker compose run --rm backend sh -lc "pytest -q"` → `383 passed`
  - `cd frontend && npm run build` → 通过
  - `cd frontend && npx playwright test e2e/dynamic-entry-layout.spec.js e2e/zd1-machine-smoke.spec.js e2e/workshop-template-config.spec.js` → `3 passed`
- 当前 owner-only 角色桶只覆盖 `contracts / inventory_keeper / utility_manager`
- `workshop_templates.py` 中这些岗位的字段责任已经明确，但仍主要挂在 `entry_fields + extra_fields` 的模板定义里
- `DynamicEntryForm.vue` 已能区分 `entry_fields / shift_fields / extra_fields`，但 owner-only 模式仍是通用骨架

## 方案比较

### 方案 A：继续沿用通用 owner-only 骨架，只做减字减块

优点：

- 代码改动最小
- 短期可继续复用 parse2 的页面结构

缺点：

- 角色之间的字段语义仍然混在一起
- 后续审阅端很难稳定讲清楚“这条数据是谁报的、为何属于这个岗位”
- 未来要接入 AI 分析、预测、核算时，来源边界仍然模糊

### 方案 B：专项 owner 一岗一表，但仍共用同一页组件骨架

优点：

- 可以复用现有 `DynamicEntryForm.vue` 的滑屏、提交、草稿、历史逻辑
- 能把 `inventory / utility / contracts` 的字段布局、标题、节奏拆开
- 与 parse2 连续，风险较低

缺点：

- 需要把通用 owner-only 模式进一步拆成“岗位模板驱动”
- 审阅端的数据来源图层也要同步调整，不能只改填报端

### 方案 C：直接为每个专项岗位单独做独立页面

优点：

- 页面最贴岗位
- 后期视觉表达最自由

缺点：

- 会快速复制出多份相似逻辑
- 与当前仓库“统一骨架 + 模板裁剪”的方向相反
- 后续维护成本高

## 推荐方案

采用 **方案 B**。

也就是：

- 保留当前 `DynamicEntryForm.vue` 的统一工作台骨架
- 但把 owner-only 从“共用补录模式”推进到“按岗位模板驱动的一岗一表”
- 同时把审阅端的数据来源图层做成稳定的来源泳道，而不是只在摘要里零散显示

这样既不推翻 parse2，也能为 parse3 之后的 AI 后端能力接入打好来源边界。

## 设计

### 1. parse3 的主目标

parse3 只做两件事：

1. `专项 owner 一岗一表`
2. `审阅端来源泳道化`

不在这一轮引入新的业务系统，也不把成本、排产、合同排序、MES 接入拉进主流程。

### 2. 填报端设计

#### 2.1 总体原则

- 继续维持填报端与审阅端彻底分离
- 专项 owner 只看到自己的岗位窗口，不看到主操录卷路径
- 每个 owner 页面优先用 `图块 + 状态 + 短标签`，而不是长字段说明
- 保持滑屏和轻微阻尼，但不追求“每个字段都一屏”，而是按岗位任务分屏

#### 2.2 inventory_keeper

成品库页面拆成三段：

- `今日入库`
- `今日发货`
- `结存与备料`

要求：

- 首屏先看当天进出库，不先看月累计
- 月累计口径退到后屏或折叠区
- `actual_inventory_weight` 继续保持只读派生，不允许手输

#### 2.3 utility_manager

水电气页面拆成三段：

- `用电`
- `天然气`
- `用水`

要求：

- 按介质分组，不按字段平铺
- “全厂 / 新厂 / 园区”这类口径用短标签明确
- 保留后续 AI 能耗分析的来源字段，不在前台解释算法

#### 2.4 contracts

计划科页面拆成三段：

- `当日合同`
- `月累计与余合同`
- `投料与坯料`

要求：

- 合同相关字段按时间口径组织
- 不把合同、投料、余量混成一屏
- 延续当前“计划科补录”的 owner-only 登录方式

#### 2.5 qc

质检目前已有独立字段责任，但还没有进入 owner-only 桶。

parse3 不强行把 `qc` 并入 owner-only 首批主线，只做两件准备：

- 明确 `qc_grade / qc_notes` 在来源泳道中的位置
- 为下一轮把质检独立成专属岗位窗口预留模板入口

这样可以避免 parse3 一次把 owner-only 范围拉太宽。

### 3. 审阅端来源泳道设计

审阅端新增稳定的来源泳道层，固定表达：

- `主操直录`
- `专项补录`
- `系统汇总`
- `结果发布`

每条关键数据都要能落到其中一条来源泳道上，并能回答三件事：

1. 谁报的
2. 现在处理到哪一步
3. 最终落进了哪张结果卡

这一层优先给管理员审阅层使用，先做到“看得懂来源”，再考虑更复杂的预测与建议。

### 4. 后端准备

parse3 的后端重点不是新建复杂 workflow，而是先把来源元数据稳定下来：

- owner-only 字段按岗位类型可追溯
- 审阅端汇总接口返回更稳定的来源分类
- 模板定义中的 `entry_fields / shift_fields / extra_fields / qc_fields` 对岗位语义更明确

如果某个来源仍要靠前端猜，就说明 parse3 还没做完。

### 5. 测试策略

parse3 继续保持“先测再改”：

- 模板分流测试：岗位模板是否正确切出一岗一表
- 填报端静态文案测试：避免重新出现 AI 解释型废话
- E2E：至少覆盖 `inventory_keeper / utility_manager / contracts` 三条专项岗位真实提交链
- 审阅端接口测试：来源泳道与结果卡映射是否稳定

## 本轮不做

- 不做 MES 接入
- 不做成本核算主流程
- 不做排产建议主流程
- 不做质检独立窗口的完整实现
- 不新增新的桌面后台统计工作台
- 不引入新的前端依赖

## 验收标准

- `inventory_keeper / utility_manager / contracts` 三类岗位不再共用同一份补录语义，而是看起来就是各自的一岗一表
- 填报端字段继续减字、减解释、减后台味
- 审阅端能稳定说明数据来自主操还是专项 owner，且能看出处理阶段
- 至少三条专项岗位真实提交流程有可复验的 E2E 证据
- parse3 完成后，可以自然进入“来源稳定前提下的 AI 分析/预测/核算挂点”下一段，而无需重新整理来源边界

## 建议实施顺序

1. 先拆 owner-only 模板语义与分屏配置
2. 再补 `inventory / utility / contracts` 三类专项岗位 E2E
3. 然后补审阅端来源泳道接口与前端卡片
4. 最后做一轮浏览器验收，确认填报和审阅都更直白
