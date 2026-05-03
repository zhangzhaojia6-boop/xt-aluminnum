# MES 可读投影与工厂生产大屏设计

日期：2026-05-02
状态：待用户审阅
适用系统：鑫泰铝业 数据中枢

## 背景

本轮目标是把管理端从“日报/审阅中心”继续收敛为“工厂总览下的多分支生产大屏”：管理层进入系统后，第一眼能看到全厂、车间、机列、卷流转、在制、库存去向、经营估算和异常。

2026-05-02 已实际登录公司内部 `MES` 做只读巡检。结论是：当前 `MES` 可以通过登录态读取生产数据，但暴露的是 MVC 页面和 DataTables POST 接口，不是稳定的正式开放 API。因此本系统应把 `MES` 视为外部真源，先做只读投影，不回写、不替代、不把本系统称作 `MES`。

## MES 巡检结论

已确认可读入口：

- 菜单权限：`/Right/GetUserRightList`，当前账号可见 57 个权限项、约 40 个页面入口。
- 实时流转：`/Dispatch/QueryList`，返回生产中卷级数据，包含当前车间、当前工艺、下一车间、下一工艺、批号、坯料卷号、规格、合金、状态、投料重量等。
- 随行卡：`/FollowCard/QueryList`，返回随行卡/批号主数据，字段与实时流转基本一致，总量很大，适合作为卷级主读源。
- 车间随行卡：`/WorkShop/QueryListByWorkShop`，偏车间视角。
- 工艺主数据：`/Craft/GetList`，当前返回 53 条工艺，覆盖 1450、1650、1850、2050、拉矫、热轧、精整、新厂在线、园区在线、园区淬火、园区精整、园区圆片、铣床等车间。
- 设备主数据：`/Device/GetList`，当前返回 50 台设备/终端，包含车间、工艺、设备名、状态。
- 铸轧/坯料机列看板：`/Material/GetBoardList`，返回 1# 到 11# 机列槽位。
- 在制统计：`/Dispatch/DoingReportTotal`，页面可读当前在制按车间/工序聚合。
- 成品库存：`/Stock/GetList`，可读库存批号、规格、合金、状态、净重、入出库等字段。

2026-05-02 巡检时首页读到的生产摘要：

- 当月合同量 462t
- 当日合同量 92t
- 当月投料量 1109.0t
- 当日投料量 526.0t
- 当日包装总量 137.6t

2026-05-02 巡检时在制统计读到的主要分布：

- 1850车间：53.0t，冷轧 53.0t
- 2050车间：323.0t，冷轧 323.0t
- 拉矫车间：601.3t，洗拉 279.5t、拉矫 42.5t、分切 53.0t、退火 226.3t
- 精整：70.0t，剪切 61.0t、纵剪 9.0t
- 新厂在线车间：358.0t，北线退火 344.0t、南线退火 14.0t
- 园区在线车间：107.5t，在线退火 107.5t
- 园区精整：87.0t，剪切 61.0t、重卷 26.0t

## 关键业务判断

### 1. 卷级主键不能只用二维码

`MES` 的随行卡打印模板中，二维码值来自 `BatchNumber`。但真实卷级流转还同时依赖：

- `Product.Id`
- `BatchNumber`
- `MaterialCode`
- `CurrentWorkShop`
- `CurrentProcess`
- `NextWorkShop`
- `NextProcess`
- `ProductProcess / ProductProcessRecord`

因此本系统内部应使用 `mes_product_id + batch_no + material_code` 做幂等线索，`tracking_card_no` 可以优先等同 `BatchNumber`，但不能把它当作唯一能表达卷流转的字段。

### 2. 工艺路线已经在 MES 内存在

`MES` 返回字段中已有：

- `CurrentWorkShop`
- `CurrentProcess`
- `NextWorkShop`
- `NextProcess`
- `CurrentProcessSort`
- `NextProcessSort`
- `ProcessRoute`
- `PrintProcessRoute`
- `DelayHour`
- `StatusName`

这意味着数据中枢填报端新增“上个工艺/下个工艺”时，推荐优先由 `MES` 自动带出路线；人工只做确认和补缺，不要让一线重新手工维护整条工艺路线。

### 3. 机列口径有两层

`MES` 中存在两套机列/设备线索：

- 机列槽位：`Material/GetBoardList` 的 1# 到 11#。
- 设备终端：`Device/GetList` 中的具体终端，如 1450 冷轧 1/2 号机、1850 冷轧 1-4 号机、2050 冷轧、精整剪切/纵剪、园区飞剪、在线退火南北线等。

数据中枢应把它们映射成统一 `machine_line`：

- `line_code`：稳定机列编码，用于聚合。
- `device_code`：终端/设备编码，用于填报登录和采集来源。
- `display_name`：管理端展示名。
- `source_aliases`：承接 `MES` 里的中文名、WIFI/WAN 设备名、历史别名。

## 推荐方案

采用“三层只读投影”：

1. `MES MVC read adapter`
   先兼容当前可读的页面接口，使用登录态、反伪造 token 和 DataTables 参数读取数据。只在服务端运行，不把账号密码写入前端或代码。

2. `MES coil/process projection`
   将 `MES` 的卷级、工序、库存、设备、工艺主数据投影到本地读模型。所有写入均为本地缓存，不回写 `MES`。

3. `Factory command screens`
   管理端以本地投影为主数据源，形成“全厂 -> 车间 -> 机列 -> 卷 -> 去向”的可视化链路。数据过期时明确显示“已滞后”，不伪装实时。

这个方案比直接改填报端更稳，因为它先把外部真源读清楚，再让填报端只补 `MES` 缺失或需要现场确认的事实。

## 管理端信息架构

取消“日报交付”作为主线，保留为后台历史/导出能力。工厂总览下新增生产大屏分支：

1. `工厂总览`
   全厂今日产量、在制、投料、包装、库存、异常、经营估算、数据新鲜度。

2. `生产流转大屏`
   以卷为流动粒子，展示从投料、当前工序、下一工序、包装、入库、调拨/发货的流向。

3. `车间机列大屏`
   行为车间/机列，列为工艺状态、当前卷数、当前吨数、完成吨数、停滞卷数、单位成本估算。

4. `卷级追踪`
   搜批号/卷号后展示完整路线：来料、已过工序、当前工序、下道工序、计划去向、最终库存/发货状态。

5. `经营效益大屏`
   按车间/机列估算“做了多少、花了多少、赚了多少”。口径为经营估算，不作为财务结算。

6. `库存去向大屏`
   展示已完成的东西去了哪里：成品库、调拨、发货、仍在制、问题卷。

7. `异常地图`
   展示工艺延迟、问题卷、库存异常、重量异常、未匹配路线、数据滞后。

## AI 助手设计

AI 采用“双形态”设计：一个常驻、可交流、会主动汇报的 `数据中枢 AI 助手`，再加上散落在各生产大屏里的上下文解释能力。AI 不是一个孤立页面，也不是几条静态摘要；它应该像一个一直盯着工厂运行的人，能听你问、主动提醒、按你的关注点持续巡检。

### 核心定位

`数据中枢 AI 助手` 是管理层和现场的生产参谋：

- 能对话：随时问“现在厂里什么情况”“2050 冷轧为什么毛差低”“这卷去哪了”。
- 能主动汇报：按班次、小时、异常事件、关注对象主动推送简报。
- 能持续盯事：用户可以说“帮我盯 2050 冷轧能耗”“这批 5052 到入库前有异常就报我”。
- 能带证据：每条结论能点回卷、机列、车间、工序、同步时间、规则或成本系数。
- 能给下一步：告诉用户先看哪台机、哪几卷、哪个班次、哪个字段。

### 产品形态

1. 常驻助手
   - 管理端右侧保留可展开的 AI 助手抽屉。
   - 大屏模式下显示为右上角状态灯和一行主动播报，不遮挡主画面。
   - 移动端显示为底部小入口，只在扫码、异常、退回、路线缺失时主动出现。

2. 对话工作台
   - 保留一个二级入口，用于完整历史对话、关注列表、主动汇报记录、AI 能力探针。
   - 这里不是管理主入口，而是“和 AI 深聊”的地方。

3. 大屏内嵌解释
   - 每个卡片、卷、机列、异常点都有“问 AI”入口。
   - 用户从哪个对象点开，AI 就自动带上对应上下文。

4. 主动汇报收件箱
   - 汇总 AI 主动发出的开班简报、小时巡检、异常快报、交接摘要。
   - 每条汇报都有状态：未读、已读、已跟进、忽略。

### 主动汇报类型

主动汇报不等同于日报，不生成传统日报文件。它是运行中的短简报。

1. 开班简报
   - 班次开始时生成。
   - 内容：当前在制、重点机列、上一班遗留、今天高风险卷、MES 同步状态。

2. 小时巡检
   - 默认每小时一次，可按角色配置。
   - 内容：产量进度、在制变化、停滞卷、机列异常、数据滞后。

3. 异常快报
   - 事件触发。
   - 触发条件：工艺延迟、重量异常、下道工序缺失、机列成本突增、库存去向异常、MES 同步滞后。

4. 关注对象汇报
   - 用户主动订阅某车间、机列、批号、合金、客户或工艺。
   - 示例：“只要 26RA03492 有新流转就提醒我。”

5. 交接摘要
   - 班次结束前生成。
   - 内容：本班完成、未完成、异常、需要下一班继续盯的卷和机列。

6. 管理层晨/午/晚简报
   - 给厂级观察者。
   - 内容：全厂态势、风险排行、经营估算偏差、需要人工决策的事项。

### 对话能力

AI 助手支持三类对话。

生产问答：

- “现在厂里最卡的是哪里？”
- “2050 冷轧今天做了多少、花了多少、估算赚了多少？”
- “拉矫车间在制为什么突然多了？”
- “这卷前一道是什么，下一道去哪？”

诊断追问：

- “为什么你说这个机列异常？”
- “证据是哪几卷？”
- “和昨天比差在哪？”
- “是不是 MES 数据滞后导致的？”

持续任务：

- “帮我盯着 1850 冷轧 1 号机，有停滞就报。”
- “这批 5052 到包装前有路线缺失就提醒我。”
- “每小时给我汇报一次全厂异常，不要报正常项。”
- “今天只看园区在线和园区精整。”

### AI 能力分层

第一层：规则引擎

- 不调用大模型。
- 负责高频巡检：缺字段、超阈值、路线不匹配、同步滞后、重量不合理、库存去向异常。
- 产出 `rules_fired`，作为 AI 汇报证据。

第二层：主动汇报引擎

- 按时间或事件触发。
- 把规则结果、MES 投影、成本估算和用户关注点组合成短简报。
- 可先使用模板化中文生成，必要时再调用大模型润色。

第三层：对话助手

- 调用大模型，但只能读取后端准备好的 `context_pack`。
- 支持多轮追问和对象上下文。
- 输出必须包含 `answer`、`confidence`、`evidence_refs`、`missing_data`、`recommended_next_actions`。

第四层：行动草稿

- AI 可以生成“催报话术”“交接提醒”“异常处理建议”。
- AI 不能直接发送、提交、删除、改权限、回写 `MES`。
- 所有对外消息或系统写动作必须由人确认。

### 关注与订阅

新增 `AI Watchlist` 概念。每个用户可以订阅：

- 车间：如 `2050车间`
- 机列：如 `2050冷轧`
- 卷/批号：如某个 `BatchNumber + MaterialCode`
- 工艺：如 `退火 -> 剪切`
- 合金/规格：如 `5052`、`1.5*1250*C`
- 指标：如单吨能耗、成材率、停滞时长、毛差估算

订阅项包含：

- `watch_type`
- `scope_key`
- `trigger_rules`
- `quiet_hours`
- `report_frequency`
- `channels`
- `created_by`
- `is_active`

默认先支持站内汇报。企业微信、钉钉、短信等外部推送必须单独配置和确认。

### 上下文包设计

AI 不直接吃整库数据。后端为每次对话或主动汇报生成窄上下文：

```json
{
  "intent": "machine_line_diagnosis",
  "question": "为什么 2050 冷轧今天毛差偏低？",
  "scope": {
    "business_date": "2026-05-02",
    "workshop": "2050车间",
    "machine_line": "2050冷轧"
  },
  "freshness": {
    "data_source": "mes_projection",
    "last_synced_at": "2026-05-02T14:30:00+08:00",
    "lag_seconds": 63
  },
  "metrics": {},
  "coil_refs": [],
  "rules_fired": [],
  "watchlist_matches": [],
  "cost_assumptions": [],
  "known_missing_data": []
}
```

上下文包最多包含：

- 当前页面指标。
- Top N 异常卷。
- 当前车间/机列汇总。
- 相关工艺路线。
- 相关库存去向。
- 成本估算系数。
- 已触发规则。
- 用户关注对象。
- 数据新鲜度。

上下文包不能包含：

- 登录凭据。
- 原始账号密码。
- 不必要的客户联系方式。
- 超出当前用户权限的数据。
- 未经脱敏的大批量明细。

### AI 数据结构

新增读模型 `ai_conversations`：

- `id`
- `owner_user_id`
- `title`
- `scope_type`
- `scope_key`
- `created_at`
- `updated_at`

新增读模型 `ai_messages`：

- `id`
- `conversation_id`
- `role`
- `content`
- `evidence_refs`
- `confidence`
- `created_at`

新增读模型 `ai_watchlist_items`：

- `id`
- `owner_user_id`
- `watch_type`
- `scope_key`
- `trigger_rules`
- `quiet_hours`
- `report_frequency`
- `channels`
- `is_active`
- `created_at`
- `updated_at`

新增读模型 `ai_briefing_events`：

- `id`
- `business_date`
- `briefing_type`
- `scope_type`
- `scope_key`
- `title`
- `summary`
- `severity`
- `evidence_refs`
- `recommended_next_actions`
- `delivery_status`
- `read_status`
- `generated_at`
- `expires_at`

新增读模型 `ai_context_packs`：

- `id`
- `context_key`
- `scope_type`
- `scope_key`
- `payload`
- `source_hash`
- `freshness_status`
- `created_at`
- `expires_at`

这些表都不是生产事实真源。它们记录 AI 的对话、订阅、主动汇报和上下文快照，可以过期重建。

### AI API 设计

对话接口：

- `GET /api/v1/ai/assistant/conversations`
- `POST /api/v1/ai/assistant/conversations`
- `GET /api/v1/ai/assistant/conversations/{id}/messages`
- `POST /api/v1/ai/assistant/conversations/{id}/messages`
- `POST /api/v1/ai/assistant/ask`

主动汇报接口：

- `GET /api/v1/ai/briefings`
- `POST /api/v1/ai/briefings/{id}/read`
- `POST /api/v1/ai/briefings/{id}/follow-up`
- `POST /api/v1/ai/briefings/generate-now`

关注订阅接口：

- `GET /api/v1/ai/watchlist`
- `POST /api/v1/ai/watchlist`
- `PATCH /api/v1/ai/watchlist/{id}`
- `DELETE /api/v1/ai/watchlist/{id}`

大屏上下文接口：

- `POST /api/v1/factory-command/ai/explain-coil`
- `POST /api/v1/factory-command/ai/explain-machine-line`
- `POST /api/v1/factory-command/ai/explain-cost`
- `GET /api/v1/factory-command/ai/context-packs/{context_key}`

AI 回答统一结构：

```json
{
  "answer": "2050冷轧今天毛差偏低，主要来自单位能耗偏高和完成吨数低于同类机列。",
  "confidence": "medium",
  "evidence_refs": [
    {"type": "machine_line", "id": "2050-LZ", "label": "2050冷轧"},
    {"type": "metric", "id": "energy_cost_per_ton", "label": "单吨能耗成本"}
  ],
  "missing_data": ["部分机列能耗为估算值"],
  "recommended_next_actions": ["先核对 2050 冷轧本班能耗填报", "再看停滞卷清单"],
  "can_create_watch": true
}
```

### 前端交互

常驻助手抽屉：

- 左侧显示当前页面上下文。
- 中间是对话流。
- 底部输入框支持自然语言。
- 右侧小栏显示证据、关注按钮、最近主动汇报。

主动汇报卡片：

- 显示在工厂总览顶部、助手收件箱、对应大屏侧栏。
- 卡片结构：标题、严重度、两行摘要、证据数、建议动作、关注/忽略。

大屏模式：

- 不打开完整聊天窗。
- 只显示 AI 状态灯、最新一句主动汇报、严重异常数量。
- 点击后进入助手抽屉。

移动填报端：

- AI 不常驻打扰。
- 只在扫码失败、路线缺失、数据异常、被退回时出现。
- 重点说“该填什么、哪里不合理、下一步怎么补”。

### 主动性边界

AI 可以主动：

- 生成站内简报。
- 在大屏上提示异常。
- 建议关注对象。
- 生成催报/交接/异常处理草稿。
- 提醒数据滞后和证据不足。

AI 不可以自动：

- 回写 `MES`。
- 提交填报。
- 删除或作废数据。
- 修改成本系数。
- 修改权限。
- 发送外部消息。
- 对外发布正式口径。

需要发送企业微信、钉钉、短信、邮件时，第一阶段只生成草稿和站内提醒；启用真实外部发送前必须有管理员配置、接收人范围、审计记录和人工确认。

### 安全与权限

- AI 使用当前登录用户的权限 scope 生成上下文。
- 厂级观察者看全厂，车间观察者只看本车间，填报端只看本机列/本卷。
- 第三方模型调用前必须由后端完成字段裁剪和脱敏。
- 当 `MES` 同步滞后超过 300 秒，AI 必须在回答和主动汇报中提示数据滞后。
- 当成本系数缺失，AI 只能解释生产事实，不能输出毛差判断。
- 当证据不足，AI 必须说“当前证据不足”，并列出缺什么数据。

### 运行策略

- 规则引擎每次 `MES` 同步后运行。
- 开班简报、小时巡检、交接摘要由后台任务生成。
- 异常快报由规则事件触发。
- 对话按用户操作实时调用。
- 所有主动汇报带过期时间，过期后前端显示“需刷新”。
- 保留 `live-probe`，但它只表示 AI 服务可用，不表示生产数据可信。

## 数据模型增补

在现有 `mes_coil_snapshots` 基础上，建议先增补或通过 `source_payload` 固化以下字段：

- `mes_product_id`
- `batch_no`
- `material_code`
- `contract_no`
- `contract_notice_no`
- `customer_alias`
- `mode`
- `product_type`
- `alloy_grade`
- `material_state`
- `spec_thickness`
- `spec_width`
- `spec_length`
- `spec_display`
- `feeding_weight`
- `material_weight`
- `gross_weight`
- `net_weight`
- `current_workshop`
- `current_process`
- `current_process_sort`
- `next_workshop`
- `next_process`
- `next_process_sort`
- `process_route_text`
- `print_process_route_text`
- `status_name`
- `card_status_name`
- `production_status`
- `delay_hours`
- `in_stock_date`
- `delivery_date`
- `allocation_date`
- `last_seen_from_mes_at`

新增读模型 `mes_machine_line_snapshots`：

- `business_date`
- `workshop_name`
- `workshop_code`
- `line_code`
- `line_name`
- `process_name`
- `active_coil_count`
- `active_weight_ton`
- `finished_weight_ton`
- `stalled_coil_count`
- `estimated_energy_cost`
- `estimated_labor_cost`
- `estimated_material_loss`
- `estimated_gross_margin`
- `last_seen_from_mes_at`
- `source_payload`

新增读模型 `coil_flow_events`：

- `coil_key`
- `batch_no`
- `material_code`
- `from_workshop`
- `from_process`
- `to_workshop`
- `to_process`
- `event_type`
- `event_time`
- `source`
- `source_payload`

`coil_key` 推荐规则：

```text
MES:{mes_product_id}
fallback:{batch_no}:{material_code}
```

## 实时性策略

目标口径：

- 正常情况下 60 秒轮询一次 `MES` 读取接口。
- 管理端可见延迟目标 `<= 120 秒`。
- 超过 300 秒标为 `stale`。
- 超过 900 秒标为 `offline_or_blocked`。

管理端所有大屏顶部必须展示：

- 数据源：`MES 投影` / `本地填报` / `混合`
- 最后同步时间
- 当前滞后秒数
- 最近一次同步状态

不要只显示“实时”两个字。实时要有时间戳证明。

## 填报端增强

卷级填报新增“流转确认”字段组：

- `previous_workshop`
- `previous_process`
- `current_workshop`
- `current_process`
- `next_workshop`
- `next_process`
- `flow_source`
- `flow_confirmed_at`

页面行为：

- 如果 `MES` 返回工艺路线，自动带出上工序、当前工序、下工序，并默认锁定。
- 一线只需要确认本卷是否确实到本机列。
- 如果 `MES` 没有下工序，前工序主操只填“下道去哪”。
- 如果 `MES` 不可用，允许临时手填 `next_workshop + next_process`，标记为 `manual_pending_match`。
- 人工填的路线不回写 `MES`，只用于数据中枢自己的卷流转看板。

存储方式：

- 第一阶段先放 `work_order_entries.extra_payload.flow`.
- 等字段稳定后，再决定是否升为正式列。

## 成本与收益口径

机列级“花了多少、赚了多少”先做经营估算：

- 收入估算：按产品类型/合金/规格配置吨价或合同均价。
- 能耗成本：优先使用按机列能耗填报；缺失时按车间/工艺系数估算。
- 人工成本：按班组/机列/班次配置标准人工成本。
- 损耗成本：按投入、产出、废料和成材率估算。
- 毛差估算：收入估算 - 能耗 - 人工 - 损耗 - 辅材。

所有页面文案使用“估算”“经营口径”，不使用“财务利润”。

## API 设计

新增后端只读接口：

- `GET /api/v1/factory-command/overview`
- `GET /api/v1/factory-command/screens`
- `GET /api/v1/factory-command/workshops`
- `GET /api/v1/factory-command/machine-lines`
- `GET /api/v1/factory-command/coils`
- `GET /api/v1/factory-command/coils/{coil_key}/flow`
- `GET /api/v1/factory-command/cost-benefit`
- `GET /api/v1/factory-command/destinations`
- `GET /api/v1/mes/sync-status`
- `GET /api/v1/ai/assistant/conversations`
- `POST /api/v1/ai/assistant/conversations`
- `GET /api/v1/ai/assistant/conversations/{id}/messages`
- `POST /api/v1/ai/assistant/conversations/{id}/messages`
- `POST /api/v1/ai/assistant/ask`
- `GET /api/v1/ai/briefings`
- `POST /api/v1/ai/briefings/{id}/read`
- `POST /api/v1/ai/briefings/{id}/follow-up`
- `POST /api/v1/ai/briefings/generate-now`
- `GET /api/v1/ai/watchlist`
- `POST /api/v1/ai/watchlist`
- `PATCH /api/v1/ai/watchlist/{id}`
- `DELETE /api/v1/ai/watchlist/{id}`
- `POST /api/v1/factory-command/ai/explain-coil`
- `POST /api/v1/factory-command/ai/explain-machine-line`
- `POST /api/v1/factory-command/ai/explain-cost`

新增同步任务：

- `sync_mes_menu_rights`
- `sync_mes_crafts`
- `sync_mes_devices`
- `sync_mes_follow_cards`
- `sync_mes_dispatch`
- `sync_mes_wip_total`
- `sync_mes_stock`

所有同步任务必须幂等，失败不能清空已有投影。

## 前端落点

建议改造：

- `/manage/overview`：默认进入未来感工厂总览。
- `/manage/factory/flow`：生产流转大屏。
- `/manage/factory/machine-lines`：车间机列大屏。
- `/manage/factory/coils`：卷级追踪。
- `/manage/factory/cost`：经营效益大屏。
- `/manage/factory/destinations`：库存去向大屏。
- `/manage/factory/exceptions`：异常地图。
- `/manage/ai-assistant`：AI 助手工作台，包含历史对话、主动汇报、关注列表和能力探针。

导航调整：

- `日报交付` 从一级导航移除，收入 `设置 / 历史导出` 或 `经营归档`。
- `班次中心` 不再独立作为管理主入口，只作为车间机列大屏的时间维度。
- `数据接入` 保留给管理员，不出现在普通管理者的第一层视野。
- `AI 助手` 不作为替代大屏的主导航，但在管理端常驻；完整工作台放在二级入口。

## 验收标准

1. 管理者 10 秒内能回答：
   - 每个车间/机列现在做了多少。
   - 当前在制卷在哪道工序。
   - 下一道去哪。
   - 完成后去了成品库、调拨还是发货。
   - 哪些卷/机列停滞或异常。
   - 每个机列的经营估算是否偏差。

2. 数据新鲜度可验证：
   - 每张大屏都有最后同步时间和滞后状态。
   - `MES` 不可用时页面降级，不伪装实时。

3. 填报端减负：
   - `MES` 可用时自动带出上工序/当前工序/下工序。
   - 前工序只需确认或填写下道去向。
   - 手填路线有来源标记。

4. 不破坏现有系统：
   - 不回写 `MES`。
   - 不删除现有填报、模板、用户权限。
   - 不把数据中枢命名为 `MES`。

5. AI 助手可交流、可主动汇报、可控：
   - 常驻助手能围绕当前页面、卷、机列、车间进行多轮对话。
   - 开班简报、小时巡检、异常快报、关注对象汇报、交接摘要能进入站内收件箱。
   - 用户能订阅车间、机列、卷/批号、工艺、合金/规格或指标。
   - AI 主动汇报能指出今日 Top 3 风险，并能点回证据。
   - 卷级追问能回答当前位置、前工序、下工序和去向。
   - 机列解释能说明产量、成本、停滞或数据缺失原因。
   - 数据滞后、成本系数缺失、证据不足时，AI 明确说不确定。
   - AI 不自动提交、删除、回写、修改权限或发送外部消息。

## 风险

- 当前 `MES` 读取方式依赖登录态和页面接口，不如正式 API 稳定。
- `MES` DataTables 字段很宽，字段含义需要继续和现场确认。
- `BatchNumber` 不是足够强的卷级唯一键，必须和 `Product.Id / MaterialCode` 一起用。
- `WIFI/WAN` 设备名和机列槽位需要人工建立别名映射。
- 经营估算需要系数，不应承诺财务级准确。
- AI 如果不受控读取上下文，容易生成看似合理但无证据的结论，必须走 `context_pack + evidence_refs`。
- 第三方模型调用需要脱敏和权限裁剪，不能把凭据、联系方式或超范围明细传出。
- 主动汇报如果频率过高会变成噪音，需要支持 quiet hours、严重度阈值、关注列表和忽略规则。

## 下一步

1. 先做 `MES read adapter` 的只读 POC，验证 5 类接口：工艺、设备、随行卡、实时调度、库存。
2. 建立 `MES 字段 -> 数据中枢读模型` 的正式映射表。
3. 设计 `/manage/overview` 的大屏分支信息架构和首屏视觉。
4. 补 `AI assistant / briefing / watchlist / context_pack` 的接口契约。
5. 先做站内 AI 助手和主动汇报 POC。
6. 再改填报端的流转确认字段。
7. 最后把经营估算和 AI 对话解释接入机列级看板。
