# Hermes Factory Brain Readiness Report

日期：2026-06-25

## 状态

blocked

不能标记为 `ready`。原因很简单：Hermes 工厂大脑专项链路已经通过，但后端全量测试还没有通过。按计划要求，只要全量门禁没过，就不能说“可正式打开生产流量”。

## 已验证

- 配置门禁
- 持久化模型
- Soul.md
- 长期规则
- 钉钉四条件采样
- RAG 路由
- 事实优先级和冲突展示
- LangChain 工具注册
- LangGraph 状态图
- DingTalk 入站分流
- Codex 施工记录
- 三场景 Harness
- CLI 支持 `--business-date` 的日报 smoke 命令
- Alembic 当前 head 已对齐 `0052_hermes_factory_brain`
- 前端单测和构建

## 关键命令

- `python -m pytest backend/tests/test_hermes_factory_brain_config.py backend/tests/test_hermes_factory_brain_models.py backend/tests/test_hermes_long_term_rule_service.py backend/tests/test_hermes_factory_brain_intent_service.py backend/tests/test_hermes_dingtalk_sampling_service.py backend/tests/test_hermes_rag_router_service.py backend/tests/test_hermes_fact_priority_service.py backend/tests/test_hermes_langchain_tools.py backend/tests/test_hermes_langgraph_app.py backend/tests/test_hermes_factory_brain_orchestrator.py backend/tests/test_hermes_codex_construction_service.py backend/tests/test_dingtalk_factory_brain_inbound.py backend/tests/test_hermes_factory_brain_acceptance.py -q --tb=short`：pass，`43 passed, 1 warning in 5.07s`
- `python -m pytest backend/tests/test_dingtalk_agent_inbound_route.py backend/tests/test_agent_command_rag_route.py backend/tests/test_rag_routes.py backend/tests/test_hermes_data_audit_service.py backend/tests/test_hermes_mes_read_service.py backend/tests/test_dingtalk_service.py -q --tb=short`：pass，`99 passed in 5.58s`
- `python backend/scripts/hermes_factory_brain_cli.py daily_report --business-date 2026-06-19`：pass，输出 `Hermes factory brain smoke: scenario=daily_report text=生成 2026-06-19 正式日报`
- `python -m pytest backend/tests/test_hermes_factory_brain_acceptance.py -q --tb=short`：pass，`7 passed in 2.44s`
- `python -m pytest backend/tests/test_migration_chain.py -q --tb=short`：pass，`4 passed in 13.87s`
- `npm --prefix frontend test -- --run`：pass，`701 passed`
- `npm --prefix frontend run build`：pass，构建成功
- `python -m pytest backend/tests -q --tb=short`：fail，`30 failed, 1679 passed, 3 skipped, 27 deselected, 48 warnings in 644.00s`

## 阻塞项

- 全量后端测试未通过。这是当前唯一阻止 `ready` 的硬门槛。
- 失败命令：`python -m pytest backend/tests -q --tb=short`
- 失败结果：`30 failed, 1679 passed, 3 skipped, 27 deselected, 48 warnings in 644.00s`
- 6 个 dry-run 导入测试在 `seed_real_master_data()` 时触发 `sqlalchemy.orm.exc.StaleDataError`，集中在 `equipment` 表更新行数不匹配。
- 4 个业务日边界测试仍按 `07:30` 预期，但当前运行结果是 `07:50` 口径。
- 13 个运维/发布文档测试找不到旧文档文件，例如 `docs/ssl-setup.md`、`docs/快速试跑运维手册.md`、`docs/部署文档.md`、`docs/launch-readiness-checklist.md`。
- 3 个日报 dashboard 合约测试出现额外 `MesStockRecord` 查询。
- 1 个 `publish_report` 工作流事件测试被 `template daily report is blocked` 拦住。
- 3 个 runtime config 测试受到当前本地 `.env` 中工作流相关开关影响，默认值断言不成立。

## 当前判断

Hermes 工厂大脑的新增模块可以作为“关闭生产开关下的代码合并候选”。它已经具备配置、数据表、钉钉入站、RAG、事实优先级、LangChain 工具、LangGraph 状态图、审计落库、Codex 施工记录和验收 Harness。

但它还不能作为“已可正式打开生产流量”的交付。全量测试没过时，如果直接打开 `HERMES_FACTORY_BRAIN_ENABLED=true`，风险不是 Hermes 单点，而是整个后端门禁还没有干净。

## 生产开关

- 继续保持 `HERMES_FACTORY_BRAIN_ENABLED=false`
- checkpoint schema setup 完成后再考虑灰度开启
- 首次开启只能小流量观察，重点看 `agent_runs`、`chat_inbox`、`external_message_logs` 和应用日志
- 若出现异常，直接设置 `HERMES_FACTORY_BRAIN_ENABLED=false`，DingTalk 入站会回落到旧 `handle_agent_command`

## 下一步

1. 先修全量测试的 6 类剩余阻塞。
2. 修完后重新跑 `python -m pytest backend/tests -q --tb=short`。
3. 全量通过后，把本报告状态从 `blocked` 改成 `ready`。
4. 再执行生产灰度，而不是直接全量放开。
