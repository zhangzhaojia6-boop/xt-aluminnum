# 鑫泰铝业 数据中枢：MES 主账、卷级线索与实时生产流转大屏评审优化计划

日期：2026-06-11

状态：评审版，可进入第一阶段只读审计和 TDD 实施准备。

## 1. 本轮评审结论

原计划方向正确，但还不够“可直接施工”。这次按 CEO、工程、设计三个视角重新审查后，计划需要补强四件事：

1. 先修正数据可信度，再做大屏视觉升级。
2. 先解决 MES 终端到机列的归属，再削减填报端字段。
3. 先隔离异常算法值，再把自动废料、成品率放上前端主屏。
4. 先做只读外部通讯，再做钉钉群 AI 多模态助手。

一句话：不要再做“多一个漂亮页面”，要做“用户一眼知道哪卷料在哪里、数据来自哪里、异常该谁处理”的生产指挥系统。

## 2. 当前证据

### 2.1 代码证据

- MES 卷级、工序、库存模型已存在：`backend/app/models/mes.py:32`, `backend/app/models/mes.py:104`, `backend/app/models/mes.py:132`。
- 机列别名和主数据别名已存在：`backend/app/models/master.py:119`, `backend/app/services/mes_machine_match_service.py:114`, `backend/app/services/mes_machine_match_service.py:217`。
- 卷级接口已存在：`backend/app/routers/factory_command.py:51`, `backend/app/routers/factory_command.py:57`, `backend/app/routers/factory_command.py:79`。
- 卷级服务已有机列列表、卷列表、卷流向：`backend/app/services/factory_command_service.py:1393`, `backend/app/services/factory_command_service.py:1464`, `backend/app/services/factory_command_service.py:1511`。
- 手机端已有 MES 待补录和随行卡流向建议：`backend/app/routers/mobile.py:90`, `backend/app/routers/mobile.py:283`。
- 手机端按卷录入页已存在：`frontend/src/views/mobile/CoilEntryWorkbench.vue:23`, `frontend/src/views/mobile/CoilEntryWorkbench.vue:138`, `frontend/src/views/mobile/CoilEntryWorkbench.vue:731`。
- 实时大屏已有 SSE 和 30 秒快照兜底：`frontend/src/views/manage/live/LiveDashboardPage.vue:113`, `frontend/src/views/manage/live/LiveDashboardPage.vue:123`。
- 当前能耗主口径是 `machine_energy_records`：`backend/app/models/energy.py:30`, `backend/app/domain/metric_contracts.py:21`。
- 钉钉推送和群消息已有服务基础：`backend/app/services/dingtalk_service.py:535`, `backend/app/services/dingtalk_service.py:564`。
- AI 读取生产上下文已有基础：`backend/app/services/ai_context_service.py:339`, `backend/app/services/ai_context_service.py:341`, `backend/app/services/ai_context_service.py:342`。

### 2.2 浏览器体验证据

使用真实线上地址 `https://xtmijd.com` 登录管理端，只读打开核心页面：

- `/manage/live` 能打开，标题为“全厂实时调度墙”，但页面显示 `MES包装产量 0`、`过站下机 0`、`总电耗 0`。
- `/manage/today` 能打开，标题为“工厂总览”，但多个核心指标显示“暂无可信数据”。
- `/manage/production` 能打开，标题为“生产”，但显示“入库产量 —”“车间排行 0 个车间”。
- `/manage/fill-details` 能打开，但核心对照区多处显示“暂无可信数据”。
- `/manage/admin/settings` 能打开，系统设置里显示 `MES 补录就绪 可试跑`、`机台匹配 81%`、`09:30窗口 91`。

### 2.3 线上接口证据

同一登录态下，只读查询接口：

- MES 同步是 fresh，适配器为 `sqlserver`，最近同步成功。
- `mes/extended/summary` 显示车间过站 1531 行、成品库存 1223 行、成品率 310 行。
- `material_records` 最新业务日为 `2026-06-07`，比当前生产日滞后，不能直接当实时在制主数据。
- `2026-06-10` 全厂最终包装口径为 `327.41 吨`，来源 `mes_stock_records`。
- `2026-06-11` 全厂最终包装口径为 `170.03 吨`，来源 `mes_stock_records`。
- `2026-06-10` 实时聚合过站输出为 `2431.21 吨`，这不是最终入库产量。
- `2026-06-11` 实时聚合出现 `input=106351.77`、`output=1186.6`、`scrap=105143.55`、`yield_rate=1.12%`，这个值明显需要进入异常口径审查，不能直接作为大屏主值。
- `mes/supplement-readiness` 显示 `sample_count=91`、`machine_match_rate=81.25%`、`generic_terminal_count=59`、`unmatched_count=6`。
- 未匹配设备集中在 `精整新19辊（WAN）`，说明不是所有问题都叫 `PC`，还需要通用终端和设备别名归属机制。

### 2.4 第二轮页面审查证据

继续只读打开管理端页面后，新增发现：

- `/manage/energy` 能打开，但页面体验里仍出现“同步中 / 0 条 / 能耗为 0”的状态；同日接口实际能返回能耗明细，说明需要核对前端日期、接口返回结构和加载状态。
- `/manage/contracts` 显示 `活跃合同 274`、`履约率 100%`、`延期 269`、`当月交付 0 吨`，这几个数放在一起不符合用户直觉，必须查公式或页面文案。
- `/manage/factory/destinations` 页面显示 `MES 投影 -- 未就绪`，但接口已返回在制和已分配数据，说明页面状态和接口状态没有对齐。
- `/manage/reports`、`/manage/inventory`、`/manage/attendance` 仍偏空，如果暂未接入真实业务，应在导航和页面上明确“预留/未接入”，避免用户误以为系统坏了。
- `/manage/master`、`/manage/alias`、`/manage/admin/users`、`/manage/admin/governance` 能打开，但角色、账号、别名仍比较分散，清理前必须先导出使用记录，不能直接删。
- `/entry` 和 `/entry/history` 用管理员账号无法代表真实填报端体验，后续必须用机台账号或二维码再测一轮。

### 2.5 第二轮接口与代码证据

只读查询线上接口和本地代码后，新增证据：

- `/api/v1/aggregation/live?business_date=2026-06-11` 返回 `factory_total.packaging_output=170.03`、`daily_output=170.03`、`finished_inbound_output=0`，所以“实时页显示 0”不能简单归因成 MES 没同步。
- 同一接口显示 `mes_sync_status.adapter=sqlserver`、`status=fresh`，说明线上已在用 SQL Server 投影链路，后续重点是字段映射、异常隔离和前端展示。
- `/api/v1/energy/summary?business_date=2026-06-11` 返回 5 条能耗明细，例如铸锭长白班 `electricity_value=2800`、`gas_value=6583`，但 `output_weight=0`，吨耗无法计算。
- `/api/v1/factory-command/coils?business_date=2026-06-11` 能返回卷级线索，但样例里 `line_code=unknown`、`machine_code=null`，说明卷已经能追踪，机列归属还不稳。
- `/api/v1/factory-command/destinations?business_date=2026-06-11` 返回在制 `1373` 卷、`330735.5`，已分配 `12` 卷、`70436`；这里单位需要复核，不能直接标成“吨”。
- `frontend/src/views/manage/live/LiveDashboardPage.vue:209` 使用 `fetchLiveAggregation` 获取实时聚合，`frontend/src/utils/liveDashboardPhase2.js:248` 已读取 `packaging_output`，所以修复应优先查业务日期、实时事件补丁、页面状态，而不是重写大屏取数。
- `frontend/src/utils/liveDashboardPhase2.js:368` 会把实时事件补丁合并进当前聚合，如果补丁缺字段或传了空值，有可能让快照里的完整数据被局部状态影响，需要写测试保护。
- `backend/app/services/mes_machine_match_service.py` 已把 `PC`、`电脑`、`一体机` 当通用终端处理，但现有逻辑仍缺“终端到机列/工艺”的人工绑定层。

### 2.6 第三轮路由、导航、接口覆盖证据

继续按全站体检目标做只读盘点：

- 前端路由文件里共发现 `143` 个 path，其中包含大量历史兼容跳转；真正管理端子路由约 `53` 个。
- 管理端左侧导航配置里有 `13` 个导航项，其中“各车间看板”包含车间主任专用入口和普通管理端入口，正常管理端实际展示的是一组精简核心入口。
- 后端 `backend/app/routers` 有 `34` 个路由文件、约 `224` 个接口声明，说明系统接口面很大，不能靠“页面能打开”判断业务链路已闭环。
- 前端 `frontend/src/api` 有 `22` 个 API 模块，但仍存在部分页面直接调用 `api.get(...)`，例如合同、库存、按卷补录页；后续最好逐步统一到 API 模块，便于测试和权限审计。
- 真实浏览器批量打开 `23` 个页面或详情页，均能返回 200 并渲染页面；这证明“整体可访问”，但不证明“业务数据都正确”。
- `/shift/detail/1` 页面能打开，但浏览器控制台出现 404 资源请求噪声，容易干扰 QA 判断。
- `/attendance/detail/360/2026-06-09` 和 `/attendance/exceptions` 是可访问的独立页面，但它们不在管理端主导航里；如果保留，应有清楚入口或只作为内部详情页。
- `/manage/reports`、`/manage/inventory`、`/manage/attendance` 批量抽查仍出现“暂无数据 / 0 条”信号，属于“页面存在但业务价值不足”的候选合并或隐藏对象。
- `/manage/contracts` 批量抽查仍出现“履约率 / 延期”信号，和前一轮接口矛盾一致，合同指标需要单独审查。
- `/manage/admin/users` 页面已渲染到“权限治理中心”，但自动脚本的登录页误判规则曾被页面文字干扰；后续自动化测试要用更稳的判断方式，例如检查 URL 和核心标题，不用简单查“登录”二字。

### 2.7 页面/接口覆盖矩阵

已新增独立审计文档：`docs/superpowers/audits/2026-06-11-page-api-coverage-matrix.md`。

这份矩阵把页面分成：

1. 核心页。
2. 管理页。
3. 详情页。
4. 隐藏页。
5. 已停用入口。
6. 可合并页。

并逐页记录导航入口、主要接口、浏览器现状、风险和建议。后续任何删除、合并、隐藏、改导航、改接口，都应先对照这份矩阵。

### 2.8 后端架构风险图

已新增独立审计文档：`docs/superpowers/audits/2026-06-11-backend-architecture-risk-map.md`。

这份架构图把后端分成：

1. 接口入口 `routers`。
2. 业务服务 `services`。
3. 数据库模型 `models`。
4. 外部适配器 `adapters`。
5. 自动任务 `agents`。
6. 领域口径 `domain`。
7. 接口结构 `schemas`。

当前只读统计显示：后端路由 `35` 个文件、服务 `97` 个文件、模型 `19` 个文件、适配器 `13` 个文件、Agent `10` 个文件、测试 `218` 个文件。最大风险集中在 `realtime_service.py`、`factory_command_service.py`、`mes_sync_service.py`、`energy_service.py`、`mobile` 填报链路和 AI 上下文链路。

后续任何修复 MES、能耗、实时大屏、卷级线索、AI 助手，都应先对照这份架构图，确认改动落在哪一层、会影响哪些页面、需要补哪些测试。

## 3. CEO 视角评审

### 3.1 关键判断

这个项目的真正价值不是“少填几个字段”，而是把生产现场从“人追表、人问人”升级成“系统主动告诉你哪卷料在哪里、哪个数据不可信、谁需要处理”。

### 3.2 当前计划的业务问题

1. **P1：用户仍会看不懂 0 是什么意思。**
   如果页面显示 0，但接口里其实有数据，管理者会怀疑系统不可信。

2. **P1：不能把异常算法值直接放上大屏。**
   `2026-06-11` 的实时聚合废料超过 10 万吨，明显不适合作为主屏指标。

3. **P1：后工序填报端不能马上取消。**
   MES 有主账价值，但机列归属、在制材料、异常字段还没有完全闭环。

4. **P2：卷级线索页应该成为新的核心页面。**
   用户最常问的不是“今天多少吨”，而是“这卷料现在在哪、下一步去哪、为什么异常”。

5. **P2：调度大屏要从汇总屏变成行动屏。**
   大屏不只是展示数字，还要告诉现场“接下来先处理哪 3 件事”。

### 3.3 CEO 结论

采用“MES 主账 + 填报补录 + 异常审核 + 实时指挥”的方向，分阶段灰度，不一次性砍掉填报端。

评分：9.7/10。

扣分原因：仍需确认每台 PC/一体机与机列、工艺的现场对应关系。

## 4. 工程视角评审

### 4.1 数据主线

推荐最终形成四层数据：

1. **MES 原始层**：只保存外部 MES 原始事实，不人工改。
2. **本地投影层**：把 MES 数据映射为本系统能用的卷级、机列、工艺、业务日。
3. **人工补录层**：只补 MES 没有或不可信的字段。
4. **展示指标层**：前端只读统一指标，不直接拼多张业务表。

### 4.2 必须新增的后端能力

1. **MES 终端绑定表**
   建议表名：`mes_terminal_bindings`。
   字段：`raw_terminal_name`、`raw_device_name`、`raw_workshop_name`、`raw_process_name`、`raw_operator_name`、`ip_hint`、`workshop_id`、`equipment_id`、`process_code`、`confidence`、`is_active`、`effective_from`、`effective_to`。

2. **机列匹配解释器**
   每条 MES 工序记录都返回匹配解释：直接编码、别名匹配、终端绑定、工艺推断、未匹配。

3. **卷级线索聚合接口**
   建议新增或增强：`GET /api/v1/factory-command/coils` 和 `GET /api/v1/factory-command/coils/{coil_key}/flow`。
   增加字段：算法废料、人工废料、差异、能耗参考、补录状态、异常状态、数据来源。

4. **废料安全计算器**
   不允许简单把所有 `input - output` 都当真实废料。
   必须按工艺、单位、上下限、异常阈值做校验。

5. **物联网能耗只读适配器**
   前端不能连物联网数据库。
   后端定时同步到本地影子表，再由本系统接口统一输出。

6. **实时事件中心**
   当前已有 SSE，但事件需要更结构化。
   事件类型至少包括：MES 新卷、工序更新、机列归属变化、能耗更新、异常新增、缺补录变化。

### 4.3 必须修复的技术问题

1. **P1：前端实时页显示 0 与接口实际有数不一致。**
   必须先查 `buildLiveStitchSurface`、`fetchLiveAggregation`、业务日期选择和字段映射。

2. **P1：6月11日废料/成品率异常。**
   必须先隔离异常行，不能让异常总值污染大屏。

3. **P1：MES 在制材料数据滞后。**
   `material_records` 最新业务日是 `2026-06-07`，当前不能作为实时在制唯一依据。

4. **P2：终端匹配不能只处理 PC。**
   未匹配样例是 `精整新19辊（WAN）`，说明要做终端/设备别名通用机制。

5. **P2：`0`、`—`、`暂无可信数据` 三种状态需要统一。**
   否则用户不知道是没数据、加载中、接口失败，还是真实为 0。

### 4.4 工程结论

计划可以执行，但第一阶段必须从“数据可信度修复”开始，而不是先做大屏重构。

评分：9.6/10。

扣分原因：物联网数据库字段和一体机唯一标识尚未拿到，不能直接估算工期。

## 5. 设计视角评审

### 5.1 页面结构建议

#### `/manage/live` 实时生产流转大屏

目标：现场调度墙，一眼看状态。

布局：

- 顶部：全厂最终包装产量、过站下机参考、在制卷数、算法废料、吨电耗、异常数。
- 中部：按工艺路线展示卷材流转。
- 左侧或下方：各车间/机列状态矩阵。
- 右侧：实时事件流和优先处理事项。
- 底部：MES、物联网、填报、钉钉、AI 服务状态。

必须区分：

- 真实为 0。
- 数据未同步。
- 接口失败。
- 当前业务日暂无数据。
- 数据异常被隔离。

#### `/manage/coils` 卷级线索页

目标：查一卷料的全过程。

核心信息：

- 随行卡、批号、客户、合金、规格。
- 当前车间、当前工艺、当前机列。
- 上机量、下机量、算法废料、人工废料。
- 能耗参考、质量异常、补录状态。
- 时间线：MES 过站、人工补录、异常审核。

#### 手机填报端

目标：少填、可改、不中断。

交互：

- 优先显示“MES 待补录卷”。
- 点一卷后自动带出客户、合金、规格、工艺、重量。
- 字段不锁死，允许人工改。
- 改动必须留下“人工修正”痕迹。
- 找不到卷时保留扫随行卡兜底。

### 5.2 设计问题

1. **P1：实时页当前全 0 的视觉会误导用户。**
   它看起来像系统没数据，而不是“当前筛选条件无数据”。

2. **P1：大屏不能只追求动效。**
   动效只服务于“数据变化”，不能用重光效拖慢页面。

3. **P2：卷级页面必须比填报明细更清楚。**
   填报明细是“谁填了什么”，卷级线索是“这卷料发生了什么”，两者不能混。

4. **P2：移动端要减少字段，而不是把管理端搬到手机。**
   主操只需要看到本机列、本班、本卷、待补录、异常。

### 5.3 设计结论

计划需要增加“状态语言规范”和“卷级线索信息架构”，否则前端重构会继续变成多个相似页面。

评分：9.6/10。

扣分原因：还缺目标视觉稿和每个页面的空状态、异常状态细节稿。

## 6. 优化后的执行顺序

### 第一阶段：数据可信度修复

目标：先让系统里的数可信。

任务：

- 查清 `/manage/live` 为什么显示 0，但 `/api/v1/aggregation/live` 有数据。
- 隔离 `2026-06-11` 这种异常废料/成品率。
- 给所有核心指标增加来源和状态：MES、填报、算法、物联网、未同步、异常隔离。
- 明确生产日 07:30 和补录日 09:30 的关系，不混用。

验收：

- 页面不再把有数据展示成 0。
- 异常废料不会进入主屏主指标。
- 用户能看懂每个 0 的含义。

### 第二阶段：MES 终端绑定

目标：让 MES 工序记录能归属到机列和工艺。

任务：

- 新增 `mes_terminal_bindings`。
- 支持 `PC`、`WAN`、设备名、IP、操作员、工艺多线索绑定。
- 管理端提供终端绑定维护入口。
- 未匹配设备进入“待归属清单”。

验收：

- `精整新19辊（WAN）` 可以被绑定或清楚显示为待绑定。
- 机列匹配率从 81.25% 提升到 95% 以上。
- 绑定错误可回滚。

### 第三阶段：卷级线索页

目标：每卷材料有一条完整线索。

任务：

- 新增 `/manage/coils` 或强化现有工厂调度卷材页。
- 后端输出卷级统一 DTO。
- 前端支持搜索、筛选、时间线、异常标记。

验收：

- 搜随行卡能看到完整流转。
- 车间主任只能看本车间。
- MES 和填报分栏显示。

### 第四阶段：手机端 MES 辅助补录

目标：主操少填，不重复填 MES 已有字段。

任务：

- 优先展示 MES 待补录卷。
- 点选后带出客户、合金、规格、工艺、重量。
- 保持字段可编辑。
- 人工修改写入补录层，不覆盖 MES 原始层。

验收：

- 主操能从待补录卷进入填报。
- 无 MES 匹配时仍可手工填。
- 历史记录能看整日录入。

### 第五阶段：物联网能耗接入

目标：机列能耗从独立数据库同步进入系统。

任务：

- 新增只读适配器。
- 新增本地影子表。
- 建立表计到机列映射。
- 汇总到现有能耗页面和大屏。

验收：

- 外部库断开不影响主系统。
- 能耗数可追溯来源。
- 吨电耗可按机列和车间计算。

### 第六阶段：实时生产流转大屏

目标：把 `/manage/live` 做成真正调度墙。

任务：

- 保留 SSE 和 30 秒兜底。
- 增加实时事件流。
- 加入卷级流转、机列矩阵、异常优先级。
- 数字滚动只用于真实变化。

验收：

- 页面连续运行不卡顿。
- 数据变化 1 秒内有视觉反馈。
- 鼠标悬停不消失。
- 无数据、异常、加载、断线都有清楚状态。

### 第七阶段：钉钉和 AI 群助手

目标：让系统主动汇报，不让人反复进后台找数。

任务：

- 钉钉每日推送日报。
- 异常和 MES 延迟主动提醒。
- 群内只读问答。
- 多模态图片识别放到后续灰度。

验收：

- 未绑定钉钉账号不能查数据。
- 车间主任不能查其他车间。
- AI 回复必须带来源和更新时间。
- 群助手不能写生产数据。

## 7. 不做清单

- 不直接删除后工序填报端。
- 不把所有 MES 产量都叫全厂最终产量。
- 不把异常废料直接显示成主指标。
- 不让前端连接 SQL Server 或物联网数据库。
- 不让钉钉群写生产表。
- 不在没有终端绑定证据时强行归属机列。

## 8. 本轮发现的问题清单

### 阻塞

1. `/manage/live` 前端显示 0，但后端实时接口有数据，必须先查字段映射和日期逻辑。
2. `2026-06-11` 实时聚合废料和成品率异常，必须先隔离异常值。
3. 在制材料数据滞后，不能作为实时在制唯一来源。
4. 能耗接口有明细，但页面状态曾显示 0 或同步中，必须查清能源中心的真实取数和加载状态。
5. 合同中心出现“履约率 100% / 延期 269 / 当月交付 0 吨”的矛盾状态，不能直接用于管理决策。
6. 后端接口面达到约 224 个，旧入口和停用入口多，任何清理都必须先做“路由仍被谁调用”的证据链。

### 高风险

1. 终端匹配率只有 81.25%，还存在 `精整新19辊（WAN）` 未匹配。
2. `PC` 和 `WAN` 等通用终端如果误绑定，会造成产量归属错误。
3. 物联网能耗如果前端直连外部库，会带来安全和稳定风险。
4. 卷级接口已有线索但 `line_code=unknown`、`machine_code=null`，如果不补终端绑定，会让“卷到机列”的链路继续断。
5. 库存去向接口返回数值较大，页面单位如果直接写“吨”，可能造成严重误读。
6. 部分前端页面绕过统一 API 模块直接调用接口，会让接口测试和权限测试覆盖不完整。

### 体验问题

1. 页面里的 `0`、`—`、`暂无可信数据` 没有统一解释。
2. 卷级线索和填报明细边界不够清楚。
3. 调度页目前更像汇总页，还不像“行动指挥墙”。
4. 多个预留页面看起来像空页面，用户不知道是没接入、没权限、没数据，还是系统异常。
5. 管理员账号不能代表机台扫码填报体验，填报端还要单独用真实二维码或机台账号复测。
6. 左侧导航只展示核心入口，但可访问页面远多于导航项，详情页、历史页、已停用页需要明确“入口来源”和“是否保留”。
7. `/shift/detail/1` 有 404 资源请求噪声，页面虽能打开，但会让测试人员误判为功能异常。

### 结构优化

1. 需要统一指标 DTO，避免前端各页自己拼字段。
2. 需要统一数据来源标签。
3. 需要统一异常隔离机制。
4. 需要把“数据单位”作为指标字典的一部分，尤其是 kg、吨、卷数、块数。
5. 需要在终端绑定页里显示匹配原因，让用户知道这条 MES 记录为什么归到这台机。
6. 需要建立“页面清单表”：核心页、详情页、隐藏页、已停用页、历史兼容跳转页分开管理。
7. 需要建立“接口清单表”：页面使用、定时任务使用、AI 使用、旧入口使用分开标记，再决定是否删除。

## 9. 评分

- CEO：9.7/10。
- 工程：9.6/10。
- 设计：9.6/10。
- 安全：9.6/10。
- 真实用户：9.7/10。

综合：9.64/10。

## 10. PC 终端匹配、卷级线索、物联网能耗、实时流转大屏方案

这部分对应最新目标：

1. MES 里很多包装工序设备名是 `PC`，但每个 PC 实际应能对应车间、工艺、机列。
2. 废料不再让用户重复填，优先通过投料、下机、合格/入库等数据自动计算。
3. 能耗后续接物联网模块的独立数据库。
4. 前端新增“卷级线索”页面。
5. 调度页改造成实时动态生产流转大屏。

### 10.1 PC 终端匹配设计

不能直接把 `PC` 当机列名，因为 `PC` 是终端名，不是生产设备名。

正确做法是新增一层“终端绑定规则”：

| 字段 | 作用 |
| --- | --- |
| 终端名 | 例如 `PC`、`WAN`、一体机编号、电脑名 |
| MES 车间 | MES 记录里的车间名称 |
| MES 工艺 | MES 记录里的工艺名称，例如包装、剪切、冷轧 |
| 绑定机列 | 数据中枢里的真实机列 |
| 有效时间 | 防止后续电脑换线后历史数据被改错 |
| 匹配置信度 | 高、中、低 |
| 匹配原因 | 为什么这条 MES 记录归到这台机 |
| 是否启用 | 绑定错时可停用，不删历史 |

匹配优先级：

1. MES 记录里有明确机列名，优先按机列名匹配。
2. 没有机列名，但有终端名、车间、工艺，按“终端绑定规则”匹配。
3. 同一个 PC 在同一时间只能绑定一个车间工艺机列组合。
4. 证据不足时进入“待归属”，不能自动猜。
5. 绑定后只影响新计算和可回放结果，不直接改 MES 原始记录。

前端呈现：

1. `/manage/admin/settings` 或新设置页增加“MES 终端绑定”。
2. 显示待归属终端、出现次数、最近工艺、最近卷号、建议机列。
3. 用户确认后才启用绑定。
4. 所有绑定结果都保留“匹配原因”，方便追责。

TDD 验收：

1. `PC + 包装 + 园区在线车间` 能按绑定归到指定机列。
2. 同名 `PC` 在不同车间不会串线。
3. 未绑定 `WAN` 仍进入待归属。
4. 绑定停用后不再继续自动归属。
5. 历史 MES 原始记录不被改写。

### 10.2 废料自动计算设计

废料建议做成“算法结果”，不要继续强迫主操重复填。

推荐公式：

| 场景 | 废料计算 |
| --- | --- |
| 主操有投料、下机 | 废料 = 投料 - 下机 |
| MES 有上机、下机 | 废料 = MES上机重量 - MES下机重量 |
| 包装/入库工序 | 不在这里算废料，包装产量只算最终包装/入库结果 |
| 冷轧道次 | 每卷每道次只记录通过量和道次，不把开坯、中退计入全厂最终产量 |
| 数据异常 | 废料为负、废料率过高时进入异常，不进主屏 |

注意：自动计算不是“永远正确”，而是“默认主口径”。现场人员仍可以补充异常原因。

前端呈现：

1. 填报端显示“系统自动计算废料”，字段不要求必填。
2. 管理端显示废料来源：MES 自动 / 填报自动 / 人工修正。
3. 异常页显示“为什么被判异常”，例如投料 4.6 吨、废料 4 吨。

TDD 验收：

1. 有投料和下机时自动算废料。
2. 缺任一字段时不乱算。
3. 废料为负进入异常。
4. 废料率超过阈值进入异常。
5. 人工修正不覆盖原始 MES 值，只作为对照。

### 10.3 物联网能耗独立数据库接入

物联网能耗库不能让前端直连。

正确边界：

1. 后端只读连接物联网数据库。
2. 定时同步到数据中枢本地投影表。
3. 管理端只读本地投影表。
4. 外部库异常时，页面显示“物联网同步延迟”，不影响登录和主系统健康。

建议新增本地投影表：

| 表 | 作用 |
| --- | --- |
| `iot_energy_meter_readings` | 原始电表/气表/水表读数投影 |
| `iot_energy_sync_runs` | 每次同步记录 |
| `iot_energy_meter_bindings` | 表计和车间/机列/能耗类型绑定 |
| `energy_metric_snapshots` | 按业务日、班次、车间汇总后的能耗快照 |

能耗主口径：

1. 有物联网数据时，算法能耗优先取物联网投影。
2. 电工填报保留为对照和纠偏。
3. 没有产量分母时，吨耗显示“无产量分母”，不能显示真实 0。
4. 物联网同步延迟时，页面显示最近更新时间。

TDD 验收：

1. 外部库失败不影响 `/readyz`。
2. 物联网同步失败有同步日志。
3. 同一表计重复同步不会重复计入。
4. 电工填报与物联网值并列显示。
5. 吨耗分母为 0 时不显示 0 吨耗。

### 10.4 卷级线索页面

新增页面建议：`/manage/coils`，中文名“卷级线索”。

这个页面不等同于填报明细。它主要回答：

1. 这卷现在在哪个车间？
2. 走过哪些工艺？
3. 当前工艺是否到达？
4. 对应哪台机列？
5. MES 是否已经有产量？
6. 是否还需要人工补录？
7. 有没有异常或缺口？

页面核心模块：

| 模块 | 数据来源 |
| --- | --- |
| 卷号搜索 | MES 随行卡号、批号、卷号 |
| 卷生命周期 | `mes_workshop_process_records` |
| 当前所在工序 | MES 最新过站记录 |
| 机列匹配结果 | 机列名匹配 + 终端绑定规则 |
| 重量对照 | MES 上机/下机/包装 + 填报补录 |
| 冷轧道次 | MES 工艺记录 + 人工补充道次 |
| 待补录提示 | MES 有记录但本地缺必要补录 |
| 异常提示 | 重量异常、机列未匹配、工艺未到达 |

前端交互：

1. 默认显示当天业务日卷材。
2. 支持按卷号、随行卡、客户名、合金、规格、工艺搜索。
3. 只显示“需要处理”的优先队列，避免用户被海量记录淹没。
4. 每条卷显示“MES 已有字段”和“需要人工补录字段”。
5. 字段不锁死，现场仍可改。

TDD 验收：

1. 有 MES 记录的卷能搜到。
2. PC 终端绑定后能显示对应机列。
3. 未绑定终端显示待归属。
4. 冷轧多道次按顺序展示。
5. 没有 MES 记录时允许手工补录。

### 10.5 实时动态生产流转大屏

`/manage/live` 要从“汇总页”升级为“指挥墙”。

大屏核心结构：

1. 顶部：全厂总产量、MES 包装产量、内勤入库填报、过站下机、总电耗、吨耗、未填、异常。
2. 中部：生产流转链路，按铸锭、铸轧、热轧、冷轧、退火、拉矫、精整、剪切、包装流动。
3. 右侧：实时事件流，显示 MES 新过站、填报提交、能耗同步、异常新增、终端待绑定。
4. 下方：全厂机列矩阵，像股票一样数字跳动，但只对真实变化补间动画。
5. 底部：系统状态，显示登录、MES、物联网、填报、算法、同步延迟。

实时规则：

1. SSE 正常时，只更新变化卡片。
2. SSE 异常时，每 30 秒快照兜底。
3. 页面刚打开先显示“加载中”，不要先显示 0。
4. 真实 0、未同步、异常隔离要用不同状态。
5. 数字动画控制在 1 秒内，不加重型光效，保证页面不卡。

TDD 验收：

1. `/api/v1/aggregation/live` 有数时，页面不能长期显示 0。
2. 页面打开 12 秒内关键 KPI 与接口一致。
3. SSE 中断时快照兜底可用。
4. 机列矩阵数量与接口一致。
5. 未匹配 PC/WAN 显示在待处理列表。

### 10.6 推荐执行顺序

第一阶段：终端绑定和数据可信度。

1. 建终端绑定规则和待归属清单。
2. 修废料自动计算和异常隔离。
3. 统一实时页的加载中、真实 0、未同步、异常状态。

第二阶段：卷级线索页。

1. 后端新增卷级查询 DTO。
2. 前端新增 `/manage/coils`。
3. 接入搜索、卷生命周期、机列匹配、待补录。

第三阶段：物联网能耗投影。

1. 只读连接物联网库。
2. 写入本地投影表。
3. 能耗页和实时页并列显示物联网值与电工填报值。

第四阶段：实时流转大屏。

1. 重构 `/manage/live` 信息结构。
2. 接入事件流和数字跳动。
3. 做大屏横屏、手机屏幕模式适配。

第五阶段：灰度和清理。

1. 与人工填报对账 7 天。
2. 清理不再需要的后工序重复填报字段。
3. 保留人工补录和异常审核，不直接废掉填报端。

### 10.7 五视角评分

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.8 | 把 MES 真值、人工补录、实时指挥墙放到一条业务线上 |
| 工程 | 9.7 | 先终端绑定，再卷级页面，再物联网，顺序稳 |
| 设计 | 9.7 | 页面按“先看问题，再查卷，再处理”组织，比堆表格清楚 |
| 安全 | 9.8 | 外部库只读同步，本系统不让前端直连 |
| 真实用户 | 9.8 | 能减少重复扫码、重复填重量、找不到卷的痛点 |

综合：9.76/10。

结论：计划方向可执行，但必须把“数据可信度修复”提前到第一阶段，否则后续大屏和卷级页面会建立在不稳的数据上。

## 11. 下一步

建议下一步进入第一阶段，只做三件事：

1. 修复 `/manage/live` 前端 0 值映射问题。
2. 给异常废料/异常成品率加隔离规则。
3. 查清 `PC`、`WAN`、一体机字段在 MES 原始 payload 里到底有哪些可绑定线索。
4. 给 `/manage/energy`、`/manage/factory/destinations`、`/manage/contracts` 增加接口与页面一致性测试。
5. 用真实机台账号或二维码复测 `/entry` 和 `/entry/history`，确认补录流程不是只在管理端“看起来可用”。
6. 以 `docs/superpowers/audits/2026-06-11-page-api-coverage-matrix.md` 为底表，先标记“核心、详情、隐藏、停用、可合并”，再做删除或合并。
7. 以 `docs/superpowers/audits/2026-06-11-backend-architecture-risk-map.md` 和 `docs/superpowers/audits/2026-06-11-core-api-contract-test-plan.md` 为底表，先给核心接口写字段契约测试，再动前端大屏和卷级页面。

完成这三件事后，再做终端绑定表和卷级线索页面。

## 12. 核心接口字段契约测试计划

已新增 `docs/superpowers/audits/2026-06-11-core-api-contract-test-plan.md`。

这份计划把下一阶段测试重点锁定在 7 类接口：

1. `/api/v1/aggregation/live`：保护实时大屏、昨日报表、填报明细、车间看板。
2. `/api/v1/mes/supplement-readiness`：保护 PC、WAN、一体机到机列的匹配判断。
3. `/api/v1/factory-command/coils`：保护卷级线索页。
4. `/api/v1/factory-command/destinations`：保护库存去向和单位口径。
5. `/api/v1/energy/summary`：保护能耗、吨耗、未来物联网接入。
6. `/api/v1/mobile/current-shift` 和 `/api/v1/mobile/mes-pending-supplements`：保护手机填报和 MES 辅助补录。
7. `/api/v1/assistant/live-probe`：保护 AI 助手只读健康检查。

本轮确认已有测试覆盖不算少，但还缺“字段契约”和“页面映射契约”。下一阶段应该优先补 6 个 TDD 用例：

1. 后端有 MES 包装产量时，实时大屏不能显示 0。
2. 异常废料和异常成品率必须进入 `data_quality`，不能直接上主屏。
3. 有能耗但无产量分母时，吨耗为 `None`，前端显示“无产量分母”。
4. 库存去向 `tons` 必须确认是吨，不是 kg。
5. PC/WAN/未知一体机必须进入终端绑定或待归属，不自动归到任意机列。
6. 手机 MES 待补录必须按 09:30 业务窗口，字段可编辑，MES 缺失不阻断手填。

五视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 先保护最影响决策的数字可信度 |
| 工程 | 9.7 | 用小测试保护大改造，风险可控 |
| 设计 | 9.6 | 明确 0、未同步、异常、待绑定的状态语言 |
| 安全 | 9.7 | 明确外部 MES 和物联网库只读同步，前端不直连外部库 |
| 真实用户 | 9.6 | 能减少看错数和重复填报，但还要真实二维码回归 |

综合：9.66/10。

## 13. 前端体验与页面保留审计

已新增 `docs/superpowers/audits/2026-06-11-frontend-experience-retention-review.md`。

本轮用管理员登录线上管理端，只读抽查了核心页面：

1. `/manage/live`
2. `/manage/today`
3. `/manage/production`
4. `/manage/fill-details`
5. `/manage/energy`
6. `/manage/workshop-dashboard`
7. `/manage/admin/settings`
8. `/manage/factory/destinations`
9. `/manage/contracts`
10. `/manage/inventory`
11. `/manage/attendance`

关键证据：

1. `/api/v1/aggregation/live?business_date=2026-06-11` 返回 MES 包装产量 `177.61` 吨，`finished_inbound_output=0`，MES 同步为 `sqlserver/fresh`。
2. 同接口仍出现异常运行时数据：`input=106490.53`、`scrap=105145.3`、`yield_rate=1.24`，必须隔离后再上主屏。
3. `/manage/energy` 有 6 条能耗记录，电耗 `8907 kWh`、气耗 `18939 m³`，但产量分母为 0，单吨能耗不能显示成真实 0。
4. `/api/v1/mes/supplement-readiness?limit=100` 显示机台匹配率 `83.33%`，通用终端 `64` 条，未匹配集中在 `精整新19辊（WAN）`。
5. `/manage/contracts` 显示活跃合同 274、履约率 100%、延期 269、本月交付 4444 吨，指标口径互相冲突。
6. `/manage/factory/destinations` 显示在制 `330735.5`、1373 卷，单位需要确认，不能直接当吨展示。
7. 实时页因为 SSE 长连接，自动化 QA 不能用 `networkidle` 作为页面完成条件，应改为等待 `data-testid="manage-live"` 和关键指标卡稳定。

本轮页面保留建议：

| 页面 | 建议 | 原因 |
| --- | --- | --- |
| `/manage/live` | 保留并优先打磨 | 是生产指挥墙核心入口 |
| `/manage/today` | 保留 | 是日报入口，但要强化数据来源和日期口径 |
| `/manage/production` | 保留但与 today 分工 | 避免和日报重复 |
| `/manage/fill-details` | 保留为人工填报明细 | 不要变成卷级主线页 |
| `/manage/energy` | 保留 | 能耗数据已有，但要修分母状态 |
| `/manage/workshop-dashboard` | 保留 | 车间主任和管理端都需要 |
| `/manage/admin/settings` | 保留 | 可作为系统健康和配置入口 |
| `/manage/factory/destinations` | 合并到实时大屏或卷级线索 | 有数据但入口和单位口径不清 |
| `/manage/contracts` | 先隐藏/修公式 | 当前指标不能支撑决策 |
| `/manage/inventory` | 合并到卷级线索或库存去向 | 当前为空壳 |
| `/manage/attendance` | 移到系统预留区 | 等钉钉接入后再提升 |

前端下一步推荐：

1. 先统一 `0`、`—`、`暂无可信数据`、`同步中`、`待同步` 的含义。
2. 再做页面合并和隐藏，不直接硬删。
3. 新增“卷级线索页”，不要继续往填报明细页塞 MES 主线。
4. 实时大屏重构为“优先处理 + 机列矩阵 + 关键指标 + 系统状态”，数字跳动只用于真实新值。

三视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 能把老板每天真正要看的可信指标收敛出来 |
| 工程 | 9.6 | 明确了页面、接口、测试和 SSE 验收边界 |
| 设计 | 9.6 | 明确下一轮先做状态语言和行动优先级，而不是堆视觉效果 |

综合：9.63/10。

## 14. 第一阶段 TDD 修复作业单

已新增 `docs/superpowers/audits/2026-06-11-phase1-tdd-remediation-backlog.md`。

这份作业单把第一阶段压缩成 6 个可以直接施工的问题域：

1. 实时大屏 0 值状态：修复“加载中/未同步被显示为 0”的误导。
2. 异常废料和成品率隔离：异常值进入 `data_quality`，不直接上主屏。
3. 能耗分母为 0：有能耗但无产量分母时，吨耗显示“无产量分母”，不能显示真实 0。
4. 库存去向单位：确认 `tons` 真的是吨，疑似 kg 必须折算或带单位说明。
5. 合同页指标矛盾：合同量缺失时不能显示履约率 100%。
6. MES PC/WAN 机列匹配：PC/WAN/一体机不能无证据自动归属机列。

对应执行门禁：

1. 先写失败测试，再改代码。
2. 每次只改一个问题域。
3. 修完跑对应后端测试、前端测试、浏览器抽查。
4. 实时页 QA 不使用 `networkidle`，改等 `data-testid="manage-live"` 和关键指标稳定。
5. 不删除页面、接口、数据表，不直连外部数据库，不自动误归属机列。

本轮进一步定位到的关键文件：

| 问题域 | 主要代码 | 主要测试 |
| --- | --- | --- |
| 实时大屏状态 | `frontend/src/utils/liveDashboardPhase2.js`、`frontend/src/views/manage/live/LiveDashboardPage.vue` | `frontend/tests/manageLivePhase2.test.js` |
| 异常废料/成品率 | `backend/app/services/realtime_service.py` | `backend/tests/test_realtime_service.py`、`backend/tests/test_realtime_service_contract.py` |
| 能耗分母 | `backend/app/services/energy_service.py`、`frontend/src/views/energy/EnergyCenter.vue`、`frontend/src/utils/stitchManageSurface.js` | `backend/tests/test_energy_summary.py` |
| 库存单位 | `backend/app/services/factory_command_service.py` | `backend/tests/test_factory_command_service.py` |
| 合同矛盾 | `backend/app/routers/contracts.py`、`frontend/src/views/contracts/ContractsCenter.vue` | `backend/tests/test_inventory_contract_routes.py` |
| MES 机列匹配 | `backend/app/services/mes_supplement_readiness_service.py`、`frontend/src/views/manage/admin/SystemSettingsPage.vue` | `backend/tests/test_mes_supplement_readiness_service.py` |

五视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.8 | 第一阶段聚焦最影响决策可信度的问题 |
| 工程 | 9.7 | 文件、测试、验收边界清楚，适合 TDD 执行 |
| 设计 | 9.7 | 先统一状态语言，避免用户误读 |
| 安全 | 9.8 | 不删数据、不直连外部库、不误绑定机列 |
| 真实用户 | 9.7 | 修完后用户更能分清真 0、未同步、异常、加载中 |

综合：9.74/10。

## 15. 登录权限与运行健康审计

已新增 `docs/superpowers/audits/2026-06-11-auth-permission-health-audit.md`。

本轮只读验证了线上登录、健康检查、管理端实时页和移动入口相关路径。

关键证据：

1. `/healthz`、`/api/v1/healthz`、`/readyz` 均返回 200。
2. `/api/v1/readyz` 返回 404，健康检查路径还没有完全统一。
3. `/readyz` 显示 MES 同步为 `sqlserver/fresh`，`lag_seconds=0`，说明线上已切到 SQL Server 同步链路。
4. 登录接口返回 200，并同时返回 `access_token` 和 `refresh_token`。
5. 前端只保存 `access_token`，401 时直接退出登录，没有自动续期。
6. `/manage/live` 单页等待 12 秒后，页面显示 `MES包装产量 284.84 吨`，接口同值为 `factory_total.packaging_output=284.84`，说明当前不是后端无数据，而是验收等待方式和加载状态需要规范。

新增到第一阶段的修复门禁：

1. 增加 `/api/v1/readyz`，避免监控脚本误报。
2. 前端接入 refresh token 自动续期，减少现场“登录不上”的误解。
3. 管理端账号访问 `/entry` 时显示友好提示或隐藏“操作员端”入口。
4. QA 规则明确：实时页不等 `networkidle`，要等快照接口和关键 KPI 卡片。

五视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 解决登录误解和健康误报，能减少现场阻塞 |
| 工程 | 9.7 | 修复边界小，测试路径清晰 |
| 设计 | 9.5 | 还要补友好权限页和加载状态 |
| 安全 | 9.7 | refresh token 接入要注意只存前端会话，不暴露外部库 |
| 真实用户 | 9.6 | 能明显减少“登录不上”和“刚打开都是 0”的困惑 |

综合：9.64/10。

## 16. 设置、主数据、MES 终端绑定审计

已新增 `docs/superpowers/audits/2026-06-11-settings-terminal-binding-audit.md`。

本轮只读验证了：

1. `/manage/admin/settings`
2. `/manage/alias`
3. `/manage/admin/users`
4. `/manage/master`
5. `/api/v1/mes/supplement-readiness?limit=100`
6. `/api/v1/master/aliases?entity_type=equipment&limit=100`
7. `/api/v1/master/equipment?limit=200`

关键证据：

1. 设置页能显示 MES 补录就绪：机台匹配 `83%`、下机重量 `94%`、冷轧道次 `100%`、09:30窗口 `109`。
2. 线上 `generic_terminal_count=64`，说明大量记录是 `PC/电脑/一体机` 这类通用终端。
3. 线上 `unmatched_count=6`，未匹配设备集中在 `精整新19辊（WAN）`。
4. 线上设备别名接口 `total=0`，当前没有设备别名数据。
5. 后端 `resolve_mes_machine_binding()` 会先把 `PC/电脑/一体机` 判定为 `generic_mes_terminal`，这一步发生在别名匹配之前。

结论：

不能用现有“别名映射”硬做 PC 绑定。别名映射只适合名称标准化，不适合表达“终端 + 车间 + 工艺 + 生效时间 + 机列”的业务规则。

推荐新增：

1. 只读“待绑定终端”清单。
2. `mes_terminal_machine_bindings` 结构化绑定表。
3. 设置页三栏：通用终端、未匹配设备、已绑定规则。
4. 匹配算法按“明确设备名、设备别名、终端上下文绑定、工艺推断、待归属”的顺序执行。

三视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 解决 PC 归属才会让机列级大屏可信 |
| 工程 | 9.8 | 新表比复用别名表更稳，可测试可回滚 |
| 设计 | 9.6 | 设置页要从百分比变成可处理清单 |

综合：9.7/10。

## 17. 卷级线索、MES 辅助补录与实时生产流转大屏专项方案

已新增 `docs/superpowers/audits/2026-06-11-coil-trace-mes-supplement-command-screen-plan.md`。

本轮按 `plan` 和 `office-hours` 重新梳理了以下问题：

1. 机列匹配还不够稳，尤其 MES 设备名为 `PC`、`电脑`、`一体机`、`WAN` 时，不能直接知道是哪台机。
2. 每个 PC/终端应结合 MES 车间、MES 工艺、生效时间，绑定到真实机列。
3. 废料可以自动计算，但必须有安全阈值，不能让负数或异常大值污染主屏。
4. 能耗计划要接物联网模块独立数据库，但前端不能直连，后端应只读同步到本地影子表。
5. 管理端需要新增 `/manage/coils` 卷级线索页，集中展示随行卡、批号、客户、合金、规格、机列、工艺、补录、异常、能耗参考。
6. `/manage/live` 应从“实时指标页”升级为“实时动态生产流转大屏”，展示工艺路线、机列矩阵、卷级事件流、系统状态和轻量数字跳动。

本轮核心代码证据：

1. `backend/app/services/mes_machine_match_service.py` 中 `resolve_mes_machine_binding()` 会先把 `PC` 判定为 `generic_mes_terminal`，因此普通设备别名不能解决 PC 归属。
2. `backend/app/models/mes.py` 已有 `mes_coil_snapshots`、`mes_workshop_process_records`、`mes_stock_records`、`coil_flow_events`，可以支撑卷级线索。
3. `backend/app/routers/factory_command.py` 已有卷列表和卷流向接口，但字段还不够管理端使用。
4. `frontend/src/views/mobile/CoilEntryWorkbench.vue` 已有 MES 待补录、扫码兜底、MES 参考值、人工可改和废料自动计算。
5. `frontend/src/views/manage/live/LiveDashboardPage.vue` 已有 SSE 和 30 秒快照兜底，适合在现有基础上升级为实时流转墙。
6. `backend/app/services/energy_service.py` 当前能耗主链路来自导入、手机电工填报和内勤/专项填报，还没有物联网独立库适配层。

推荐执行顺序：

1. 先做终端绑定只读审计，不改历史归属。
2. 再新增 `mes_terminal_machine_bindings` 结构化绑定表和匹配测试。
3. 再增强手机 MES 待补录，让 PC 记录进入“待确认”，不是直接消失。
4. 再新增 `/manage/coils` 卷级线索页。
5. 再接物联网能耗只读适配器和本地影子表。
6. 最后重构 `/manage/live` 为实时生产流转大屏。

五视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.8 | 把“哪卷在哪、哪个数可信、谁要处理”变成核心价值 |
| 工程 | 9.7 | 先补绑定和测试，再做页面，风险可控 |
| 设计 | 9.7 | 新页面能减少用户来回查表，实时墙更像指挥系统 |
| 安全 | 9.8 | 外部库只读、前端不直连、绑定可停用可追溯 |
| 真实用户 | 9.7 | 能减少重复扫码和重复填报，但还要现场二维码回归 |

综合：9.74/10。

## 18. 终端绑定、卷级线索与实时生产流转大屏执行计划

已新增 `.omx/plans/2026-06-11-terminal-binding-coil-realtime-screen.md`。

本轮根据最新业务补充，把方案从“方向正确”进一步压成“可进入 TDD 的执行计划”：

1. `PC`、`电脑`、`一体机` 这类 MES 设备名必须被当成终端，不是机列。
2. 每个终端必须结合 `MES 车间 + MES 工艺 + 生效时间` 绑定到真实机列和工艺。
3. 废料按 `MES 上机量 - MES 下机量` 自动计算，但负数、超阈值、缺字段都进入异常审核，不进入主屏汇总。
4. 物联网能耗独立库只能后端只读同步到本地影子表，前端不直连外部库。
5. 新增 `/manage/coils` 卷级线索页，清楚展示随行卡、批号、客户、合金、规格、机列、工艺、补录、异常、能耗参考。
6. `/manage/live` 后续改造成实时动态生产流转大屏，保留 SSE 和 30 秒快照兜底，只对真实变化做轻量数字跳动。

推荐执行顺序：

1. 终端绑定只读审计。
2. 新增终端绑定表和匹配测试。
3. 废料自动计算安全化。
4. 新增卷级线索页。
5. 接入物联网能耗只读影子表。
6. 改造实时动态生产流转大屏。

五视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.8 | 把“哪卷在哪、哪个数可信、谁处理”变成核心价值 |
| 工程 | 9.8 | 先绑定和测试，再页面和大屏，风险可控 |
| 设计 | 9.7 | 卷级线索页减少来回查表，大屏更像调度工具 |
| 安全 | 9.8 | 外部库只读、本地影子表、前端不直连 |
| 真实用户 | 9.8 | 减少重复扫码、重复录重量、找不到卷的痛点 |

综合：9.78/10。

## 19. 前端信息架构与页面保留审计

已新增 `docs/superpowers/audits/2026-06-11-frontend-information-architecture-review.md`。

本轮从路由、导航、页面文件、API 入口四个角度继续审查管理端信息架构。

关键证据：

1. `frontend/src/router/index.js` 当前有 `143` 个 path、`78` 个命名路由。
2. `frontend/src/config/manage-navigation.js` 当前有 `13` 个导航项。
3. `frontend/src/views` 当前有 `84` 个 Vue 页面文件。
4. `frontend/src/api` 当前有 `24` 个 API 模块。
5. 真实文件系统里 `frontend/src/views/factory-command` 只剩 `DestinationScreen.vue` 和 `FactoryCommandShell.vue`，没有正式卷级线索页。
6. 后端和 API 已有 `GET /factory-command/coils` 与 `GET /factory-command/coils/{coil_key}/flow`，适合先新增 `/manage/coils` 最小可用页。
7. `reports/LiveDashboard.vue` 仍有 4029 行，属于高风险旧大屏文件，删除前必须做依赖追踪。
8. 合同、库存、按卷补录页仍有直接 `api.get/post` 调用，后续应逐步迁移到统一 API 模块。

页面保留建议：

| 类型 | 页面 |
| --- | --- |
| 核心保留 | `/manage/live`、`/manage/today`、`/manage/production`、`/manage/fill-details`、`/manage/energy`、`/manage/workshop-dashboard`、`/manage/alerts`、`/manage/admin/settings` |
| 新增核心 | `/manage/coils` |
| 可合并/降级 | `/manage/factory/destinations`、`/manage/inventory`、`/manage/reports`、`/manage/attendance`、`/manage/contracts` |
| 详情保留 | `/attendance/detail/:employeeId/:businessDate`、`/shift/detail/:id`、质量详情、差异详情 |
| 停用兼容 | `/imports/*`、`/review/*`、模板中心旧入口、旧 `/mobile/*` 跳转 |

推荐主导航最终收敛为：

1. 实时调度
2. 昨日报表
3. 生产分析
4. 卷级线索
5. 填报明细
6. 能耗中心
7. 异常处理
8. 系统设置

执行顺序：

1. 先新增 `/manage/coils`，不删除旧页面。
2. 再统一 `真实 0 / 未同步 / 加载中 / 异常隔离 / 无产量分母` 状态语言。
3. 再灰度合并库存、报表、考勤、合同等弱业务页面。
4. 最后对旧入口和旧大文件做依赖追踪，确认无业务路径后再删除。

三视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 把页面从“多而散”收敛到真实业务主线 |
| 工程 | 9.7 | 先新增、再合并、最后删除，风险可控 |
| 设计 | 9.6 | 用户路径更清楚，但还要配合浏览器截图继续打磨 |

综合：9.67/10。

## 20. 页面、接口、数据表链路覆盖审计

已新增 `docs/superpowers/audits/2026-06-11-page-api-dataflow-coverage-review.md`。

本轮继续从“页面 -> 前端 API -> 后端路由 -> 服务 -> 数据表 -> 测试”这条链路做只读审计。

关键证据：

1. `backend/app/main.py` 第 291 到 325 行挂载了 `auth/users/master/dashboard/attendance/production/mobile/reports/mes/factory-command/energy/inventory/contracts/realtime/ai` 等主要接口。
2. `frontend/src/api` 当前有 `24` 个 API 模块，覆盖实时、日报、能耗、MES、工厂指挥、移动端、主数据、用户等链路。
3. `realtime_service.py` 有 2457 行，是实时大屏、填报明细、缺报、车间看板的共同核心，任何改动都必须 TDD。
4. `factory_command_service.py` 有 1609 行，支撑卷级线索、库存去向、工厂指挥，是新增 `/manage/coils` 的主要后端基础。
5. `energy_service.py` 负责导入、机列能耗、手机填报、内勤专项和包装入库分母，后续物联网能耗库必须从这里进入统一输出。
6. 合同页和库存页还直接调用 `/contracts/*`、`/inventory/*`，后续应先迁移到统一 API 模块，再决定是否降级或合并。
7. 后端和前端测试数量不少，但缺 `/manage/coils` 正式页面测试和跨页面状态语言测试。

页面链路结论：

| 页面 | 主接口/服务 | 风险 |
| --- | --- | --- |
| `/manage/live` | `/aggregation/live`、`realtime_service` | 核心页，字段契约必须强保护 |
| `/manage/today` | `/dashboard/timeseries`、`/aggregation/live` | 容易出现业务日口径不一致 |
| `/manage/fill-details` | `/aggregation/live/fill-details`、`/aggregation/live/mes-fill-gaps` | 应专注人工填报明细，不要承担卷级主线 |
| `/manage/energy` | `/energy/summary`、`energy_service` | 物联网接入必须后端只读影子表 |
| `/manage/workshop-dashboard` | `/dashboard/workshop-director`、MES 扩展接口 | 车间主任权限必须严格隔离 |
| `/manage/admin/settings` | `/mes/supplement-readiness` | 适合承载 PC/WAN 待绑定终端清单 |
| `/manage/contracts` | `/contracts/summary` | 口径未稳前不建议主导航强化 |
| `/manage/inventory` | `/inventory/summary` | 更适合合并到卷级线索 |

新增风险分级：

1. **P1：缺页面-接口-表字段统一契约。** 后端有数，前端仍可能显示 0、空或暂无可信数据。
2. **P1：缺 `/manage/coils` 正式页面。** MES 卷级数据已有，但用户没有清晰入口。
3. **P1：`realtime_service.py` 过大。** 改实时聚合容易影响多个页面。
4. **P2：合同和库存页面直接调 API。** 错误处理、超时、权限和测试不统一。
5. **P2：钉钉、导入、模板、考勤预留仍有痕迹。** 应保留兼容和权限保护，但前端降级。

推荐下一步：

1. 先补 `/aggregation/live`、`/energy/summary`、`/factory-command/coils`、`/mes/supplement-readiness` 字段契约测试。
2. 再新增 `/manage/coils` 最小可用页。
3. 再统一核心页面状态语言。
4. 最后灰度合并库存、报表、考勤、合同等弱业务页面。

五视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 找到页面多但业务主线不集中的根因 |
| 工程 | 9.8 | 接口、服务、模型、测试链路已定位，可安全施工 |
| 设计 | 9.6 | 用户路径可收敛到卷级、调度、异常、能耗 |
| 安全 | 9.7 | 保留权限边界，旧接口不硬删，外部数据不前端直连 |
| 真实用户 | 9.7 | 减少找页面、看空页面、看错 0 的困惑 |

综合：9.7/10。

## 21. 测试体系与 QA 验收门禁审计

已新增 `docs/superpowers/audits/2026-06-11-testing-qa-gates-review.md`。

这轮审计的重点不是“有没有测试”，而是“测试能不能挡住真实业务问题”。结论是：项目测试资源比较多，但还要按页面、接口字段、数据口径、角色权限、浏览器实测来重新组织上线门禁。

关键证据：

1. `backend/tests` 下有 214 个测试文件，覆盖实时聚合、能耗、MES 同步、MES 补录、机列匹配、日报、手机填报、权限和安全。
2. `frontend/tests` 下有 81 个测试文件，覆盖实时大屏、日报、生产页、能耗页、填报明细、异常页、设置页、导航、合同、库存和按卷填报。
3. `frontend/e2e` 下有 52 个 Playwright 文件，可用于登录、导航、移动端和核心页面浏览器验收。
4. `backend/pytest.ini` 默认跑 `tests`，并排除 `frontend_contract` 标记，说明后端已有基础测试门禁。
5. `frontend/playwright.config.js` 会自动启动后端和前端测试服务，并支持已有线上环境复用。
6. `.github/workflows/ci.yml` 已包含后端测试、前端安全审计、构建、组合烟测、健康检查、登录检查和 Playwright smoke。

当前缺口：

| 缺口 | 影响 |
| --- | --- |
| 缺 `/manage/coils` 正式页面测试 | 新增卷级线索页后，容易出现页面能打开但字段对不齐 |
| 缺跨页面状态语言测试 | `0`、未同步、无产量分母、异常隔离容易混用 |
| 缺终端绑定全链路测试 | PC -> 车间 -> 工艺 -> 机列匹配不稳时，前端可能误判机列 |
| 缺合同/库存降级回归测试 | 页面合并或弱化时，可能误删仍被使用的接口 |
| 浏览器测试不宜依赖 `networkidle` | 实时流页面长期连接时，会误判为超时 |

推荐门禁：

1. 后端核心门禁：实时聚合、能耗、工厂指挥、MES 补录、机列匹配。
2. 前端管理页门禁：实时大屏、昨日报表、生产页、能耗页、填报明细、导航。
3. 手机端门禁：扫码进入、按卷补录、历史填报、缺报提醒、字段可编辑。
4. 浏览器门禁：登录、导航、关键页面加载、无 401/403 误伤、无 `network error`。
5. 发版门禁：后端全量测试、前端测试、前端构建、Playwright smoke、线上健康检查。

五视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 能把“页面显示错数”这类业务风险提前挡住 |
| 工程 | 9.8 | 测试资源充足，下一步要把门禁和业务链路绑定 |
| 设计 | 9.6 | 页面验收会更关注状态语言和用户路径 |
| 安全 | 9.7 | 登录、权限、外部数据和健康检查能进入固定门禁 |
| 真实用户 | 9.7 | 能减少“能打开但不好用、看不懂、数字不可信”的情况 |

综合：9.7/10。

## 22. 浏览器体验与核心主线风险审计

已新增 `docs/superpowers/audits/2026-06-11-browser-core-flow-experience-review.md`。

这轮继续把“代码里看起来有”和“浏览器里真的能用”分开验证。结论是：后端 MES、机列匹配、工厂指挥和手机待补录测试基础较稳；管理端壳浏览器门禁首次失败，定位后已补齐 E2E mock 并复跑通过。

关键证据：

1. 前端测试命令跑完 `619` 个测试，全部通过，覆盖实时页、昨日报表、生产页、能耗页、填报明细、手机按卷录入、网络错误文案和实时流兜底。
2. 后端主线测试跑完 `54` 个测试，全部通过，覆盖 MES 补录准备度、MES 机列匹配、工厂指挥服务/路由和手机 MES 待补录。
3. Playwright 管理端壳首次测试 `5` 个用例中 `3` 个通过、`2` 个失败。
4. 失败截图显示浏览器停在“管理员登录”页，不是停在管理端页面。
5. 后端测试日志里出现 `/api/v1/mes/supplement-readiness?limit=100` 返回 `401 Unauthorized`。
6. 根因是 `frontend/e2e/helpers/review-mocks.js` 漏 mock `/api/v1/mes/supplement-readiness`，管理员测试登录后先落到系统设置页，未 mock 请求触发 401 登出。
7. 已补齐 E2E mock，复跑 `npx playwright test e2e/manage-shell.spec.js --reporter=line --workers=1`，结果 `5` 个全部通过。
8. 当前真实路由有 `/manage/live`、`/manage/today`、`/manage/production`、`/manage/fill-details`，但没有 `/manage/coils`。
9. 当前真实文件系统里 `frontend/src/views/factory-command` 只剩 `FactoryCommandShell.vue` 和 `DestinationScreen.vue`，不能把旧 CodeGraph 索引里的卷级页面当作现存页面。
10. 生产站点 `/healthz`、`/api/v1/healthz`、`/readyz` 返回 `200`，说明服务本身可访问。
11. 生产站点 `/api/v1/readyz` 返回 `404`，健康检查路径仍未完全统一。
12. 生产真实管理员登录 smoke 停在 `/login`，`/api/v1/auth/login` 返回 `400`；后端代码显示 `400` 对应用户名或密码校验失败，账号停用才会是 `403`。
13. 已在本地代码补齐 `/api/v1/readyz` 兼容路由，复跑 `backend/tests/test_health.py` 结果 `14` 个全部通过；部署后需复验生产 `/api/v1/readyz`。
14. 已在 `/api/v1/mes/supplement-readiness` 增加 `generic_terminals`，把 `PC`/一体机泛化终端样例和原始 payload 线索返回给管理端。
15. 系统设置页 MES 补录卡片已展示“PC 终端待绑定”数量和前 3 条线索，作为后续绑定规则的入口证据。
16. 已新增 `mes_terminal_bindings` 结构化绑定表、`0038_mes_terminal_bindings` 迁移、后端 CRUD 接口和 `mes_terminal_binding` 匹配来源。
17. 已验证 PC 有结构化绑定时可归到真实机列；没有绑定时仍保持 `generic_mes_terminal`，不自动乱归。
18. 已新增 `/manage/mes-terminal-bindings` 首版前端维护页，并在系统设置页补充“终端绑定”入口。
19. 已复跑前端相关测试，`623` 个通过；已复跑后端相关测试，`34` 个通过。
20. 已复跑前端生产构建，`MesTerminalBinding` 页面成功进入构建产物。
21. 已补充管理端浏览器用例，`npx playwright test e2e/admin-surface.spec.js --reporter=line --workers=1` 结果 `12` 个全部通过，覆盖从系统设置页进入终端绑定页。

新增风险分级：

1. **P1：生产管理员真实登录 smoke 未通过。** 服务是活的，但生产库账号密码记录需要按安全流程修复后再验收。
2. **P1：缺正式 `/manage/coils` 卷级线索页。** 后端和 API 已有卷级能力，但管理端没有清晰入口。
3. **P1：MES 设备名 `PC` 不能直接当机列。** “终端 + 车间 + 工艺 + 有效期”绑定规则、后端接口和首版前端维护入口已完成；仍需生产部署后复验。
4. **P2：CodeGraph 索引和当前文件系统存在差异。** 后续审计必须交叉确认，不能只看索引。
5. **P2：浏览器测试偏慢。** 要拆成快速 smoke 和深度 e2e，避免上线前被跳过。
6. **已处理：`/api/v1/readyz` 兼容入口缺失。** 本地代码和测试已补齐，等待部署后线上复验。
7. **已推进：PC 泛化终端线索可见化。** 本地代码和前端卡片已补齐。
8. **已推进：PC 结构化绑定闭环。** 表、迁移、接口、匹配逻辑、首版前端维护页和测试已补齐；待生产部署复验和样例一键带入。

优化后的执行顺序：

1. 先修复生产管理员账号登录记录，再跑真实登录 smoke，让 `/manage/today`、`/manage/live`、`/entry` 在真实线上环境可进入。
2. 再部署并复验 PC/一体机终端绑定，让 `generic_terminal_count` 和 `unmatched_devices` 能在真实管理端被处理。
3. 再新增 `/manage/coils` 最小可用页，承接随行卡、客户、合金、规格、当前工艺、上下机重量和补录差异。
4. 最后把 `/manage/live` 升级为实时生产流转大屏，保留 30 秒快照兜底和局部数字跳动。

五视角评分：

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 把“进得去、看得懂、数字可信”排到视觉重构前 |
| 工程 | 9.8 | 单元/后端绿灯与浏览器红灯分开记录，并已修复 E2E mock 缺口 |
| 设计 | 9.6 | 明确卷级页面和实时大屏的真实用户任务 |
| 安全 | 9.6 | 把 401、登录态和外部只读边界纳入门禁 |
| 真实用户 | 9.7 | 直接减少重复扫码、重复填报和找不到卷材信息 |

综合：9.68/10。

## 23. 卷级线索最小页实施记录

本轮已先完成 `/manage/coils` 最小可用页，没有改后端主算法，也没有写生产数据。它的作用是把“随行卡/卷材现在在哪、MES 原始值是多少、人工补录值是多少、机列是否待绑定”先在管理端展示出来。

已完成：

1. 新增 `frontend/src/views/manage/coils/CoilTracePage.vue`。
2. 新增 `/manage/coils` 路由，并加入管理端导航、命令中心和横屏管理壳。
3. 页面接现有 `factory-command` 卷级接口，显示卷列表、搜索、详情和流向。
4. 页面明确区分“MES 主数据”和“人工补录对照”。
5. 未匹配机列显示“待绑定”，避免把 `PC` 误当具体机列。
6. 新增页面契约测试和浏览器 E2E 测试。

本轮验证：

| 验证项 | 结果 |
| --- | --- |
| 页面契约 TDD | 先失败后通过 |
| `manageCoilsPage` + 导航骨架测试 | `13` 项通过 |
| `/manage/coils` 浏览器 E2E | `1` 项通过 |
| 前端 node 测试 | `627` 项通过 |
| `git diff --check` | 通过 |

剩余高优先级：

1. 生产部署后复验 `/manage/coils` 真实接口和 PC 待绑定样例。
2. 接废料自动计算，但异常值必须隔离，不能污染主屏。
3. 接物联网能耗只读影子表。
4. 把 `/manage/live` 改成实时生产流转大屏。

## 24. 卷级自动废料线索实施记录

本轮已把“废料自动计算”做成只读卷级线索，没有改全厂总产量、日报主口径或成品率主算法。后端从 `mes_workshop_process_records` 里按批号取最新工序记录，返回 MES 上机、MES 下机、自动废料和废料状态；前端在 `/manage/coils` 中展示。

已完成：

1. `FactoryCoilListItemOut` 和 `FactoryCoilFlowOut` 增加 MES 重量和自动废料字段。
2. `factory_command_service.list_coils()` 和 `get_coil_flow()` 返回同一套重量线索。
3. 自动废料按 `MES 上机重量 - MES 下机重量` 计算。
4. 下机大于上机时返回 `abnormal_output_gt_input`，不返回假废料值。
5. 缺重量时返回 `missing_weight`，无工序记录时返回 `no_mes_process_record`。
6. `/manage/coils` 页面新增“自动废料”列和详情中的“MES 上机 / MES 下机 / 自动废料”。
7. 页面去向筛选已修正为后端真实值：`in_progress`、`finished_stock`、`allocation`、`delivery`、`unknown`。

验证：

| 验证项 | 结果 |
| --- | --- |
| 后端新增 TDD | 先失败后通过 |
| 工厂指挥服务/路由测试 | `43` 项通过 |
| 卷级页静态测试 | `5` 项通过 |
| 管理导航/命令中心相关前端测试 | `42` 项通过 |
| `/manage/coils` 浏览器 E2E | `1` 项通过 |

风险控制：

1. 不写生产数据。
2. 不改日报和全厂总产量主口径。
3. 异常废料只作为线索展示，后续再进入异常中心和实时大屏事件流。
4. 生产部署后必须用真实 MES 工序记录复验批号匹配稳定性。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | 发现 2 个 P1 业务信任问题：实时页 0 值误导、异常算法值不能上主屏 |
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 | issues_open | 发现 3 个 P1 工程问题：前端映射、异常废料、在制材料滞后 |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | issues_open | 发现 3 个体验问题：状态语言不统一、卷级线索缺页面、调度页行动性不足 |
| Coverage Review | route/browser/API audit | Page and interface coverage | 1 | issues_open | 发现路由多、入口少、详情页孤立、部分页面直接调 API、旧入口多 |
| Matrix Review | page/API matrix | Deletion and merge safety | 1 | issues_open | 已建立页面/接口覆盖矩阵，供后续删减、合并和自动测试使用 |
| Backend Architecture Review | backend architecture map | Data flow and risk map | 1 | issues_open | 已建立后端架构风险图，标出 MES、实时聚合、能耗、手机填报、AI、自动任务关键链路 |
| Contract Test Review | API contract audit | Front/back field safety | 1 | issues_open | 已建立核心接口字段契约测试计划，下一阶段用 TDD 保护实时大屏、能耗、MES 补录、卷级线索 |
| Frontend Experience Review | browser/page audit | UX and page retention | 1 | issues_open | 已建立前端体验与页面保留审计，确认能耗分母、合同矛盾、库存单位、SSE 验收、页面合并顺序 |
| Phase 1 TDD Backlog Review | executable remediation plan | First implementation gate | 1 | issues_open | 已建立第一阶段 TDD 修复作业单，锁定 6 个问题域和对应测试文件 |
| Auth Permission Health Review | login/health/browser smoke | Login stability and runtime health | 1 | issues_open | 已建立登录权限与运行健康审计，确认测试登录链路可用；生产真实管理员登录 smoke 仍需修复，SQL Server MES fresh；`/api/v1/readyz` 兼容路由已补齐并通过测试，前端未使用 refresh token |
| Settings Terminal Binding Review | settings/master/browser audit | PC/WAN terminal binding feasibility | 1 | issues_open | 已建立设置与终端绑定审计，确认现有别名映射不能承载 PC 绑定；PC 待绑定线索已进入 readiness 和系统设置页，结构化绑定表/接口/匹配规则和首版前端维护入口已完成，管理端浏览器用例 12 项通过，待生产复验 |
| Coil Trace Command Screen Review | plan + office-hours | Coil trace, supplement, energy and live wall design | 1 | issues_open | 已建立卷级线索、MES 辅助补录与实时生产流转大屏专项方案，确认 PC 需按终端+车间+工艺绑定，物联网能耗应走只读影子表 |
| Terminal Binding Execution Plan | `$plan` + `$office-hours` | PC terminal binding, scrap, IoT energy, coils and realtime wall | 1 | issues_open | 已新增 `.omx/plans/2026-06-11-terminal-binding-coil-realtime-screen.md`，把 PC 终端绑定、废料安全计算、物联网只读影子表、卷级线索页和实时大屏拆成可验收阶段 |
| Frontend IA Review | route/nav/page audit | Management information architecture | 1 | issues_open | 已新增前端信息架构审计，确认 `/manage/coils` 缺正式页面，库存/报表/考勤/合同应先灰度合并或降级，不能直接硬删 |
| Page API Dataflow Review | page/API/model audit | Page-to-interface-to-table coverage | 1 | issues_open | 已新增页面-接口-数据表链路审计，确认核心页面接口依赖、服务体量、测试覆盖和 `/manage/coils`/状态语言缺口 |
| Testing QA Gates Review | test/CI/e2e audit | Verification gates | 1 | issues_open | 已新增测试体系与 QA 验收门禁审计，确认测试资源充足但缺 `/manage/coils`、跨页面状态语言、终端绑定全链路和页面合并回归门禁 |
| Browser Core Flow Review | Playwright + core tests | Real browser and core flow experience | 1 | issues_open | 已新增浏览器体验与核心主线风险审计，确认前端 619 测试和后端 54 主线测试通过；Playwright 管理端壳补 mock 后 5 项全过；生产健康接口可用但真实管理员登录 smoke 返回 400 |
| Coil Trace Page Execution | TDD + Playwright | Coil-level clue page implementation | 1 | partially_resolved | 已新增 `/manage/coils` 最小页、导航入口、页面契约测试和浏览器测试；前端 627 项 node 测试通过，E2E 1 项通过，待生产部署后用真实 MES 样例复验 |
| Auto Scrap Clue Execution | TDD + service contract | Coil-level scrap clue | 1 | partially_resolved | 已新增 MES 上机/下机/自动废料字段和异常状态；后端 43 项相关测试通过，前端卷级页和 E2E 通过；仍需真实 MES 记录复验和异常中心接入 |

- **UNRESOLVED:** 需要现场确认 PC/WAN/一体机唯一标识、物联网数据库字段、终端是否跨机列使用。
- **VERDICT:** 计划已进入第一阶段 TDD 施工；E2E 登录态门禁已恢复，PC 终端绑定本地闭环已完成，`/manage/coils` 最小页面和卷级自动废料线索已完成本地验证。但生产真实管理员登录仍未通过，PC 终端绑定、卷级线索页和自动废料仍需部署后用真实 MES 样例复验。下一优先级应为“生产复验 + 工艺废料阈值 + 物联网能耗影子表 + `/manage/live` 实时生产流转大屏”，不建议直接做大规模视觉重构。
