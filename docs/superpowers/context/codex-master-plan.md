# Codex Master Plan：xt-aluminnum 真实通讯、RAG、数据对齐、前端重构总计划

## 0. 项目身份

你正在修改 `xt-aluminnum / aluminum-bypass`。这是鑫泰铝业数据中枢，不是新项目，不是演示项目，不是纯 AI 聊天项目。系统已有 `/entry` 手机填报、`/manage` 管理审阅、钉钉 H5、日报、催报、实时流、权限、审计、部分 Agent、企业微信发布器、AI context 等基础。必须在现有系统上补强，不允许重写。

本轮目标是把系统打磨成可验证的生产级闭环：

1. 文本附件上传和 RAG 入库。
2. 真实钉钉通讯和 Agent 群消息。
3. Agent 通讯中台和 outbox。
4. 平台映射汇总算法与 `D:\输出skill` 高匹配。
5. Stitch MCP 辅助的中国风工业大气前端重构。
6. 云端数据库、云端系统、浏览器、钉钉真实验证。
7. 后端、前端、migration、浏览器、钉钉都有证据。

## 1. 工作方式

每轮按 gstack 执行：

G：Goal。先说本轮只做哪个小目标。
S：Scan。读现有代码、表结构、云端数据、页面、日志。
T：Test。确定本轮要跑的测试、构建、浏览器验收、钉钉验收。
A：Apply。做最小可回滚补丁。
C：Check。跑测试，查错误，浏览器实际看，钉钉实际验证。
K：Keep。记录证据、失败原因、修复结果和下一轮。

每轮按 superpower 执行：

spec：写极短规格。
plan：写具体步骤。
implement：改代码。
audit：检查权限、安全、兼容、数据口径。
tests：补测试。
evidence：留下命令结果、日志、截图说明、钉钉返回结果、数据匹配率。

不要大爆改。不要只改文档。不要伪代码。不要删除旧业务入口。失败后继续 loop 修。

## 2. 强制保留

必须保留：

`/entry`
`/manage`
钉钉 H5 免登
日报生成
日报推送
催报
实时流
权限隔离
审计日志
历史兼容重定向
现有部署脚本
现有测试基线

任何改动如果破坏这些，必须优先修复。

## 3. 真实配置和密钥处理

用户允许 Codex 使用真实钉钉 MCP、Stitch MCP、云端数据库、云端系统和浏览器验证。真实配置可以用于联调，但必须遵守工程安全：

可以从 MCP、云端 secret、本地 `.env`、临时运行环境读取。
不要提交到 Git。
不要写进 migration。
不要写进前端包。
不要打印到最终报告。
不要在测试日志里明文输出。
不要把真实 webhook、app secret、数据库密码写进 fixture。

最终报告只写“已使用真实配置验证”，不要明文列出密钥。

## 4. 阶段一：数据匹配基线

目标：读取云端数据库和 `D:\输出skill`，建立平台映射汇总算法匹配基线。

先读取 `docs/superpowers/context/output-skill-reconciliation.md`。如果 Codex 运行环境无法直接访问 `D:\输出skill`，要求将它挂载或同步到 `reference/output-skill/`。只读分析，不直接改生产数据。

任务：

1. 找到云端数据库里平台映射汇总算法相关表和字段。
2. 读取输出skill 文件结构。
3. 自动识别日期、生产日、班次、车间、机台、工序、卷号、随行卡、合同、产量、辅材、能耗、质量、停机、成材率、吨耗、成本等字段。
4. 生成字段映射表。
5. 检查单位差异：kg/吨、元/万元、百分比/小数。
6. 检查日期差异：自然日/生产日/班次跨日。
7. 检查别名差异：车间、机台、班组、工序、班次。
8. 检查状态差异：原始、提交、审核、确认、发布。
9. 计算字段级、记录级、汇总级、综合匹配率。
10. 输出推荐修正规则。

产出：

`docs/audits/output-skill-data-mapping-baseline.md`
`backend/tests/fixtures/output_skill_mapping_sample.*`
`mapping_reconciliation_service`
`/api/v1/mapping-reconciliation/*` 接口
前端 `/manage/mapping-reconciliation`

验收：

同口径字段尽量 95%+。达不到要解释差异来源。不能为了匹配率改原始生产数据。

## 5. 阶段二：文本附件上传和 RAG 入库

目标：管理员或有权限用户可以上传文本附件，系统切片入库，用于 RAG 查询和 Agent 回答。

支持文件：

`.txt`
`.md`
`.csv`
`.json`
`.log`

编码：

UTF-8
GBK

限制：

限制文件大小。
拒绝二进制文件。
拒绝可执行文件。
拒绝明显密钥文件入库，或提示风险。
敏感字段要做基础拦截，比如 secret、token、password、api_key、数据库连接。

表：

`rag_documents`
`rag_chunks`
`rag_query_logs`

如果已有相近表就复用，不重复造轮子。

接口：

`POST /api/v1/rag/documents/upload`
`GET /api/v1/rag/documents`
`GET /api/v1/rag/documents/{id}`
`DELETE /api/v1/rag/documents/{id}`
`POST /api/v1/rag/query`

切片：

500 到 800 中文字。
重叠 80 到 120 字。
表格按字段说明切。
日报按日期、车间、指标、异常、总结切。
维修记录按机台、故障、原因、处理、结果切。

检索：

先做 PostgreSQL 文本检索 fallback。
如果 pgvector 已存在或容易接入，再接 embedding 字段。
RAG 回答必须带来源。
没有事实就说数据不足，不能编。

前端：

`/manage/rag`，支持上传、列表、详情、切片预览、删除、测试问答。

测试：

上传成功。
非法文件拒绝。
编码识别。
切片生成。
权限隔离。
RAG 查询 fallback。
来源返回。
敏感字段拦截。

## 6. 阶段三：Agent 通讯中台

目标：外部群消息和系统事件都进入统一 Agent 编排层。

表：

`agent_profiles`
`communication_channels`
`agent_channel_bindings`
`agent_event_rules`
`agent_events`
`agent_runs`
`agent_outbox`
`chat_inbox`
`external_message_logs`

如果已有等价结构就复用。

统一入口：

`POST /api/v1/agent/command`

入参：

`channel`
`group_id`
`sender_external_id`
`text`
`agent_code`
`trace_id`

流程：

1. 保存 chat_inbox。
2. 识别用户身份。
3. 识别群绑定范围。
4. 校验权限。
5. 识别意图。
6. 查实时事实。
7. 查 RAG。
8. 生成回答。
9. 写 agent_runs。
10. 需要外发时写 agent_outbox。
11. 返回回答和证据。

输出模板：

`【范围｜时间】状态：绿/黄/橙/红；结论；关键数字；原因；建议动作；数据来源；可回复命令`

禁止：

禁止让大模型直接查数据库。
禁止编造产量、停机、辅材、质量、成本、人名。
禁止越权查车间。
禁止绕过审计。

## 7. 阶段四：真实钉钉接入

目标：真实钉钉可以作为群消息入口和外发通道。

必须复用：

`dingtalk_service`
钉钉 H5 免登
钉钉用户绑定
`send_work_notification`
`send_group_message`
`DINGTALK_NOTIFY_DRY_RUN`

新增或完善：

DingTalk Stream 或机器人入口。
钉钉消息适配器。
钉钉群绑定配置。
钉钉真实发送测试。
钉钉返回结果写入 `external_message_logs`。

能力：

群里 @Agent 问今日产量。
群里 @Agent 问哪个车间异常。
群里 @Agent 问 2 号机为什么停。
群里 @Agent 问辅材是否超耗。
系统主动发整点状态。
系统主动发停机升级。
系统主动发催报。
系统主动发日报。

所有外发先进入 `agent_outbox`，再发送。

outbox 要求：

支持 dry-run。
支持真实发送。
失败重试 3 次。
失败进入 dead-letter。
幂等 key。
同一异常 30 分钟去重。
记录发送时间、目标、返回、错误。

验收：

真实钉钉测试群收到至少一条测试消息。
群里至少一次 @Agent 得到回答。
外发日志可查。
失败可重试。
不在最终报告暴露密钥。

## 8. 阶段五：Agent 最小业务集

第一批 Agent：

全厂总控 Agent。
车间状态检测专员。
修停机专员。
上下机产量专员。
辅材消耗专员。
质量异常专员。
能耗成本专员。
管理层日报秘书。
催报 Agent。

规则默认值：

停机超过 10 分钟：黄色。
停机超过 30 分钟：橙色。
停机超过 60 分钟：红色。
产量低于计划 80%：橙色。
辅材超过定额 110%：黄色。
辅材超过定额 120%：橙色。
质量门禁 blocked：红色。
同一异常 30 分钟内不重复刷屏。

每个 Agent 都是确定性执行器。先查结构化事实，再查 RAG，再组织语言。大模型只能润色和解释，不能创造数字。

## 9. 阶段六：完整业务流程闭环

目标：把现场填报、MES/能耗/辅材/质量同步、平台映射汇总算法、输出skill 对齐、异常识别、Agent 判断、钉钉播报、群里追问、RAG 解释、管理员处理、日报生成、管理层查看、审计留痕全部串起来。

每条链路都要能回答：

数据从哪来。
怎么算。
和输出skill 差多少。
谁能看。
发给谁。
谁确认。
在哪里追溯。
哪里失败。
怎么重试。

## 10. 阶段七：Stitch MCP 前端重构

目标：重构前端为中国风工业大气，不要 AI 味。

必须使用 Stitch MCP 辅助设计，但最终必须落到真实 Vue 组件。禁止把整张截图当背景。禁止破坏接口、权限和路由。

视觉要求：

深墨黑。
钢铁灰。
青铜金。
暗红状态灯。
玉白文字。
细边框。
压暗纹理。
厚重卡片。
清晰表格。
工业驾驶舱大数字。
稳重筛选器。
抽屉和确认弹窗。
不要机器人头像。
不要霓虹科技球。
不要英文 AI 营销词。
不要花哨海报风。

页面：

`/manage/admin/agents`
`/manage/rag`
`/manage/channels`
`/manage/mapping-reconciliation`
`/manage/ai-assistant`
`/manage/live`
`/manage/today`
`/manage/production`
`/manage/workshop-dashboard`
`/manage/coils`
`/manage/fill-details`
`/manage/energy`
`/manage/alerts`
`/entry`

手机端保持现场工人可用：大按钮、大输入框、少字、单手操作。

## 11. 阶段八：浏览器真实验证

必须登录云端系统，用至少三种角色验证：

管理员。
车间主任。
主操。

至少验证页面：

`/manage/live`
`/manage/today`
`/manage/admin/agents`
`/manage/rag`
`/manage/channels`
`/manage/mapping-reconciliation`
`/entry`

至少完成动作：

上传一个文本附件。
查看切片。
做一次 RAG 查询。
配置或查看一个钉钉通道。
真实发送一条钉钉测试消息。
手动触发一次 Agent。
查看 outbox。
查看 external_message_logs。
跑一次输出skill 对齐。
查看匹配率和差异表。

记录截图说明或浏览器验收日志。

## 12. 阶段九：测试和 CI

后端必须跑：

`cd backend && pytest`
`alembic upgrade head`

前端必须跑：

`cd frontend && npm test`
`cd frontend && npm run build`

测试范围：

文本上传。
非法文件拒绝。
编码识别。
切片。
RAG fallback。
RAG 来源。
权限隔离。
agent command。
outbox。
钉钉 mock。
真实配置隔离。
重复消息去重。
数据匹配率。
口径差异解释。
前端页面渲染。
前端构建。

失败就继续 loop 修到通过。

## 13. 阶段十：最终交付

分支建议：

`feature/real-dingtalk-rag-agent-stitch-reconciliation`

commit message：

`feat: connect real dingtalk rag agents reconciliation and industrial UI`

最终报告必须包含：

改动摘要。
数据匹配结果。
输出skill 差异和推荐规则。
真实钉钉验证结果。
浏览器验证结果。
后端测试结果。
前端测试结果。
migration 结果。
未解决差异。
下一步建议。

最终报告禁止包含：

真实密钥。
数据库密码。
钉钉 app secret。
webhook 完整地址。
客户敏感信息。
员工隐私。
伪代码。
“核心功能还需要你自己实现”这类话。