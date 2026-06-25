# 数据中枢减法瘦身审计报告

日期：2026-06-25

本报告只做分类和建议，不删除任何文件、表或生产数据。

| 分类 | 动作 | 路径 | 原因 |
|---|---|---|---|
| protect | keep | `artifacts/gstack-mes-audit-20260617/mes-sqlserver/WMS_Stock.sample.json` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/adapters/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/adapters/factory.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/adapters/iot_energy_adapter.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/adapters/llm.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/adapters/mes_adapter.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/adapters/mvc_mes_adapter.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/adapters/rest_api_mes_adapter.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/adapters/sqlserver_mes_adapter.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/adapters/wecom/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/adapters/wecom/group_bot.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/adapters/workflow/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/adapters/workflow/base.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/adapters/workflow/null_publisher.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/adapters/workflow/registry.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/adapters/xintai_mes_adapter.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/models/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/models/agent_communication.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/models/assistant.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/assistant_usage.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/attendance.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/base.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/consumable.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/energy.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/executive.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/models/hermes_data_audit.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/models/hermes_factory_brain.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/models/imports.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/master.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/models/mes.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/models/production.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/quality.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/models/rag.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/models/reconciliation.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/reports.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/rule_config.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/shift.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/system.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/models/user_preferences.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/agent.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/agent_management.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/ai.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/assistant.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/assistant_actions.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/attendance.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/auth.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/command.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/config.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/consumables.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/contracts.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/dashboard.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/routers/dingtalk.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/routers/energy.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/executive.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/export.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/factory_command.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/routers/hermes.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/routers/hermes_data_audit.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/routers/imports.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/inventory.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/mapping_reconciliation.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/master.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/routers/mes.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/routers/mobile.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/notifications.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/ocr.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/production.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/quality.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/routers/rag.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/routers/realtime.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/reconciliation.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/reports.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/rule_configs.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/search.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/telemetry.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/templates.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/user_preferences.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/users.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/routers/work_orders.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/agent_active_reporting_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/agent_command_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/services/agent_communication_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/services/agent_designated_operation_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/agent_knowledge_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/agent_management_overview_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/agent_multimodal_evidence_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/agent_operation_approval_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/agent_personal_bootstrap_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/agent_robot_bootstrap_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/ai_briefing_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/ai_context_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/ai_rules_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/anomaly_detection_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/app_connection_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/assistant_action_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/assistant_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/attendance_confirm_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/attendance_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/services/audit_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/services/bootstrap.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/command_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/config_readiness_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/consumable_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/contract_canonical_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/contract_delivery_target_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/contract_progress_projection_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/daily_energy_report_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/daily_production_canonical_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/daily_production_mapping_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/deterministic_orchestration_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/services/dingtalk_daily_report.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/dingtalk_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/dingtalk_templates.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/services/energy_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/equipment_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/exception_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/executive_constants.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/executive_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/factory_command_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/services/hermes_codex_construction_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_data_audit_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_datahub_diet_audit_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_day1_evidence_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_day1_harness_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_day1_intent_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_day1_orchestrator.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_day1_report_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_day1_source_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_dingtalk_sampling_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_fact_priority_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_fact_source_map_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_factory_brain_harness.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_factory_brain_intent_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_factory_brain_orchestrator.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_factory_brain_types.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_governance_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_intent_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_knowledge_seed_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_langchain_model.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_langchain_tools.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_langgraph_app.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_long_term_rule_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_memory_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_mes_read_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_professional_knowledge_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_rag_router_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_rag_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/hermes_soul_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/services/import_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/iot_energy_sync_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/leader_summary_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| freeze | freeze_and_observe | `backend/app/services/legacy_data_profile_service.py` | 疑似旧入口或参考资产，先冻结观察，不直接删除。 |
| review | manual_review | `backend/app/services/locked_fields_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/management_estimate_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/mapping_reconciliation_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/master_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/services/mes_assisted_fill_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/mes_extended_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/mes_fill_gap_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/mes_machine_match_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/mes_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/mes_supplement_readiness_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/mes_sync_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/services/missing_report_export_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/services/mobile_mes_supplement_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/services/mobile_reminder_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/mobile_report/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/mobile_report/_utils.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/mobile_report/flow_enrichment.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/mobile_report/lifecycle.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/mobile_report/shift_context.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/mobile_report/summary.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/mobile_report_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/ocr_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/owner_agents/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/owner_agents/consumable_stat.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/owner_agents/energy_chief.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/owner_agents/overhaul.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/owner_agents/planning.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/owner_agents/quality.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/owner_agents/recovery.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/owner_agents/shipment_outflow.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/services/owner_agents/storage.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/services/pass_count_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/pilot_metrics_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/pilot_observability_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/pilot_schedule_seed.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/processing_fee_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/production_output_scope.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/production_per_machine_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/production_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/quality_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/services/rag_embedding_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/rag_service.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/services/real_master_data.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/realtime_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/reconciliation_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/report/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/report/_utils.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/services/report/daily_fact_bundle.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| merge | merge_after_source_map | `backend/app/services/report/daily_overview_builder.py` | 属于报表加工层，可在 DailyFactBundle 稳定后逐步合并。 |
| protect | keep | `backend/app/services/report/daily_report_history.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| merge | merge_after_source_map | `backend/app/services/report/dashboard_builder.py` | 属于报表加工层，可在 DailyFactBundle 稳定后逐步合并。 |
| review | manual_review | `backend/app/services/report/lane_builders.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/services/report/mes_fact_bundle.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/report/mes_factory_packaging_fact.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/report/mes_factory_production_fact.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/report/mes_home_packaging_fact.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/report/mes_workshop_machine_reconciliation.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `backend/app/services/report/mes_workshop_mapping.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `backend/app/services/report/operation_analysis.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/report/output_skill_reconciliation.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/report/output_skill_report_parser.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/report/period_rollup.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/report/report_generation.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/report/template_daily_fact_sources.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/report/template_daily_field_contract.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| merge | merge_after_source_map | `backend/app/services/report/template_daily_report.py` | 属于报表加工层，可在 DailyFactBundle 稳定后逐步合并。 |
| review | manual_review | `backend/app/services/report_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/rule_config_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/scan_lookup_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/shift_engine.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/work_order/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/work_order/_access.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/work_order/_utils.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/work_order/amendment.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/work_order/crud.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/work_order/entry.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/work_order_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/workshop_template_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/yield_matrix_canonical_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/yield_matrix_delivery_target_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/services/yield_rate_deprecation_map_service.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/tasks/__init__.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/tasks/agent_outbox.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/tasks/daily_report.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/tasks/data_archive.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/tasks/fill_reminder.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `backend/app/tasks/iot_energy_sync.py` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `backend/app/tasks/mes_sync.py` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/VERCEL_PREVIEW.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/api-system-lane-spec.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/audits/0730-template-daily-report-field-coverage.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/2026-05-02-cleanup-round2-test-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/2026-05-06-xintai-report-source-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/2026-05-12-live-fill-mes-binding-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/2026-05-13-active-goal-completion-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/2026-05-17-a11y-contrast-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/2026-05-17-backend-completion-gate-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/2026-05-17-completion-summary.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/2026-05-17-e2e-full-run-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/2026-05-17-full-completion-evidence.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/2026-05-17-system-smoke-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/output-skill-data-mapping-baseline.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/real-rag-dingtalk-agent-reconciliation-gap-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/audits/template-daily-report-outputskill-baseline.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/cli-rollout-lane-spec.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/contracts/2026-05-21-mes-data-gap.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/datahub-deprecation-register.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/deploy/current-state.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/deploy/go-live.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/deploy/perf-report.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/deploy/runbook.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/domain/calibration-log.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/domain/xintai-real-fields.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/functional-audit-2026-05-27-pass2.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/functional-audit-2026-05-27.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/hermes/fact-source-map.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/import-templates/MES导出样例说明.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/import-templates/打卡导入样例说明.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/import-templates/排班导入样例说明.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/import-templates/生产数据导入样例说明.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/import-templates/能耗导入样例说明.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/known-gaps-and-todos.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/launch-readiness-checklist.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/mes-api-integration-checklist.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/mes-data-hub-hermes-fact-map-2026-06-19.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/mes-page-table-mapping.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/mes-xintaily-full-page-table-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/mes-xtmijd-alignment-matrix.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/ssl-setup.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/superpowers/audits/2026-05-16-phase-4-8-done.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-05-16-status-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-auth-permission-health-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-backend-architecture-risk-map.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-browser-core-flow-experience-review.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-coil-trace-mes-supplement-command-screen-plan.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-core-api-contract-test-plan.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-frontend-experience-retention-review.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-frontend-information-architecture-review.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-page-api-coverage-matrix.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-page-api-dataflow-coverage-review.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-phase1-tdd-remediation-backlog.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-settings-terminal-binding-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-11-testing-qa-gates-review.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-12-iot-energy-field-handoff-checklist.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-12-pc-terminal-coil-realtime-office-hours.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/audits/2026-06-12-terminal-binding-coil-realtime-completion-audit.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/context/026-06-14-agent-comm-rag-frontend.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/superpowers/context/codex-loop-goal.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/context/codex-master-plan.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/context/output-skill-reconciliation.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-02-ai-agent-enhancement-office-hours.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-04-mes-sqlserver-direct-connection-office-hours.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-06-stitch-industrial-blue-manage-ui.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-09-mes-assisted-fill-simplification.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-09-mes-direct-data-realtime-screens-office-hours.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-09-mes-fill-report-optimization-route.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-11-mes-primary-coil-flow-command-screen-reviewed.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-frontend-image2-stitch-mes-primary-final-executable-plan.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-frontend-second-pass-stitch-image2-taste-final-reviewed-plan.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-frontend-second-pass-stitch-image2-taste-office-hours.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-stitch-image2-frontend-redesign-total-plan.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-stitch-image2-phase1-system-map.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-stitch-image2-phase10-final-qa-ship.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-stitch-image2-phase2-qa-baseline.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-stitch-image2-phase3-design-freeze.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-stitch-image2-phase5-visual-system-check.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-stitch-image2-phase6-core-pages-check.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-stitch-image2-phase7-business-pages-check.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-stitch-image2-phase8-admin-mobile-check.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-12-stitch-image2-phase9-metric-contract-check.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-multimodal-active-agent-reporting-plan.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage0-readiness-report.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage1-4-validation-and-frontend-gate.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage1-implementation-report.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage2-implementation-report.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage3-implementation-report.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage4-implementation-report.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage5-implementation-report.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage6-implementation-report.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage7-implementation-report.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage8-implementation-report.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-13-dingtalk-stage9-frontend-stitch-taste-validation-report.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/superpowers/plans/2026-06-17-0730-forecast-final-role-cleanup.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-17-template-daily-report-facts.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-18-daily-report-agent-workflow-and-workshop-cards-plan.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/plans/2026-06-18-mes-daily-dashboard-reconciliation.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/superpowers/plans/2026-06-19-hermes-high-privilege-data-audit-and-hub-correction-plan.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/superpowers/plans/2026-06-20-xintaily-daily-report-manual-alignment.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/superpowers/plans/2026-06-21-hermes-day1-super-brain-mvp-plan.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-22-hermes-daily-fact-bundle-phase2-plan.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-25-hermes-factory-brain-upgrade-plan.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/plans/2026-06-25-hermes-knowledge-and-datahub-diet-plan.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/superpowers/reports/2026-06-12-frontend-image2-stitch-mes-primary-execution-review.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/reports/2026-06-12-frontend-second-pass-final-qa.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/reports/2026-06-12-frontend-second-pass-phase0-baseline.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/superpowers/reports/2026-06-25-hermes-factory-brain-readiness.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/reports/datahub-diet-audit-2026-06-25.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/superpowers/specs/2026-06-10-mes-triggered-mobile-supplement-design.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/specs/2026-06-17-0730-forecast-0930-final-role-cleanup-design.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/specs/2026-06-17-machine-account-duty-person-agent-design.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/superpowers/specs/2026-06-18-daily-report-agent-workflow-and-workshop-cards-design.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/superpowers/specs/2026-06-19-hermes-high-privilege-data-audit-and-hub-correction-design.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/specs/2026-06-21-hermes-day1-super-brain-mvp-design.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/specs/2026-06-22-hermes-daily-fact-bundle-phase2-design.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/specs/2026-06-25-hermes-factory-brain-upgrade-design.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `docs/superpowers/specs/2026-06-25-hermes-knowledge-and-datahub-diet-design.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/system-understanding-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-admin-login-auth-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/system-understanding-ai-dingtalk-communication-2026-06-14.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/system-understanding-alert-energy-attendance-export-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-consolidated-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-dashboard-live-dataflow-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-database-api-route-map-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-manage-admin-permission-map-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-manage-core-qa-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `docs/system-understanding-master-data-permission-audit-2026-06-14.md` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `docs/system-understanding-mes-production-dashboard-dataflow-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-mobile-entry-dataflow-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-role-permission-route-flow-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-role-qa-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-runtime-map-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-today-production-dataflow-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/system-understanding-users-permissions-master-mobile-2026-06-14.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/team-workflow/2026-05-10-hud-four-way-handoff.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| freeze | freeze_and_observe | `docs/ui-reference/DESIGN_REVERSE_PLAN.md` | 疑似旧入口或参考资产，先冻结观察，不直接删除。 |
| freeze | freeze_and_observe | `docs/ui-reference/GAP_MATRIX.md` | 疑似旧入口或参考资产，先冻结观察，不直接删除。 |
| freeze | freeze_and_observe | `docs/ui-reference/IMAGE2_PROMPTS.md` | 疑似旧入口或参考资产，先冻结观察，不直接删除。 |
| freeze | freeze_and_observe | `docs/ui-reference/REFERENCE_MANIFEST.md` | 疑似旧入口或参考资产，先冻结观察，不直接删除。 |
| freeze | freeze_and_observe | `docs/ui-reference/UI_TARGET_SPEC.md` | 疑似旧入口或参考资产，先冻结观察，不直接删除。 |
| review | manual_review | `docs/usability/2026-05-20-worker-test-task-card.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/企业微信生产入口准备清单.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/供应商对接手册-前端重构版.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/发布冻结基线清单.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/快速试跑运维手册.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/模板.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/现场UAT清单.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `docs/部署文档.md` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/Login.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/ai/AiChatMessage.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/ai/AiConversationList.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/ai/AiWorkstation.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/attendance/AttendanceDetail.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/attendance/AttendanceOverview.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/attendance/ExceptionList.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/contracts/ContractsCenter.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/energy/EnergyCenter.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `frontend/src/views/entry/EntryDrafts.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `frontend/src/views/factory-command/DestinationScreen.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/factory-command/FactoryCommandShell.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/inventory/InventoryCenter.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/manage/admin/AgentManagementPage.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/manage/admin/SystemSettingsPage.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/manage/alerts/AlertsPage.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/manage/channels/CommunicationChannelsPage.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `frontend/src/views/manage/coils/CoilTracePage.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `frontend/src/views/manage/fill-details/FillDetailsPage.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `frontend/src/views/manage/live/AnimatedMetricValue.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/live/LiveDashboardPage.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/live/LiveDataStatePanel.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/live/LiveEventRail.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/live/LiveMachineCard.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/live/LiveMachineDrawer.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/live/LiveMachineMatrix.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/live/LiveMarketTicker.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/live/LiveMetricCompareCard.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/live/LiveProcessFlow.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `frontend/src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `frontend/src/views/manage/production/ProductionPage.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/rag/RagKnowledgePage.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/manage/today/TodayPage.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `frontend/src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/master/AliasMapping.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/master/MesTerminalBinding.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/master/QRCodePrint.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/master/RuleConfigCenter.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/master/UserManagement.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/master/Workshop.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| protect | keep | `frontend/src/views/mobile/AttendanceConfirm.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/mobile/CoilEntryWorkbench.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/mobile/ConsumableEntry.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| freeze | freeze_and_observe | `frontend/src/views/mobile/MobileBottomNav.vue` | 疑似旧入口或参考资产，先冻结观察，不直接删除。 |
| protect | keep | `frontend/src/views/mobile/MobileEntry.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/mobile/OCRCapture.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| freeze | freeze_and_observe | `frontend/src/views/mobile/ReminderList.vue` | 疑似旧入口或参考资产，先冻结观察，不直接删除。 |
| protect | keep | `frontend/src/views/mobile/ShiftReportForm.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/mobile/ShiftReportHistory.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| protect | keep | `frontend/src/views/mobile/UnifiedEntryForm.vue` | 涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。 |
| review | manual_review | `frontend/src/views/quality/QualityDetail.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/reconciliation/ReconciliationDetail.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/reports/LiveDashboard.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| review | manual_review | `frontend/src/views/reports/ReportList.vue` | 需要结合引用、路由、测试和生产访问再判断。 |
| freeze | freeze_and_observe | `frontend/src/views/review/GovernanceCenter.vue` | 疑似旧入口或参考资产，先冻结观察，不直接删除。 |
| review | manual_review | `frontend/src/views/shift/ShiftDetail.vue` | 需要结合引用、路由、测试和生产访问再判断。 |

硬规则：本阶段没有直接删除动作。所有删除必须另开计划，并提供回滚办法。