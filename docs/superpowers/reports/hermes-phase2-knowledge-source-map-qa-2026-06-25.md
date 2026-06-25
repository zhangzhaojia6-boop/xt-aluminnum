# Hermes Phase-2 Knowledge and Source Map QA

日期：2026-06-25

## 状态

ready

## 已验证

- 事实来源地图可加载。
- 事实来源地图不含敏感字段。
- Hermes source_map 工具可解释核心指标来源。
- 专业知识种子可导入。
- RAG 仍优先使用专业知识库。
- 数据中枢减法审计不执行删除。
- Hermes 来源型回答必须包含来源和 trace_id。

## 关键命令

- `python -m pytest backend/tests/test_hermes_fact_source_map_service.py backend/tests/test_hermes_knowledge_seed_service.py backend/tests/test_hermes_langchain_tools.py backend/tests/test_hermes_phase2_source_map_acceptance.py backend/tests/test_hermes_professional_knowledge_service.py -q --tb=short`: pass
- `python -m pytest backend/tests/test_hermes_factory_brain_acceptance.py backend/tests/test_hermes_factory_brain_orchestrator.py backend/tests/test_hermes_rag_router_service.py backend/tests/test_dingtalk_factory_brain_inbound.py backend/tests/test_rag_routes.py -q --tb=short`: pass
- `python -m compileall backend/app/services backend/scripts`: pass
- `git diff --check`: pass

## 结论

本阶段可以进入生产灰度验证，但只允许导入知识、增加来源解释和生成减法审计报告。不得直接删除生产表、生产路由或证据链。
