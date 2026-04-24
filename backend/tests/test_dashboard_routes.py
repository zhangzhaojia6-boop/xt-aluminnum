from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.core.permissions import get_current_manager_user
from app.core.deps import get_current_user
from app.main import app
from app.schemas.dashboard import FactoryDashboardResponse, WorkshopDashboardResponse
from app.services import report_service


class DummyDB:
    pass


def test_factory_dashboard_exposes_leader_summary_payload(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user():
        return SimpleNamespace(
            id=7,
            role='manager',
            is_admin=False,
            is_manager=True,
            is_reviewer=False,
            workshop_id=None,
            data_scope_type='all',
        )

    def fake_dashboard(_db, *, target_date):
        assert target_date == date(2026, 4, 10)
        return {
            'target_date': '2026-04-10',
            'leader_summary': {
                'summary_text': '2026-04-10，今日产量 123.40 吨，异常 0 条。',
                'summary_source': 'deterministic',
            },
            'leader_metrics': {
                'today_total_output': 123.4,
                'energy_per_ton': 3.21,
                'contract_weight': 98.7,
                'yield_rate': 96.5,
                'shipment_weight': 55.0,
                'storage_inbound_area': 1200.0,
            },
            'history_digest': {
                'daily_snapshots': [
                    {'date': '2026-04-09', 'output_weight': 118.0},
                    {'date': '2026-04-10', 'output_weight': 123.4},
                ],
                'month_archive': {'total_output': 1234.5},
                'year_archive': {'total_output': 5678.9},
            },
            'runtime_trace': {
                'source_lanes': [
                    {
                        'key': 'operator',
                        'label': '主操直录',
                        'actor_label': '机台主操',
                        'detail': '12 / 12 班次已到位',
                        'stage_label': '自动确认',
                        'stage_detail': '11 条已收口',
                        'result_label': '产量 / 在制 / 班次原始值',
                        'result_targets': ['今日产量', '今日上报状态'],
                        'status': 'healthy',
                    },
                    {
                        'key': 'owner',
                        'label': '专项补录',
                        'actor_label': '成品库 / 水电气 / 计划科',
                        'detail': '3 条来源已补齐',
                        'stage_label': '岗位来源',
                        'stage_detail': '成品库 1 · 水电气 1 · 计划科 1 · 质检占位',
                        'result_label': '库存 / 能耗 / 合同来源',
                        'result_targets': ['今日发货', '入库面积', '合同量', '单吨能耗'],
                        'status': 'healthy',
                    },
                ],
                'frontline': {
                    'status': 'healthy',
                    'expected_count': 12,
                    'reported_count': 12,
                    'auto_confirmed_count': 11,
                    'returned_count': 0,
                    'unreported_count': 0,
                    'late_count': 0,
                    'reminder_count': 0,
                    'reporting_rate': 100.0,
                },
                'backline': {
                    'status': 'healthy',
                    'history_points': 7,
                    'energy_row_count': 3,
                    'exception_count': 0,
                    'reconciliation_open_count': 0,
                    'mes_last_run_status': 'success',
                },
                'delivery': {
                    'status': 'healthy',
                    'delivery_ready': True,
                    'reports_generated': 3,
                    'reports_ready_count': 3,
                    'reports_published_count': 2,
                    'missing_steps': [],
                },
            },
            'analysis_handoff': {
                'target_date': '2026-04-10',
                'surface': 'factory',
                'readiness': True,
                'blocking_reasons': [],
                'priority': 'medium',
                'attention_flags': ['contract_stalled'],
                'data_gaps': [],
                'section_matrix': {
                    'healthy_sections': ['reporting', 'delivery', 'energy', 'risk'],
                    'warning_sections': ['contracts'],
                    'blocked_sections': [],
                    'idle_sections': [],
                },
                'section_reasons': {
                    'reporting': [],
                    'delivery': [],
                    'energy': [],
                    'contracts': ['contract_stalled'],
                    'risk': [],
                },
                'source_matrix': {
                    'reporting': ['主操直录'],
                    'delivery': ['系统汇总', '结果发布'],
                    'energy': ['专项补录', '系统汇总'],
                    'contracts': ['专项补录', '系统汇总'],
                    'risk': ['系统汇总'],
                },
                'source_variants': {
                    'reporting': ['mobile'],
                    'delivery': ['system', 'publish'],
                    'energy': ['owner_only', 'system'],
                    'contracts': ['owner_only', 'system'],
                    'risk': ['system'],
                },
                'action_matrix': {
                    'reporting': ['watch_reporting_arrivals'],
                    'delivery': ['watch_delivery_release'],
                    'energy': ['watch_energy_baseline'],
                    'contracts': ['review_stalled_contracts'],
                    'risk': ['watch_risk_signals'],
                },
                'freshness': {
                    'freshness_status': 'fresh',
                    'sync_status': 'success',
                    'sync_lag_seconds': 30,
                    'history_points': 7,
                    'published_report_at': '2026-04-10T12:00:00+08:00',
                },
                'trend': {
                    'current_output': 123.4,
                    'yesterday_output': 118.0,
                    'output_delta_vs_yesterday': 5.4,
                    'seven_day_average_output': 120.7,
                },
                'reporting': {
                    'status': 'healthy',
                    'reporting_rate': 100.0,
                    'reported_count': 12,
                    'unreported_count': 0,
                    'auto_confirmed_count': 11,
                    'returned_count': 0,
                    'source_labels': ['主操直录'],
                },
                'delivery': {
                    'status': 'healthy',
                    'delivery_ready': True,
                    'reports_generated': 3,
                    'reports_published_count': 2,
                    'missing_steps': [],
                    'source_labels': ['系统汇总', '结果发布'],
                },
                'energy': {
                    'status': 'healthy',
                    'energy_per_ton': 3.21,
                    'total_energy': 321.0,
                    'electricity_value': 280.0,
                    'gas_value': 31.0,
                    'water_value': 10.0,
                    'source_labels': ['专项补录', '系统汇总'],
                },
                'contracts': {
                    'status': 'healthy',
                    'daily_contract_weight': 98.7,
                    'month_to_date_contract_weight': 456.7,
                    'active_contract_count': 3,
                    'stalled_contract_count': 1,
                    'remaining_weight': 123.4,
                    'source_labels': ['专项补录', '系统汇总'],
                },
                'risk': {
                    'status': 'healthy',
                    'has_blockers': False,
                    'blocker_digest': '未发现关键异常',
                    'reconciliation_open_count': 0,
                    'mobile_exception_count': 0,
                    'production_exception_count': 0,
                    'source_labels': ['系统汇总'],
                },
            },
            'delivery_ready': True,
            'delivery_status': {
                'target_date': '2026-04-10',
                'imports_completed': True,
                'reconciliation_open_count': 0,
                'quality_open_count': 0,
                'blocker_count': 0,
                'reports_generated': 3,
                'reports_reviewed_count': 1,
                'reports_published_count': 2,
                'reports_published': 3,
                'reports_published_deprecated': True,
                'delivery_ready': True,
                'missing_steps': [],
            },
            'mobile_reporting_summary': {
                'expected_count': 12,
                'reported_count': 12,
                'auto_confirmed_count': 11,
                'unreported_count': 0,
                'reporting_rate': 100.0,
            },
            'reminder_summary': {
                'unreported_count': 0,
                'late_report_count': 0,
                'today_reminder_count': 0,
            },
            'blocker_summary': {
                'has_blockers': False,
                'digest': '未发现关键异常',
            },
            'management_estimate': {
                'estimate_ready': True,
                'estimated_revenue': 1000.0,
                'estimated_cost': 300.0,
                'estimated_margin': 700.0,
                'energy_cost': 100.0,
                'labor_cost': 200.0,
                'active_contract_count': 3,
                'stalled_contract_count': 1,
                'active_coil_count': 12,
                'stalled_coil_count': 2,
                'today_advanced_weight': 88.8,
                'remaining_weight': 123.4,
                'reported_shift_count': 12,
                'unreported_shift_count': 0,
                'reporting_rate': 100.0,
                'total_attendance': 24,
                'sync_lag_seconds': 30,
                'sync_status': 'success',
                'assumptions': {
                    'revenue_per_ton': 10.0,
                    'electricity_cost_per_unit': 1.2,
                    'gas_cost_per_unit': 0.8,
                    'labor_cost_per_attendance': 5.0,
                },
            },
            'contract_lane': {
                'business_date': '2026-04-10',
                'snapshot_count': 1,
                'owner_entry_count': 0,
                'delivery_scopes': ['factory'],
                'daily_contract_weight': 98.7,
                'month_to_date_contract_weight': 456.7,
                'daily_input_weight': 88.8,
                'month_to_date_input_weight': 432.1,
                'quality_status': 'ready',
                'items': [
                    {
                        'business_date': '2026-04-10',
                        'source_batch_id': 11,
                        'sheet_name': '合同日报',
                        'delivery_scope': 'factory',
                        'daily_contract_weight': 98.7,
                        'month_to_date_contract_weight': 456.7,
                        'daily_input_weight': 88.8,
                        'month_to_date_input_weight': 432.1,
                        'lineage_hash': 'hash-1',
                        'quality_status': 'ready',
                    }
                ],
            },
            'contract_progress': {
                'target_date': '2026-04-10',
                'active_contract_count': 3,
                'stalled_contract_count': 1,
                'active_coil_count': 12,
                'stalled_coil_count': 2,
                'today_advanced_weight': 88.8,
                'remaining_weight': 123.4,
                'contracts': [
                    {
                        'contract_no': 'HT-001',
                        'status': 'active',
                        'active_coil_count': 2,
                        'stalled_coil_count': 0,
                        'today_advanced_coil_count': 1,
                        'today_advanced_weight': 40.5,
                        'remaining_weight': 60.0,
                        'workshops': ['ZR1'],
                        'processes': ['cast_roll'],
                        'statuses': ['processing'],
                        'tracking_cards': [
                            {
                                'tracking_card_no': 'TK-001',
                                'coil_id': 'COIL-1',
                                'status': 'processing',
                                'workshop_code': 'ZR1',
                                'process_code': 'cast_roll',
                                'updated_at': '2026-04-10T09:30:00',
                            }
                        ],
                    }
                ],
            },
            'exception_lane': {
                'unreported_shift_count': 0,
                'returned_shift_count': 0,
                'late_shift_count': 0,
                'mobile_exception_count': 0,
                'production_exception_count': 0,
                'reconciliation_open_count': 0,
                'pending_report_publish_count': 0,
            },
            'workshop_reporting_status': [
                {
                    'workshop_id': 14,
                    'workshop_name': '铸轧一车间',
                    'workshop_code': 'ZR1',
                    'report_status': 'auto_confirmed',
                    'output_weight': 123.4,
                    'source_label': '主操直录',
                    'source_variant': 'mobile',
                    'status_hint': '主操直录已稳定，系统已自动归档',
                }
            ],
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_manager_user] = fake_get_user
    monkeypatch.setattr('app.routers.dashboard.report_service.build_factory_dashboard', fake_dashboard)

    client = TestClient(app)
    response = client.get('/api/v1/dashboard/factory-director', params={'target_date': '2026-04-10'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['target_date'] == '2026-04-10'
    assert payload['leader_summary']['summary_text'] == '2026-04-10，今日产量 123.40 吨，异常 0 条。'
    assert payload['leader_summary']['summary_source'] == 'deterministic'
    assert payload['leader_metrics']['today_total_output'] == 123.4
    assert payload['leader_metrics']['yield_rate'] == 96.5
    assert payload['leader_metrics']['shipment_weight'] == 55.0
    assert payload['leader_metrics']['storage_inbound_area'] == 1200.0
    assert payload['history_digest']['daily_snapshots'][1]['output_weight'] == 123.4
    assert payload['history_digest']['month_archive']['total_output'] == 1234.5
    assert payload['delivery_ready'] is True
    assert payload['workshop_reporting_status'][0]['source_label'] == '主操直录'
    assert payload['workshop_reporting_status'][0]['status_hint'] == '主操直录已稳定，系统已自动归档'

    parsed = FactoryDashboardResponse.model_validate(payload)
    assert parsed.history_digest.daily_snapshots[1].output_weight == 123.4
    assert parsed.history_digest.month_archive.total_output == 1234.5
    assert parsed.delivery_status.delivery_ready is True
    assert parsed.delivery_status.reports_generated == 3
    assert parsed.mobile_reporting_summary.expected_count == 12
    assert parsed.reminder_summary.today_reminder_count == 0
    assert parsed.blocker_summary.has_blockers is False
    assert parsed.blocker_summary.digest == '未发现关键异常'
    assert parsed.management_estimate.estimated_margin == 700.0
    assert parsed.management_estimate.assumptions.revenue_per_ton == 10.0
    assert parsed.contract_lane.daily_contract_weight == 98.7
    assert parsed.contract_lane.items[0].sheet_name == '合同日报'
    assert parsed.contract_progress.active_contract_count == 3
    assert parsed.contract_progress.contracts[0].tracking_cards[0].status == 'processing'
    assert parsed.exception_lane.pending_report_publish_count == 0
    assert parsed.workshop_reporting_status[0].source_label == '主操直录'
    assert parsed.workshop_reporting_status[0].status_hint == '主操直录已稳定，系统已自动归档'
    assert parsed.runtime_trace.source_lanes[0].label == '主操直录'
    assert parsed.runtime_trace.source_lanes[0].result_targets == ['今日产量', '今日上报状态']
    assert parsed.runtime_trace.frontline.reported_count == 12
    assert parsed.runtime_trace.backline.mes_last_run_status == 'success'
    assert parsed.runtime_trace.delivery.reports_ready_count == 3
    assert parsed.analysis_handoff.readiness is True
    assert parsed.analysis_handoff.priority == 'medium'
    assert parsed.analysis_handoff.attention_flags == ['contract_stalled']
    assert parsed.analysis_handoff.data_gaps == []
    assert parsed.analysis_handoff.section_matrix.warning_sections == ['contracts']
    assert parsed.analysis_handoff.section_matrix.healthy_sections == ['reporting', 'delivery', 'energy', 'risk']
    assert parsed.analysis_handoff.section_reasons.contracts == ['contract_stalled']
    assert parsed.analysis_handoff.section_reasons.reporting == []
    assert parsed.analysis_handoff.source_matrix.reporting == ['主操直录']
    assert parsed.analysis_handoff.source_matrix.contracts == ['专项补录', '系统汇总']
    assert parsed.analysis_handoff.source_variants.reporting == ['mobile']
    assert parsed.analysis_handoff.source_variants.delivery == ['system', 'publish']
    assert parsed.analysis_handoff.action_matrix.reporting == ['watch_reporting_arrivals']
    assert parsed.analysis_handoff.action_matrix.contracts == ['review_stalled_contracts']
    assert parsed.analysis_handoff.freshness.freshness_status == 'fresh'
    assert parsed.analysis_handoff.freshness.sync_lag_seconds == 30
    assert parsed.analysis_handoff.trend.current_output == 123.4
    assert parsed.analysis_handoff.trend.output_delta_vs_yesterday == 5.4
    assert parsed.analysis_handoff.reporting.source_labels == ['主操直录']
    assert parsed.analysis_handoff.delivery.delivery_ready is True
    assert parsed.analysis_handoff.contracts.remaining_weight == 123.4
    assert parsed.analysis_handoff.risk.has_blockers is False

    app.dependency_overrides.clear()


def test_workshop_dashboard_exposes_owner_lane_payload(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user():
        return SimpleNamespace(
            id=8,
            role='manager',
            is_admin=False,
            is_manager=True,
            is_reviewer=False,
            workshop_id=14,
            data_scope_type='all',
        )

    def fake_dashboard(_db, *, target_date, workshop_id):
        assert target_date == date(2026, 4, 10)
        assert workshop_id == 14
        return {
            'target_date': '2026-04-10',
            'workshop_id': 14,
            'total_output': 88.0,
            'month_to_date_output': 1000.0,
            'pending_shift_count': 1,
            'mobile_reporting_summary': {'reporting_rate': 100.0},
            'energy_summary': {
                'electricity_value': 120.0,
                'gas_value': 30.0,
                'water_value': 15.0,
                'total_energy': 165.0,
                'output_weight': 66.0,
                'energy_per_ton': 2.5,
            },
            'production_lane': [
                {
                    'source': 'mobile',
                    'source_label': '主操直录',
                    'source_variant': 'mobile',
                    'workshop_name': '铸轧一车间',
                    'total_output': 88.0,
                    'compare_value': 80.0,
                    'delta_vs_yesterday': 8.0,
                }
            ],
            'energy_lane': [{'source': 'owner_only', 'source_label': '专项补录', 'source_variant': 'owner', 'water_value': 50.0}],
            'inventory_lane': [{'source': 'mobile', 'source_label': '主操直录', 'source_variant': 'mobile', 'shipment_weight': 55.0, 'storage_inbound_area': 1200.0, 'actual_inventory_weight': 980.0}],
            'exception_lane': {'returned_shift_count': 0},
            'reminder_summary': {'today_reminder_count': 0},
            'runtime_trace': {
                'source_lanes': [
                    {
                        'key': 'operator',
                        'label': '主操直录',
                        'actor_label': '机台主操',
                        'detail': '6 / 6 班次已到位',
                        'stage_label': '自动确认',
                        'stage_detail': '6 条已收口',
                        'result_label': '产量 / 在制 / 班次原始值',
                        'result_targets': ['今日产量', '生产泳道'],
                        'status': 'healthy',
                    },
                    {
                        'key': 'owner',
                        'label': '专项补录',
                        'actor_label': '成品库 / 水电气 / 计划科',
                        'detail': '2 条来源已补齐',
                        'stage_label': '岗位来源',
                        'stage_detail': '成品库 1 · 水电气 1 · 质检占位',
                        'result_label': '库存 / 能耗 / 合同来源',
                        'result_targets': ['库存物流泳道', '能耗泳道'],
                        'status': 'healthy',
                    },
                ],
                'frontline': {
                    'status': 'healthy',
                    'expected_count': 6,
                    'reported_count': 6,
                    'auto_confirmed_count': 6,
                    'returned_count': 0,
                    'unreported_count': 0,
                    'late_count': 0,
                    'reminder_count': 0,
                    'reporting_rate': 100.0,
                },
                'backline': {
                    'status': 'healthy',
                    'history_points': 7,
                    'energy_row_count': 1,
                    'exception_count': 0,
                    'reconciliation_open_count': 0,
                    'mes_last_run_status': None,
                },
                'delivery': {
                    'status': 'healthy',
                    'delivery_ready': True,
                    'reports_generated': 3,
                    'reports_ready_count': 3,
                    'reports_published_count': 2,
                    'missing_steps': [],
                },
            },
            'analysis_handoff': {
                'target_date': '2026-04-10',
                'surface': 'workshop',
                'readiness': True,
                'blocking_reasons': [],
                'priority': 'low',
                'attention_flags': [],
                'data_gaps': ['report_unpublished', 'contracts_unavailable'],
                'section_matrix': {
                    'healthy_sections': ['reporting', 'delivery', 'energy', 'risk'],
                    'warning_sections': [],
                    'blocked_sections': [],
                    'idle_sections': ['contracts'],
                },
                'section_reasons': {
                    'reporting': [],
                    'delivery': [],
                    'energy': [],
                    'contracts': ['contracts_unavailable'],
                    'risk': [],
                },
                'source_matrix': {
                    'reporting': ['主操直录'],
                    'delivery': ['系统汇总', '结果发布'],
                    'energy': ['专项补录', '系统汇总'],
                    'contracts': ['系统汇总'],
                    'risk': ['系统汇总'],
                },
                'source_variants': {
                    'reporting': ['mobile'],
                    'delivery': ['system', 'publish'],
                    'energy': ['owner_only', 'system'],
                    'contracts': ['system'],
                    'risk': ['system'],
                },
                'action_matrix': {
                    'reporting': ['watch_reporting_arrivals'],
                    'delivery': ['publish_daily_report'],
                    'energy': ['watch_energy_baseline'],
                    'contracts': ['collect_contract_owner_entries'],
                    'risk': ['watch_risk_signals'],
                },
                'freshness': {
                    'freshness_status': 'warming',
                    'sync_status': 'idle',
                    'sync_lag_seconds': None,
                    'history_points': 7,
                    'published_report_at': None,
                },
                'trend': {
                    'current_output': 88.0,
                    'yesterday_output': 80.0,
                    'output_delta_vs_yesterday': 8.0,
                    'seven_day_average_output': 84.0,
                },
                'reporting': {
                    'status': 'healthy',
                    'reporting_rate': 100.0,
                    'reported_count': 6,
                    'unreported_count': 0,
                    'auto_confirmed_count': 6,
                    'returned_count': 0,
                    'source_labels': ['主操直录'],
                },
                'delivery': {
                    'status': 'healthy',
                    'delivery_ready': True,
                    'reports_generated': 3,
                    'reports_published_count': 2,
                    'missing_steps': [],
                    'source_labels': ['系统汇总', '结果发布'],
                },
                'energy': {
                    'status': 'healthy',
                    'energy_per_ton': 2.5,
                    'total_energy': 165.0,
                    'electricity_value': 120.0,
                    'gas_value': 30.0,
                    'water_value': 15.0,
                    'source_labels': ['专项补录', '系统汇总'],
                },
                'contracts': {
                    'status': 'idle',
                    'daily_contract_weight': None,
                    'month_to_date_contract_weight': None,
                    'active_contract_count': 0,
                    'stalled_contract_count': 0,
                    'remaining_weight': 0.0,
                    'source_labels': ['系统汇总'],
                },
                'risk': {
                    'status': 'healthy',
                    'has_blockers': False,
                    'blocker_digest': '未发现关键异常',
                    'reconciliation_open_count': 0,
                    'mobile_exception_count': 0,
                    'production_exception_count': 0,
                    'source_labels': ['系统汇总'],
                },
            },
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.dashboard.report_service.build_workshop_dashboard', fake_dashboard)

    client = TestClient(app)
    response = client.get('/api/v1/dashboard/workshop-director', params={'target_date': '2026-04-10', 'workshop_id': 14})

    assert response.status_code == 200
    payload = response.json()
    assert payload['workshop_id'] == 14
    assert payload['inventory_lane'][0]['shipment_weight'] == 55.0
    assert payload['inventory_lane'][0]['storage_inbound_area'] == 1200.0
    assert payload['inventory_lane'][0]['actual_inventory_weight'] == 980.0
    assert payload['inventory_lane'][0]['source_label'] == '主操直录'
    assert payload['inventory_lane'][0]['source_variant'] == 'mobile'
    assert payload['energy_lane'][0]['source'] == 'owner_only'
    assert payload['energy_lane'][0]['source_label'] == '专项补录'
    assert payload['energy_lane'][0]['source_variant'] == 'owner'
    assert payload['energy_lane'][0]['water_value'] == 50.0

    parsed = WorkshopDashboardResponse.model_validate(payload)
    assert parsed.pending_shift_count == 1
    assert parsed.mobile_reporting_summary.reporting_rate == 100.0
    assert parsed.energy_summary.energy_per_ton == 2.5
    assert parsed.energy_summary.electricity_value == 120.0
    assert parsed.reminder_summary.today_reminder_count == 0
    assert parsed.exception_lane.returned_shift_count == 0
    assert parsed.production_lane[0].source_label == '主操直录'
    assert parsed.energy_lane[0].source_label == '专项补录'
    assert parsed.inventory_lane[0].shipment_weight == 55.0
    assert parsed.inventory_lane[0].source_variant == 'mobile'
    assert parsed.runtime_trace.source_lanes[1].label == '专项补录'
    assert parsed.runtime_trace.source_lanes[1].result_targets == ['库存物流泳道', '能耗泳道']
    assert parsed.runtime_trace.frontline.auto_confirmed_count == 6
    assert parsed.runtime_trace.backline.energy_row_count == 1
    assert parsed.runtime_trace.delivery.delivery_ready is True
    assert parsed.analysis_handoff.surface == 'workshop'
    assert parsed.analysis_handoff.priority == 'low'
    assert parsed.analysis_handoff.attention_flags == []
    assert parsed.analysis_handoff.data_gaps == ['report_unpublished', 'contracts_unavailable']
    assert parsed.analysis_handoff.section_matrix.idle_sections == ['contracts']
    assert parsed.analysis_handoff.section_matrix.healthy_sections == ['reporting', 'delivery', 'energy', 'risk']
    assert parsed.analysis_handoff.section_reasons.contracts == ['contracts_unavailable']
    assert parsed.analysis_handoff.section_reasons.energy == []
    assert parsed.analysis_handoff.source_matrix.contracts == ['系统汇总']
    assert parsed.analysis_handoff.source_matrix.energy == ['专项补录', '系统汇总']
    assert parsed.analysis_handoff.source_variants.contracts == ['system']
    assert parsed.analysis_handoff.source_variants.energy == ['owner_only', 'system']
    assert parsed.analysis_handoff.action_matrix.delivery == ['publish_daily_report']
    assert parsed.analysis_handoff.action_matrix.contracts == ['collect_contract_owner_entries']
    assert parsed.analysis_handoff.freshness.freshness_status == 'warming'
    assert parsed.analysis_handoff.freshness.history_points == 7
    assert parsed.analysis_handoff.trend.seven_day_average_output == 84.0
    assert parsed.analysis_handoff.energy.energy_per_ton == 2.5
    assert parsed.analysis_handoff.contracts.status == 'idle'
    assert parsed.analysis_handoff.risk.blocker_digest == '未发现关键异常'

    app.dependency_overrides.clear()


def test_workshop_dashboard_response_model_accepts_owner_lane_fields() -> None:
    payload = WorkshopDashboardResponse(
        target_date='2026-04-10',
        workshop_id=14,
        total_output=88.0,
        month_to_date_output=1000.0,
        mobile_reporting_summary={'reporting_rate': 100.0},
        energy_summary={
            'electricity_value': 120.0,
            'gas_value': 30.0,
            'water_value': 15.0,
            'total_energy': 165.0,
            'output_weight': 66.0,
            'energy_per_ton': 2.5,
        },
        energy_lane=[{'source': 'owner_only', 'source_label': '专项补录', 'source_variant': 'owner', 'water_value': 50.0}],
        inventory_lane=[{'source': 'mobile', 'source_label': '主操直录', 'source_variant': 'mobile', 'shipment_weight': 55.0, 'storage_inbound_area': 1200.0, 'actual_inventory_weight': 980.0}],
        exception_lane={'returned_shift_count': 0},
        reminder_summary={'today_reminder_count': 0},
        runtime_trace={
            'source_lanes': [
                {
                    'key': 'operator',
                    'label': '主操直录',
                    'actor_label': '机台主操',
                    'detail': '6 / 6 班次已到位',
                    'stage_label': '自动确认',
                    'stage_detail': '6 条已收口',
                    'result_label': '产量 / 在制 / 班次原始值',
                    'result_targets': ['今日产量', '生产泳道'],
                    'status': 'healthy',
                }
            ],
            'frontline': {
                'status': 'healthy',
                'expected_count': 6,
                'reported_count': 6,
                'auto_confirmed_count': 6,
                'returned_count': 0,
                'unreported_count': 0,
                'late_count': 0,
                'reminder_count': 0,
                'reporting_rate': 100.0,
            },
            'backline': {
                'status': 'healthy',
                'history_points': 7,
                'energy_row_count': 1,
                'exception_count': 0,
                'reconciliation_open_count': 0,
                'mes_last_run_status': None,
            },
            'delivery': {
                'status': 'healthy',
                'delivery_ready': True,
                'reports_generated': 3,
                'reports_ready_count': 3,
                'reports_published_count': 2,
                'missing_steps': [],
            },
        },
    )

    assert payload.workshop_id == 14
    assert payload.pending_shift_count is None
    assert payload.inventory_lane[0].shipment_weight == 55.0
    assert payload.inventory_lane[0].source_label == '主操直录'
    assert payload.mobile_reporting_summary.reporting_rate == 100.0
    assert payload.energy_summary.electricity_value == 120.0
    assert payload.reminder_summary.today_reminder_count == 0
    assert payload.exception_lane.returned_shift_count == 0
    assert payload.energy_lane[0].source == 'owner_only'
    assert payload.energy_lane[0].source_variant == 'owner'
    assert payload.history_digest is None
    assert payload.runtime_trace.source_lanes[0].label == '主操直录'
    assert payload.runtime_trace.source_lanes[0].result_targets == ['今日产量', '生产泳道']
    assert payload.runtime_trace.frontline.expected_count == 6
    assert payload.runtime_trace.delivery.reports_published_count == 2


def test_workshop_dashboard_rejects_reviewer_as_main_review_entry(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user():
        return SimpleNamespace(
            id=9,
            role='reviewer',
            is_admin=False,
            is_manager=False,
            is_reviewer=True,
            workshop_id=14,
            data_scope_type='all',
        )

    def fail_dashboard(*_args, **_kwargs):
        raise AssertionError('reviewer should not reach workshop dashboard service')

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.dashboard.report_service.build_workshop_dashboard', fail_dashboard)

    client = TestClient(app)
    response = client.get('/api/v1/dashboard/workshop-director', params={'target_date': '2026-04-10', 'workshop_id': 14})

    assert response.status_code == 403

    app.dependency_overrides.clear()


def test_runtime_trace_builder_uses_real_dashboard_inputs() -> None:
    runtime_trace = report_service._build_runtime_trace(
        history_digest={'daily_snapshots': [{'date': '2026-04-04'}] * 7},
        energy_lane=[{'source': 'owner_only', 'total_energy': 1.0}, {'total_energy': 2.0}],
        inventory_lane=[{'source': 'owner_only', 'shipment_weight': 12.0}],
        contract_lane={'quality_status': 'owner_only'},
        exception_lane={
            'mobile_exception_count': 2,
            'production_exception_count': 1,
            'reconciliation_open_count': 1,
        },
        mobile_summary={
            'expected_count': 12,
            'reported_count': 11,
            'auto_confirmed_count': 10,
            'returned_count': 1,
            'unreported_count': 1,
            'late_count': 1,
            'reporting_rate': 91.67,
        },
        reminder_summary={'today_reminder_count': 2},
        delivery_status={
            'delivery_ready': False,
            'reports_generated': 3,
            'reports_reviewed_count': 1,
            'reports_published_count': 1,
            'missing_steps': ['reconciliation_open'],
        },
        sync_status={'last_run_status': 'failed'},
        surface='factory',
    )

    assert runtime_trace['frontline']['reminder_count'] == 2
    assert runtime_trace['source_lanes'][0]['label'] == '算法流水线'
    assert runtime_trace['source_lanes'][1]['label'] == '分析决策助手'
    assert runtime_trace['source_lanes'][2]['result_targets'] == ['交付与闭环', '数据留存与归档']
    assert runtime_trace['frontline']['status'] == 'blocked'
    assert runtime_trace['backline']['history_points'] == 7
    assert runtime_trace['backline']['energy_row_count'] == 2
    assert runtime_trace['backline']['exception_count'] == 3
    assert runtime_trace['backline']['mes_last_run_status'] == 'failed'
    assert runtime_trace['delivery']['reports_ready_count'] == 2
    assert runtime_trace['delivery']['status'] == 'blocked'


def test_lane_source_meta_returns_backend_display_fields() -> None:
    assert report_service._lane_source_meta('owner_only') == {
        'source': 'owner_only',
        'source_label': '专项补录',
        'source_variant': 'owner',
    }
    assert report_service._lane_source_meta('mobile') == {
        'source': 'mobile',
        'source_label': '主操直录',
        'source_variant': 'mobile',
    }
    assert report_service._lane_source_meta(None) == {
        'source': 'import',
        'source_label': '系统导入',
        'source_variant': 'import',
    }


def test_workshop_reporting_meta_returns_backend_display_fields() -> None:
    assert report_service._workshop_reporting_meta('auto_confirmed') == {
        'source_label': '主操直录',
        'source_variant': 'mobile',
        'status_hint': '主操直录已稳定，系统已自动归档',
    }
    assert report_service._workshop_reporting_meta('unreported') == {
        'source_label': '主操直录',
        'source_variant': 'mobile',
        'status_hint': '主操待补，系统暂未看到本班原始值',
    }
