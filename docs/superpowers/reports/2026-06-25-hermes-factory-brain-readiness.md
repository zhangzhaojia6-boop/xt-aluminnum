# Hermes Factory Brain Readiness Report

日期：2026-06-25

## 状态

ready

Hermes 工厂大脑计划内代码、数据表、钉钉入站、RAG、LangChain/LangGraph、Codex 施工记录、三场景 Harness、CLI smoke、checkpoint 初始化和全量后端门禁均已通过。

这个结论表示“代码可以进入生产灰度”。是否打开生产流量，仍由运行时开关控制。

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
- LangGraph checkpoint schema 初始化
- 前端单测和构建
- 后端全量测试

## 关键命令

- `python -m pytest backend/tests/test_hermes_factory_brain_config.py backend/tests/test_hermes_factory_brain_models.py backend/tests/test_hermes_long_term_rule_service.py backend/tests/test_hermes_factory_brain_intent_service.py backend/tests/test_hermes_dingtalk_sampling_service.py backend/tests/test_hermes_rag_router_service.py backend/tests/test_hermes_fact_priority_service.py backend/tests/test_hermes_langchain_tools.py backend/tests/test_hermes_langgraph_app.py backend/tests/test_hermes_factory_brain_orchestrator.py backend/tests/test_hermes_codex_construction_service.py backend/tests/test_dingtalk_factory_brain_inbound.py backend/tests/test_hermes_factory_brain_acceptance.py -q --tb=short`：pass，`43 passed, 1 warning in 5.07s`
- `python -m pytest backend/tests/test_dingtalk_agent_inbound_route.py backend/tests/test_agent_command_rag_route.py backend/tests/test_rag_routes.py backend/tests/test_hermes_data_audit_service.py backend/tests/test_hermes_mes_read_service.py backend/tests/test_dingtalk_service.py -q --tb=short`：pass，`99 passed in 5.58s`
- `python backend/scripts/hermes_factory_brain_cli.py daily_report --business-date 2026-06-19`：pass，输出 `Hermes factory brain smoke: scenario=daily_report text=生成 2026-06-19 正式日报`
- `python -m pytest backend/tests/test_hermes_factory_brain_acceptance.py -q --tb=short`：pass，`7 passed in 2.44s`
- `python -m pytest backend/tests/test_migration_chain.py -q --tb=short`：pass，`4 passed in 13.87s`
- `npm --prefix frontend test -- --run`：pass，`701 passed`
- `npm --prefix frontend run build`：pass，构建成功
- `PYTHONPATH=backend DATABASE_URL=postgresql://... python backend/scripts/setup_langgraph_checkpoint.py`：pass，输出 `langgraph checkpoint schema ready`
- `python -m pytest backend/tests -q --durations=10`：pass，`1712 passed, 3 skipped, 27 deselected, 48 warnings in 647.15s`

## 本轮关闭的阻塞

- dry-run 导入中的 `StaleDataError` 已修复。
- 业务日边界测试已统一到当前 `07:50` 口径。
- 缺失的发布、试跑、入口和 API/CLI 文档已补齐。
- dashboard 合约测试不再被轻量假库的 MES 明细查询误伤。
- `publish_report` 工作流事件测试已补齐 ready 模板日报前提。
- runtime config 测试已隔离本机 `.env` 和前序测试环境变量污染。

## 生产开关

- 默认仍建议保持 `HERMES_FACTORY_BRAIN_ENABLED=false`，由运维按灰度窗口开启。
- 首次开启建议只对最高权限用户和指定钉钉入口灰度。
- 观察重点：`agent_runs`、`chat_inbox`、`external_message_logs`、LangGraph checkpoint 表和应用日志。
- 若出现异常，设置 `HERMES_FACTORY_BRAIN_ENABLED=false`，DingTalk 入站会回落到旧 `handle_agent_command`。

## 当前判断

Hermes 工厂大脑已经从“功能候选”推进到“可生产灰度”。它现在不只是日报统计助手，而是具备工厂数据接入、知识检索、事实冲突解释、钉钉采样、长期规则记忆、LangGraph 编排和 Codex 施工记录的基础超级大脑框架。
