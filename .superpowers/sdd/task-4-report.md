# Task 4 Report: Factory Task Planner And Capability Registry

## Status

DONE

## Scope

本次只实现 Task 4 要求的两块能力：

- `backend/app/services/hermes_capability_registry.py`
- `backend/app/services/hermes_factory_task_planner.py`

并新增对应测试：

- `backend/tests/test_hermes_capability_registry.py`
- `backend/tests/test_hermes_factory_task_planner.py`

没有改动 `AGENTS.md`，也没有碰用户明确禁止的未跟踪 spec/plan 文档。

## What I Changed

### 1. Capability Registry

新增 `list_factory_capabilities()`，返回固定能力清单：

- `sql-api-file`
- `dingtalk-context-ingestion`
- `rag-retriever`
- `browse-research`
- `computer-use-operator`
- `image-generation`

满足任务要求的优先级：

- SQL / API / 文件解析
- 钉钉上下文
- RAG
- browse
- computer use
- image generation

其中测试重点验证：

- 结构化数据优先于 browse
- browse 优先于 computer use
- image generation 的能力类型为 `image`

### 2. Factory Task Planner

新增 `plan_factory_task(normalized)`，按固定优先级生成执行步骤：

1. `dingtalk_context_ingestion`
2. `mes_read`
3. `wms_read`
4. `datahub_query`
5. `historical_report_lookup`
6. `rag_retriever`

附加规则：

- `output_mode` 为 `analysis` 或 `formal_report` 时，追加 `factory_analysis`
- `needs_artifact=True` 时，追加 `artifact_engine`

这和 brief 要求的数据源/工具优先级保持一致：

- 钉钉责任人文本/文件
- MES
- WMS
- 数据中枢
- 历史日报
- RAG

## TDD Evidence

### Red

先创建测试，再运行：

```powershell
cd backend
python -m pytest tests/test_hermes_capability_registry.py tests/test_hermes_factory_task_planner.py -q
```

结果：失败。

失败原因：

- `ModuleNotFoundError: No module named 'app.services.hermes_capability_registry'`
- `ModuleNotFoundError: No module named 'app.services.hermes_factory_task_planner'`

### Green

实现后再次运行同一命令：

```powershell
cd backend
python -m pytest tests/test_hermes_capability_registry.py tests/test_hermes_factory_task_planner.py -q
```

结果：

```text
3 passed in 2.17s
```

## Extra Verification

运行了额外检查：

```powershell
cd backend
python -m compileall app/services/hermes_capability_registry.py app/services/hermes_factory_task_planner.py
```

结果：通过。

```powershell
git diff --check
```

结果：通过。

## Assumptions

- Task 4 brief 已经是最终批准版本，所以本次没有额外扩展设计或改动其它服务。
- `normalize_factory_request()` 和共享 dataclass 已由前置任务提供，本次只消费现有接口，不重复实现。
- 允许写入范围里包含本报告文件，因此将完整执行记录落在这里。

## Final Outcome

Task 4 已按最小改动完成。

当前工厂大脑已经具备：

- 固定能力注册表
- 固定任务规划器
- 对应测试覆盖
- 红灯到绿灯的验证证据
