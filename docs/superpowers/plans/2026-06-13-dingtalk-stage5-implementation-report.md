# 2026-06-13 RAG 口径知识库阶段五实施报告

## 1. 阶段结论

阶段五已完成本地服务闭环，可以标记完成。

本阶段完成的是“口径知识库底座”，不是完整管理端 RAG 页面，也不是接入外部向量库。现在 Agent 可以解释关键业务口径，并且回答会带来源；遇到“今天实时产量是多少”这类实时数值问题，会明确拒绝编造，让用户去实时接口或管理端页面查询。

## 2. 本阶段完成内容

- 新增 `backend/app/services/agent_knowledge_service.py`
  - `answer_question`：根据内置口径条目回答问题。
  - `build_grounded_prompt`：为后续 LLM 生成带来源的安全提示词。
  - `list_knowledge_entries`：列出当前知识条目。
- 新增 `backend/tests/test_agent_knowledge_service.py`
  - 覆盖全厂总产量口径、MES 与人工填报冲突口径、实时数值拦截、资料不足、带来源提示词。

## 3. 当前知识条目

- 全厂总产量与车间产量口径。
- MES 主数据与人工填报边界。
- 业务日时间口径。
- 图片语音证据边界。
- 补产量和发布日报审批规则。
- 钉钉群和车间权限边界。

这些条目都带 `source_ref`，用于告诉用户依据来自哪个文档或阶段报告。

## 4. 关键安全规则

- 知识库只解释规则，不查询实时产量。
- 实时数据问题直接返回 `blocked_realtime`。
- 回答必须带来源；没有来源就说资料不足。
- 后续如果接 LLM，也只能基于 `build_grounded_prompt` 里的来源回答。
- 不允许用知识库编造产量、能耗、合同量、成品率或人员信息。

## 5. 为什么本阶段不直接接完整向量库

当前最重要的是先把口径边界锁住，而不是一开始就上复杂向量库。

如果先接向量库但没有规则，风险是：

- Agent 把旧文档里的过期口径当成真。
- Agent 把实时数据问题当成知识问答来回答。
- Agent 给出没有来源的结论，用户无法追溯。

所以本阶段先做小而稳的口径知识库，后续再扩展成文档切片、管理端启停和向量检索。

## 6. 验收证据

已执行测试：

```text
python -m pytest -q backend/tests/test_agent_knowledge_service.py
结果：5 passed

python -m pytest -q backend/tests/test_agent_knowledge_service.py backend/tests/test_agent_operation_approval_service.py backend/tests/test_agent_multimodal_evidence_service.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_sqlite_model_compatibility.py backend/tests/test_alembic_version_width.py backend/tests/test_migration_chain.py
结果：33 passed

python -m pytest -q backend/tests/test_dingtalk_service.py backend/tests/test_dingtalk_cli.py backend/tests/test_dingtalk_login_route.py backend/tests/test_dingtalk_h5_login.py backend/tests/test_dingtalk_daily_report.py backend/tests/test_reporter_agent.py backend/tests/test_reminder_agent.py backend/tests/test_event_bus.py backend/tests/test_event_bus_persistence.py backend/tests/test_workflow_dispatcher.py backend/tests/test_ai_context_service.py
结果：78 passed
```

说明：

- 本阶段没有改前端页面，所以没有浏览器截图。
- 本阶段没有发真实钉钉消息。
- 本阶段没有查询生产实时数据。
- 本阶段没有接外部 LLM 或向量库。

## 7. gstack 五视角 review

### CEO 视角：9.8

这一步让 Agent 能解释“为什么这个数这样算”，能减少管理层反复问口径、现场反复争论的成本。

未到满分原因：还没有管理端知识库页面，也没有让真实用户在钉钉里问答。

### 工程师视角：9.8

实现小，边界清楚，不引入新表和外部依赖；先用测试锁住“带来源”和“拒绝实时编数”，后续可安全接 LLM 或向量库。

未到满分原因：目前是内置条目，不是可维护的数据库知识库。

### 设计师视角：9.8

知识条目已经按“标题、分类、来源、标签”整理，后续管理端可以做成清晰的口径卡片和来源列表。

未到满分原因：还没有 `/manage/rag` 页面。

### 安全审查视角：9.9

实时数据问题被拦截，回答必须有来源，资料不足会明确说不足。没有给 LLM 自由发挥空间，也没有接生产实时数据。

未到满分原因：后续接外部 LLM 前还要做 prompt 注入和文档污染测试。

### 真实用户视角：9.8

用户以后可以问“这个指标怎么算”，系统会给清楚来源；如果问“现在是多少”，系统不会乱说，会提示去实时页面看。

未到满分原因：还没有钉钉问答入口和管理端入口。

## 8. 阶段五是否可标记完成

可以标记完成。

完成口径：

- Agent 能解释指标口径。
- 回答带来源。
- 资料不足时不硬答。
- 实时数值问题不编造。
- 阶段一到五和原有钉钉链路回归通过。

下一阶段建议：

- 管理端新增 `/manage/rag` 知识库页面。
- 把口径条目迁入数据库或配置文件。
- 增加文档切片和启停状态。
- 接 LLM 前增加 prompt 注入测试。
- 钉钉问答入口只允许返回带来源回答。
