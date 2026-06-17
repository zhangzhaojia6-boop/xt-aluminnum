# 真实 RAG、钉钉 Agent、输出skill 对齐与工业前端第一轮缺口审计

日期：2026-06-17

本轮目标不是写新功能，而是接手现有能力，确认当前代码里哪些链路已经存在、哪些能跑、哪些还没有真实验收。系统名称按项目规范使用 `鑫泰铝业 数据中枢`。

## 1. 总结

| 模块 | 当前事实 | 当前判断 |
|---|---|---|
| RAG 知识库 | 后端路由、服务、模型、迁移、前端页面和测试均存在 | 底座可跑，仍缺浏览器真实上传验收 |
| 输出skill 对齐 | 后端服务、运行记录表、dry-run 规则、前端页面和测试均存在 | 底座可跑，真实业务日全量匹配率未证明达标 |
| Agent command | `/api/v1/agent/command` 已存在，能查业务事实和 RAG，能写 Agent 运行记录 | 底座可跑，仍需真实问题集验收 |
| Agent outbox | `agent_outbox_messages`、重试、dead-letter、去重窗口和调度任务均存在 | 底座可跑，真实外发链路仍需测试通道验证 |
| external_message_logs | 外部通讯日志表和查询链路存在 | 可追溯，仍需真实钉钉返回写入验证 |
| dingtalk_service | 工作通知、群消息、dry-run、失败返回体保留能力存在 | 代码可测，真实测试群发送未在本轮执行 |
| 前端五个管理页 | 路由、导航、页面、API 客户端和定向测试均存在 | 可构建基础明确，生产未登录状态会跳登录页 |

## 2. 代码和迁移证据

| 能力 | 关键文件 | 证据 |
|---|---|---|
| RAG 路由 | `backend/app/routers/rag.py` | 存在 upload/list/detail/delete/query 五类接口 |
| RAG 服务 | `backend/app/services/rag_service.py` | 支持文本校验、切片、查询、来源、查询日志 |
| RAG 表 | `backend/app/models/rag.py` | `rag_documents`、`rag_chunks`、`rag_query_logs` 已定义 |
| RAG 迁移 | `backend/alembic/versions/0041_rag_documents.py` | 迁移链中存在 `rag documents and chunks` |
| 输出skill 对齐路由 | `backend/app/routers/mapping_reconciliation.py` | 存在 `/sources`、`/run`、`/runs/{id}`、`/differences`、规则 dry-run |
| 输出skill 对齐服务 | `backend/app/services/mapping_reconciliation_service.py` | 存在输出skill 文件读取、系统行拉平、差异计算、规则建议 |
| 对齐运行表 | `backend/app/models/reconciliation.py` | `mapping_reconciliation_runs` 已定义 |
| 对齐迁移 | `backend/alembic/versions/0045_mapping_reconciliation_runs.py` | 迁移链 head 为对齐运行记录 |
| Agent command | `backend/app/routers/agent.py`、`backend/app/services/agent_command_service.py` | `/api/v1/agent/command` 已挂载，服务层包含事实查询和 RAG 查询 |
| Agent 通讯 | `backend/app/services/agent_communication_service.py` | 存在注册 Agent、通道、绑定、排队、调度、日志查询 |
| Agent 通讯表 | `backend/app/models/agent_communication.py` | `agent_profiles`、`communication_channels`、`agent_outbox_messages`、`agent_runs`、`external_message_logs` 已定义 |
| Agent 通讯迁移 | `0040`、`0043`、`0044` | 已覆盖基础表、重试 dead-letter、30 分钟去重相关字段 |
| 钉钉服务 | `backend/app/services/dingtalk_service.py` | 存在 `send_work_notification()` 和 `send_group_message()` |
| 路由挂载 | `backend/app/main.py` | 已挂载 `/agent`、`/agent-management`、`/mapping-reconciliation`、`/rag`、`/dingtalk` |

迁移链检查结果：

```text
0039_iot_energy_shadow -> 0040_agent_communication_outbox
0040_agent_communication_outbox -> 0041_rag_documents
0041_rag_documents -> 0042_agent_command_audit
0042_agent_command_audit -> 0043_agent_outbox_retry_dead_letter
0043_agent_outbox_retry_dead_letter -> 0044_agent_outbox_dedupe_window
0044_agent_outbox_dedupe_window -> 0045_mapping_reconciliation_runs
```

## 3. 前端入口证据

| 页面 | 路由 | 导航 | 页面文件 | 当前事实 |
|---|---|---|---|---|
| 通讯治理台 | `/manage/admin/agents` | 有 | `AgentManagementPage.vue` | 有 outbox 调度、外部日志展示 |
| 知识库资料 | `/manage/rag` | 有 | `RagKnowledgePage.vue` | 有上传、列表、切片预览、问答入口 |
| 通讯通道 | `/manage/channels` | 有 | `CommunicationChannelsPage.vue` | 有通道、outbox、外部日志展示 |
| 输出skill 对齐 | `/manage/mapping-reconciliation` | 有 | `MappingReconciliationPage.vue` | 有来源、运行、匹配率、差异、规则 dry-run |
| AI 助手 | `/manage/ai-assistant` | 有 | `AiWorkstation.vue` | 有管理端 AI 工作台入口 |

生产浏览器只读检查：

| 页面 | HTTP | 实际落点 | 控制台 |
|---|---:|---|---|
| `/manage/admin/agents` | 200 | `/login?redirect=/manage/admin/agents` | 无红错 |
| `/manage/rag` | 200 | `/login?redirect=/manage/rag` | 无红错 |
| `/manage/channels` | 200 | `/login?redirect=/manage/channels` | 无红错 |
| `/manage/mapping-reconciliation` | 200 | `/login?redirect=/manage/mapping-reconciliation` | 无红错 |
| `/manage/ai-assistant` | 200 | `/login?redirect=/manage/ai-assistant` | 无红错 |

小白版说明：这证明生产域名能打开这些地址，未登录会被系统拦到登录页。它不等于登录后的按钮、上传、发送都已经真实验收。

## 4. 测试证据

后端定向测试：

```text
python -m pytest backend/tests/test_rag_routes.py backend/tests/test_mapping_reconciliation_route.py backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_communication_service.py backend/tests/test_dingtalk_service.py backend/tests/test_agent_management_router.py -q
89 passed in 52.41s
```

前端定向测试：

```text
node --test tests/ragKnowledgePage.test.js tests/mappingReconciliationPage.test.js tests/agentManagementPage.test.js tests/channelManagementPage.test.js tests/aiAssistantUiContract.test.js
37 passed
```

迁移链检查：

```text
python -m alembic history -r 0040:head
通过，head 为 0045_mapping_reconciliation_runs
```

## 5. 当前缺口

| 优先级 | 缺口 | 影响 |
|---|---|---|
| 高 | 真实 `D:\输出skill` 业务日全量匹配率未完成证明 | 不能宣称输出skill 对齐达到 95% |
| 高 | 最新输出skill 文件里有大量 `.png`，当前不能稳定逐字段解析 | 图片报表不能算已匹配，只能算待 OCR 或待结构化 |
| 高 | RAG 还未做浏览器真实上传、查看切片、查询、删除验收 | 代码测试通过不等于现场页面闭环通过 |
| 高 | Agent command 还未用指定六类真实问题集跑浏览器/API 验收 | 不能证明回答格式和事实来源都满足现场要求 |
| 高 | 钉钉真实测试群发送未执行 | 不能证明非 dry-run 通道、真实返回和日志闭环可用 |
| 中 | 生产浏览器只验证了未登录拦截 | 登录后页面交互、接口返回和按钮状态仍需验收 |
| 中 | 前端五页已有工业视觉痕迹，但还未按中国风工业大气目标做完整 taste/Stitch 验收 | 视觉达标不能只靠代码标记 |
| 中 | 本轮没有跑全量 `pytest`、`npm test`、`npm run build` | 只能说明定向链路通过，不能替代最终门禁 |

## 6. 下一轮修复点

下一轮目标建议只做 `D:\输出skill` 对齐，不碰其他功能。

执行顺序：

1. 只读列出 `D:\输出skill` 文件类型和最近业务日文件。
2. 跑 `/api/v1/mapping-reconciliation/sources`。
3. 跑 `/api/v1/mapping-reconciliation/run`，选择可结构化文件先算真实业务日匹配率。
4. 把 `.png` 作为 `待解析文件` 单独统计，不计入已达成匹配率。
5. 如前端缺少 `真实全量状态`、`可解析覆盖率`、`图片待解析数量`，先写失败测试，再补兼容字段展示。
6. 禁止为了提高匹配率改生产原始数据。

## 7. 安全边界

- 本轮没有读取、打印、提交任何真实密钥、钉钉 webhook 或数据库密码。
- 本轮没有真实发送钉钉消息。
- 本轮没有修改生产数据。
- 本轮没有删除旧入口。
- 本轮新增内容只是一份审计文档。

## 8. 后续阶段实施记录

### 8.1 输出skill 对齐

已完成的小修：

- `/api/v1/mapping-reconciliation/sources` 支持 `limit` 参数，页面可以只展示有限文件列表。
- `file_summary` 改为统计全部可见参考文件，不再被列表条数截断。
- 参考文件新增 `parse_status`：`parseable` 表示可直接试算，`image_pending_ocr` 表示图片待 OCR，`unsupported` 表示暂不支持。
- 默认忽略 `.pytest_cache`、`__pycache__` 等运行缓存目录，避免把测试缓存误算成业务资料。
- 前端对账页新增“可解析覆盖率”和“图片待解析”指标，并在文件列表展示解析状态。

真实只读证据：

```text
D:\输出skill 可读
可见文件：4381
可直接解析：560
图片待 OCR：273
暂不支持：3548
可解析覆盖率：12.78%
```

本地真实匹配率阻塞：

```text
本地后端当前 DATABASE_URL 指向 sqlite ./local-dev.db
该库没有 mes_workshop_process_records 等业务表
因此不能用本地库冒充真实生产库计算匹配率
```

小白版说明：参考资料已经能看出“哪些能算、哪些是图片、哪些不能算”。但真正的“系统数字和参考资料数字匹配多少”必须连到有真实业务表的库，不能拿空开发库算。

阶段测试：

```text
python -m pytest backend/tests/test_mapping_reconciliation_route.py backend/tests/test_mapping_reconciliation_service.py -q
27 passed

node --test tests/mappingReconciliationPage.test.js
14 passed
```

### 8.2 RAG 知识库

本轮未改 RAG 生产代码。现有代码已经覆盖：

- txt、md、csv、json、log 文本类资料入口。
- UTF-8、GBK 解码。
- 可执行文件、二进制文件、敏感密钥、Bearer token、私钥文本拒绝入库。
- 700 字左右切片、100 字重叠。
- list、detail、delete、query。
- 查询返回来源；无可靠来源时返回“数据不足”。

阶段测试：

```text
python -m pytest backend/tests/test_rag_routes.py -q
19 passed
```

### 8.3 Agent command

本轮未改 Agent command 生产代码。现有代码已经覆盖：

- `/api/v1/agent/command` 写入 `chat_inbox_messages` 和 `agent_runs`。
- 回答先查业务事实和 RAG，回答格式统一为“范围时间、状态、结论、关键数字、原因、建议动作、数据来源、可回复命令”。
- 已有测试覆盖今日产量、异常、停机、辅材、能耗成本、质量异常。
- outbox 回复支持绑定通道、权限边界、30 分钟去重。

阶段测试：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py -q
23 passed
```

### 8.4 钉钉与 outbox

本轮未真实发送钉钉消息，原因是当前没有明确测试群会话 ID，也没有用户明确要求使用自定义机器人发群消息。

已验证能力：

- dry-run 只写发件箱和外发日志，不调用真实发送。
- 非 dry-run 会调用发送器，并把供应商返回写入 `external_message_logs`。
- 失败会重试，最多 3 次后进入 dead-letter。
- 未到重试时间不会重复发送。
- 同一异常 30 分钟内会去重。

阶段测试：

```text
python -m pytest backend/tests/test_agent_communication_service.py -q
10 passed

python -m pytest backend/tests/test_dingtalk_service.py -q
12 passed
```

### 8.5 前端五页

Stitch MCP 状态：

- 已创建参考项目：`projects/13127113519813389895`。
- 生成屏幕时 Stitch 网络请求失败，随后 `list_screens` 返回空对象。
- 因此本轮没有把 Stitch 生成稿落进代码，只按既有工业视觉规则和真实组件测试继续验收。

前端现状：

- `/manage/admin/agents`、`/manage/rag`、`/manage/channels`、`/manage/mapping-reconciliation`、`/manage/ai-assistant` 均有真实 Vue 页面和路由测试。
- 页面不依赖假数据，关键按钮和数据区连接真实 API helper。
- 手机端 `/entry` 未在本轮改动。

阶段测试：

```text
node --test tests/ragKnowledgePage.test.js tests/mappingReconciliationPage.test.js tests/agentManagementPage.test.js tests/channelManagementPage.test.js tests/aiAssistantUiContract.test.js
38 passed
```
