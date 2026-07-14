# Hermes 单入口与日报真实事实闭环设计

日期：2026-07-11

状态：已确认

项目：鑫泰铝业 数据中枢

## 1. 目标

本轮只解决一件事：让鑫泰铝业每天得到一份可证明、可追溯、不能靠模型猜数的生产日报，同时让 NousResearch Hermes 真正成为能理解钉钉业务、主动查证和推动补齐的企业智能大脑。

目标链路：

```text
钉钉聊天/文件 + MES/WMS 只读数据 + 扫码补录
  -> 可审计证据
  -> 字段口径校验和冲突判断
  -> DailyFactBundle 持久化
  -> 日报正文
  -> /manage 来源、异常和 trace
  -> Hermes 主动追问、补证据、创建补录动作
```

`D:\输出skill` 只在链路末端作为答案钥匙比较结果，绝不参与生产事实填数。

## 2. 当前已核实问题

### 2.1 钉钉与 Hermes

- 生产机真正接收钉钉 Stream 的进程是 NousResearch Hermes 的 `hermes-gateway.service`。
- 数据中枢仓库中的 `backend/scripts/hermes_dingtalk_stream_gateway.py` 不是生产 Hermes 当前运行入口。
- 当前生产 Hermes 使用固定关键词决定是否调用 `xt-hermes-agent-cli dingtalk-command`。口语、省略句、错别字、上下文追问和未预先定义的业务问题可能无法进入事实查询链。
- 当前 DingTalk 适配器主要抽取文本；文件、附件和非文本事件没有稳定进入数据中枢 `MultimodalEvidence`。
- 生产 `MultimodalEvidence` 最近没有随着 Stream 配置开启持续增长，说明“配置存在”不等于“真实证据已经接通”。

### 2.2 日报事实链

- MES 同步是新鲜的，但只能证明数据在流动，不能证明日报口径正确。
- 生产 `daily_fact_bundle_runs` 和 `daily_fact_bundle_snapshots` 为空，现有事实包主要在验收脚本中临时构建，没有成为每日生产闭环。
- 最近一次三日纯真实源 compare-only 对齐没有通过，已完成日期的字段匹配率约为 13.39%。
- `HermesDataAuditService`、root owner、Stream 证据和 DailyFactBundle 没有共享同一个钉钉证据读取口径。
- 直接 MES 读取结果目前更多用于审计，没有完整并入最终事实包。

### 2.3 错误指标

生产管理页曾显示 `全厂成品率 819.08%`。当前实现把不同业务窗口中的成品入库量和投料量直接相除，这不是合法成品率口径。

正式指标必须有明确的：

- 分子；
- 分母；
- 单位；
- 同一业务时间窗口；
- 来源；
- trace；
- 口径版本。

任一条件缺失时，系统应显示 `缺失` 或 `冲突`，不能计算一个看似精确的数字。

## 3. 已确认的架构决定

### 3.1 Hermes 是唯一钉钉实时入口

不再启动第二个长期运行的钉钉 Stream 消费者。

```text
钉钉企业内部应用
  -> 生产 NousResearch Hermes Gateway
  -> 原始事件规范化
  -> 数据中枢现有 /api/v1/dingtalk/agent-inbound
  -> MultimodalEvidence
  -> Hermes 语义理解与工具调用
```

这样避免两个 Stream 客户端争抢事件，也保证 Hermes 最先看到钉钉事实。

### 3.2 不设置硬群边界

生产接收范围由钉钉企业内部应用自身授权决定。

`DINGTALK_AUTHORIZED_GROUP_IDS=*` 的含义是接收应用实际能收到的群和会话事件，不在业务代码中维护固定群白名单。

取消群白名单不等于取消审计。每条事件仍必须保存：

- conversation/group id；
- sender id 和可用的发送人信息；
- event time；
- message/event id；
- message type；
- file id、文件名和文件哈希（文件事件）；
- trace id；
- 原始来源和解析状态。

### 3.3 消息识别保持宽松，事实采用保持严格

消息进入系统和消息成为正式事实是两个动作：

```text
所有应用可收到的事件
  -> 先保存为 machine_only 候选证据
  -> Hermes 理解语义和上下文
  -> 核验责任人、业务日期、字段、单位和口径
  -> confirmed / conflict / missing
```

- 不因为没有命中关键词就丢弃消息。
- 不因为消息里出现数字就自动覆盖 MES。
- 不允许所有 Stream 消息自动升级为 `specialist_sampled`。
- 只有责任人身份、内容语义、业务时间和字段口径满足规则后，才可升级为高优先级事实。

### 3.4 复用现有数据结构

本轮不新建证据表、日报门户或第二套事实系统。

复用：

- `MultimodalEvidence`：保存钉钉消息和附件证据；
- MES/WMS 本地只读投影；
- 扫码填报事实；
- `DailyFactBundle`：统一日报事实包；
- `AgentRun` 和现有 trace；
- `/manage/today`、`/manage/alerts`、`/manage/ai-assistant`；
- `/api/v1/dingtalk/agent-inbound`。

## 4. 目标运行架构

```text
                         ┌────────────────────────────┐
钉钉消息/文件 ──────────>│ NousResearch Hermes Gateway│
                         └─────────────┬──────────────┘
                                       │ 原始事件先留证
                                       v
                         /api/v1/dingtalk/agent-inbound
                                       │
                                       v
                              MultimodalEvidence
                                       │
               ┌───────────────────────┼───────────────────────┐
               │                       │                       │
               v                       v                       v
      Hermes 语义查证          DailyFactBundle          冲突/缺失任务
               ^                       ^                       │
               │                       │                       v
        MES/WMS 只读查询 ──────────────┤                扫码补录/责任人
                                       │
                                       v
                                 正式生产日报
                                       │
                         ┌─────────────┴─────────────┐
                         v                           v
                  /manage/today              /manage/alerts
```

## 5. 组件职责

### 5.1 NousResearch Hermes Gateway

职责：

- 维持唯一钉钉 Stream 连接；
- 接收文本、文件、附件和未知类型事件；
- 不用固定业务关键词决定是否留证；
- 把原始事件规范化后送入数据中枢；
- 继续由 Hermes 自主判断是否查询工具、回复、追问或创建动作；
- 所有用户可见回复使用中文，身份为 `鑫泰铝业智能大脑`。

可靠性要求：

- 入站写入采用 message/event id 幂等；
- 数据中枢暂时不可用时，网关必须留下结构化失败记录并重试；
- 失败不能伪装成已入库；
- Stream 健康状态至少暴露连接状态、最后事件时间、成功数、失败数和最后错误。

### 5.2 钉钉证据入口

`/api/v1/dingtalk/agent-inbound` 负责：

- 验证生产内部调用凭据；
- 接收企业应用授权范围内的任意会话事件；
- 规范化 text/file/attachment/unknown；
- 保存原始元数据和解析结果；
- 默认写入 `machine_only`；
- 对重复 message/event id 幂等返回；
- 不直接把候选数字标成正式日报事实。

### 5.3 统一证据读取器

Hermes root owner、数据审计和 DailyFactBundle 必须复用同一个钉钉证据查询服务。

统一过滤条件：

- 业务时间窗口；
- message/file/attachment 内容类型；
- 解析状态；
- 责任人线索；
- 事实确认状态；
- trace 完整性。

不再让 `ChatInbox`、RAG 文本和 `MultimodalEvidence` 各自形成不同事实世界。

### 5.4 MES/WMS 只读事实

- 生产账号继续保持只读；
- 查询结果进入事实包时保存表/视图、查询窗口、字段映射、单位和 trace；
- “同步成功”不能代替字段正确性证明；
- 直接读取和本地投影冲突时记录冲突，不静默选择；
- 不允许用成品入库量替代总产量。

### 5.5 DailyFactBundle 每日闭环

在现有调度器中增加每日事实闭环，不新建调度服务。

每个已结束业务日：

1. 读取钉钉确认事实；
2. 读取 MES/WMS 只读事实；
3. 读取扫码补录和人工确认；
4. 按字段口径合并；
5. 标记 confirmed、candidate、missing、conflict；
6. 持久化 run、snapshot 和 trace；
7. 只从事实包渲染日报；
8. 缺失或冲突转成 Hermes 行动建议或扫码补录任务。

### 5.6 管理端

不新建页面。

- `/manage/today`：显示关键指标、真实来源、数据时间、状态和 trace；
- `/manage/alerts`：加入事实冲突、证据缺失、Hermes 运行失败、钉钉入站失败；
- `/manage/ai-assistant`：回答返回结论、业务日期、来源、事实状态和 trace；
- 现有详情页继续用于钻取；
- `/manage/channels` 后续合入 `/manage/admin/agents`，不在本轮新增能力。

## 6. 五个关键字段合同

| 字段 | 合法来源 | 关键限制 |
|---|---|---|
| `total_output_daily` | 钉钉已确认生产日报、MES 合法产量口径 | 禁止使用 finished inbound 代替 |
| `finished_inbound_daily` | WMS/MES 成品入库事实、钉钉已确认入库日报 | 必须注明入库业务窗口 |
| `wip_total` | MES/WMS 在制快照、钉钉已确认盘点 | 快照时点必须明确 |
| `total_electricity_kwh` | 能耗库、已确认表计/钉钉能源文件、扫码补录 | IOT 未配置时必须明确缺失来源 |
| `daily_yield_rate` | 已确认成品率事实，或同一口径分子/分母计算 | 不允许 `finished_inbound / feeding_input` 跨窗口计算 |

所有关键字段必须具有：`value`、`unit`、`business_date/window`、`source_kind`、`source_ref`、`status`、`trace_id`、`metric_contract_version`。

## 7. 来源优先级

优先级不是“看见钉钉就覆盖一切”，而是“在各自合法业务域内选择最可信的已确认事实”。

1. 钉钉责任人已确认的群文件和聊天事实；
2. MES/WMS/未来能耗库在各自业务域内的只读事实；
3. 扫码补录并完成责任人确认的事实；
4. 数据中枢投影和 DailyFactBundle 历史快照；
5. RAG 只用于解释规则和历史背景，不提供实时数字。

候选钉钉消息不能覆盖已确认 MES；已确认钉钉责任人事实与 MES 冲突时采用钉钉事实，同时必须保存冲突双方和 trace。

## 8. 业务时间

- 普通生产业务日：07:50 至次日 07:50；
- 铸二、铸三、热轧：10:00 至次日 10:00；
- 内勤每日一录：09:30 归属点；
- 验收使用最近三个已经结束且有答案钥匙的业务日；
- 旧的 07:30 文案和逻辑不得再作为当前口径。

## 9. 对齐门禁

纯真实源门禁必须满足：

- `OUTPUT_SKILL_REFERENCE_MODE=compare`；
- 禁止 `official_daily_report`、`output_skill` 或参考答案反向填数；
- 五个关键字段必须有合法底层来源和非空 trace；
- 三个业务日均持久化事实包；
- 五个关键字段匹配率 100%；
- 全字段匹配率不低于 95%；
- 剩余差异必须输出字段、双方数值、单位、来源、业务窗口和原因。

误差不能统一写成 `±20`。按字段单位设置：

- 吨类字段：业务允许时绝对差不超过 20 吨，但仍需报告差异；
- 电量：按表计和日报取整规则设置独立 kWh 容差；
- 比率：使用百分点容差，不能容忍 20 个百分点；
- 计数字段：使用整数容差；
- 未配置字段容差时按严格相等处理。

## 10. Hermes 能力验收

Hermes 20 问不能再以“都回答 missing”判定通过。

每个问题必须满足以下一种结果：

1. `confirmed`：给出真实数字、业务时间、来源和 trace；
2. `conflict`：列出冲突双方并给出采用理由和下一步；
3. `missing`：指出具体缺哪个来源，并创建或建议明确补录动作。

关键五项问题必须全部为 `confirmed`，否则整轮失败。

同时验证：

- 口语、省略句、错别字和连续追问；
- 不包含旧固定关键词的问题；
- 文件内容追问；
- MES 与钉钉冲突判断；
- 不知道时明确不知道，绝不编数；
- 所有回复使用中文。

## 11. 部署与版本治理

- 数据中枢继续使用唯一 systemd 生产部署流程；
- Hermes 生产修改必须进入可追踪的 Git 分支/提交，不能长期只保留生产机脏改动；
- 生产 Hermes 仓库的现有修改和备份文件先归档，再建立可重复部署基线；
- 增加运行版本接口或健康字段，返回数据中枢 SHA 和 Hermes SHA；
- “生产目录 HEAD 一致”不能代替“运行进程已加载该 SHA”；
- 部署流程统一包含备份、迁移、构建、重启、健康、真实链路验收和可回滚点；
- 密钥只存在 GitHub Secrets 或生产环境文件中，不进入 Git、文档、前端和普通日志。

## 12. 软件减法

本轮明确不做：

- 不启动第二个 DingTalk Stream 服务；
- 不新建第二个管理门户或日报系统；
- 不新建证据表；
- 不扩展旧 `/review`、`/admin`、`/mobile`、`/dashboard` 页面；
- 不用 RAG 替代实时生产数字；
- 不把数据中枢历史日报循环当成更高事实；
- 不用硬关键词阻止消息进入理解链；
- 不在事实闭环完成前继续堆大页面和新 Agent 管理功能。

后续可在访问日志证明无人使用后，另开任务合并重复页面、清理旧工作树和历史备份；本设计不顺手删除它们。

## 13. 分阶段交付

### 阶段 0：冻结错误

- 修复非法成品率；
- 禁止入库量替代总产量；
- 收紧 compare-only 绕过条件；
- 先让错误数字不再被当作正式事实。

### 阶段 1：Hermes 单入口留证

- 修改真实 NousResearch Hermes DingTalk 适配器；
- 所有事件先送入证据入口；
- 去掉硬关键词业务门槛；
- 文本和真实附件进入 `MultimodalEvidence`；
- 增加真实 Stream 健康指标。

### 阶段 2：统一事实读取和每日落库

- root owner、数据审计、日报共用证据读取器；
- MES 直接查询结果进入事实包；
- 调度器每日持久化事实包和快照；
- 缺失/冲突生成闭环动作。

### 阶段 3：管理端和 Hermes 验收

- `/manage` 展示真实来源、状态和 trace；
- Hermes 20 问采用真实值门禁；
- 最近三业务日 compare-only 对齐达到标准；
- 扫码填报和管理扫码登录回归通过。

### 阶段 4：部署收口

- 版本化 Hermes 生产修改；
- 统一部署流程和运行 SHA；
- 清理生产目录中的无主备份和报告文件，但必须先归档和确认引用关系。

## 14. 回滚

- Hermes 事件转发通过独立开关关闭，但保留 Hermes 原有回复能力；
- 事实采用规则可回退到上一口径版本；
- 已保存的证据和 trace 不删除；
- DailyFactBundle 新调度可单独禁用；
- 前端只增加现有接口字段，回滚不影响扫码填报和车间管理；
- 生产部署前保留数据库备份和两个仓库的已知可用 SHA。

## 15. 验收完成定义

只有以下条件全部满足，才能说“真实可投入使用”：

1. 真实钉钉文本和至少一个真实附件进入 `MultimodalEvidence`；
2. Hermes 不依赖固定关键词也能理解和查询生产问题；
3. MES/WMS 查询链只读、可追 trace；
4. 最近三个业务日均有持久化 DailyFactBundle run/snapshot；
5. 五个关键字段全部 confirmed、trace 非空、匹配率 100%；
6. 全字段 compare-only 匹配率不低于 95%；
7. `/manage` 不再显示非法成品率，并可查看来源、状态和 trace；
8. Hermes 20 问关键问题全部真实通过，不用全 missing 充数；
9. 扫码填报、车间管理扫码登录、权限边界和管理页面浏览器回归通过；
10. 数据中枢和 Hermes 的运行 SHA 可证明与部署提交一致。

## 16. 自审记录

- 与已确认方案 A 一致：Hermes Gateway 是唯一 Stream 入口。
- 覆盖用户最新规则：无硬群边界、中文身份、宽松理解、严格事实、MES 只读、数据中枢减法。
- 覆盖生产已发现问题：证据未入库、事实包未持久化、13.39% 对齐、819.08% 成品率、20 问全 missing、运行 SHA 不可证明。
- 没有把 `D:\输出skill` 当事实源。
- 没有新增门户、长期服务或证据表。
- 没有用统一 `±20` 掩盖不同单位的误差。
- 没有留下 TBD、TODO 或“以后再说”的必要实现项。
