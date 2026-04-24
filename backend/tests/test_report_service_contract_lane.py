from __future__ import annotations

from datetime import UTC, date, datetime, time
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Workshop
from app.models.production import ShiftProductionData
from app.models.shift import ShiftConfig
from app.services import report_service


class FakeQuery:
    def __init__(self, *, all_value=None, scalar_value=None, first_value=None):
        self._all_value = all_value
        self._scalar_value = scalar_value
        self._first_value = first_value

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._all_value

    def scalar(self):
        return self._scalar_value

    def first(self):
        return self._first_value if self._first_value is not None else self._all_value


class DeliveryStatusDB:
    def __init__(self):
        completed_batches = [
            SimpleNamespace(import_type=import_type)
            for import_type in report_service.REQUIRED_IMPORT_TYPES
        ]
        self._queries = [
            FakeQuery(all_value=completed_batches),
            FakeQuery(scalar_value=0),
            FakeQuery(scalar_value=1),
            FakeQuery(scalar_value=1),
            FakeQuery(scalar_value=0),
        ]

    def query(self, *_args, **_kwargs):
        if not self._queries:
            raise AssertionError('unexpected extra query in build_delivery_status')
        return self._queries.pop(0)


class ProductionReportDB:
    def __init__(self):
        self._queries = [
            FakeQuery(scalar_value=0),
            FakeQuery(scalar_value=0),
        ]

    def query(self, *_args, **_kwargs):
        if not self._queries:
            raise AssertionError('unexpected extra query in _generate_production_report')
        return self._queries.pop(0)


class StatisticsDashboardDB:
    def __init__(self):
        self._queries = [
            FakeQuery(scalar_value=3),
            FakeQuery(scalar_value=2),
            FakeQuery(scalar_value=9),
            FakeQuery(scalar_value=1),
            FakeQuery(scalar_value=0),
            FakeQuery(scalar_value=0),
            FakeQuery(scalar_value=0),
            FakeQuery(scalar_value=0),
            FakeQuery(scalar_value=0),
            FakeQuery(scalar_value=4),
            FakeQuery(all_value=[]),
            FakeQuery(all_value=[]),
            FakeQuery(all_value=[]),
            FakeQuery(scalar_value=None),
        ]

    def query(self, *_args, **_kwargs):
        if not self._queries:
            raise AssertionError('unexpected extra query in build_statistics_dashboard')
        return self._queries.pop(0)


class FactoryDashboardDB:
    def __init__(self, latest_report):
        self._queries = [
            FakeQuery(scalar_value=0),
            FakeQuery(scalar_value=0),
            FakeQuery(scalar_value=0),
            FakeQuery(first_value=latest_report),
            FakeQuery(scalar_value=0),
        ]

    def query(self, *_args, **_kwargs):
        if not self._queries:
            raise AssertionError('unexpected extra query in build_factory_dashboard')
        return self._queries.pop(0)


def build_history_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'factory-history.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, ShiftConfig.__table__, ShiftProductionData.__table__])
    db = sessionmaker(bind=engine, future=True)()
    workshop = Workshop(code='ZR2', name='铸二车间', workshop_type='casting', sort_order=1, is_active=True)
    shift = ShiftConfig(
        code='A',
        name='白班',
        shift_type='day',
        start_time=time(8, 0),
        end_time=time(16, 0),
        is_cross_day=False,
        sort_order=1,
        is_active=True,
    )
    db.add_all([workshop, shift])
    db.commit()
    db.refresh(workshop)
    db.refresh(shift)
    return db, workshop, shift


def test_build_delivery_status_requires_contract_report_import(monkeypatch) -> None:
    monkeypatch.setattr('app.services.report_service.quality_service.count_open_issues', lambda *_args, **_kwargs: 0)
    monkeypatch.setattr('app.services.report_service.quality_service.count_open_blockers', lambda *_args, **_kwargs: 0)

    payload = report_service.build_delivery_status(DeliveryStatusDB(), target_date=date(2026, 4, 8))

    assert payload['imports_completed'] is False
    assert payload['delivery_ready'] is False
    assert any(step.startswith('imports_missing:') for step in payload['missing_steps'])
    assert 'contract_report' in payload['missing_steps'][0]


def test_generate_production_report_includes_contract_lane_projection(monkeypatch) -> None:
    monkeypatch.setattr('app.services.report_service._workshop_name_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr('app.services.report_service._shift_code_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr('app.services.report_service._query_shift_items', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        'app.services.report_service.mobile_report_service.summarize_mobile_reporting',
        lambda *_args, **_kwargs: {
            'auto_confirmed_count': 0,
            'submitted_count': 0,
            'draft_count': 0,
            'returned_count': 0,
            'unreported_count': 0,
            'reported_count': 0,
        },
    )
    monkeypatch.setattr(
        'app.services.report_service.energy_service.summarize_energy_for_date',
        lambda *_args, **_kwargs: {'total_energy': 0.0, 'energy_per_ton': 0.0, 'rows': []},
    )
    monkeypatch.setattr(
        'app.services.report_service.build_contract_projection',
        lambda *_args, **_kwargs: {'snapshot_count': 1, 'delivery_scopes': ['factory'], 'quality_status': 'ready'},
    )
    monkeypatch.setattr(
        'app.services.report_service.build_yield_matrix_projection',
        lambda *_args, **_kwargs: {
            'snapshot_count': 1,
            'company_total_yield': 96.0,
            'mp_targets': {'M': 88.0, 'P': 92.0},
            'quality_status': 'ready',
        },
    )

    payload = report_service._generate_production_report(ProductionReportDB(), report_date=date(2026, 4, 8), scope='auto_confirmed')

    assert payload['scope'] == 'auto_confirmed'
    assert payload['contract_lane']['snapshot_count'] == 1
    assert payload['contract_lane']['quality_status'] == 'ready'
    assert payload['yield_matrix_lane']['snapshot_count'] == 1
    assert payload['yield_matrix_lane']['company_total_yield'] == 96.0
    assert payload['yield_matrix_lane']['mp_targets']['M'] == 88.0


def test_build_statistics_dashboard_includes_yield_matrix_lane(monkeypatch) -> None:
    monkeypatch.setattr('app.services.report_service.quality_service.count_open_issues', lambda *_args, **_kwargs: 0)
    monkeypatch.setattr('app.services.report_service.quality_service.count_open_blockers', lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(
        'app.services.report_service.build_delivery_status',
        lambda *_args, **_kwargs: {'delivery_ready': True, 'missing_steps': []},
    )
    monkeypatch.setattr(
        'app.services.report_service.mobile_report_service.summarize_mobile_reporting',
        lambda *_args, **_kwargs: {'reporting_rate': 100},
    )
    monkeypatch.setattr(
        'app.services.report_service.mobile_reminder_service.summarize_reminders',
        lambda *_args, **_kwargs: {'unreported_count': 0, 'late_report_count': 0, 'today_reminder_count': 0},
    )
    monkeypatch.setattr(
        'app.services.report_service.build_contract_projection',
        lambda *_args, **_kwargs: {'snapshot_count': 1, 'quality_status': 'ready'},
    )
    monkeypatch.setattr(
        'app.services.report_service.build_yield_matrix_projection',
        lambda *_args, **_kwargs: {
            'snapshot_count': 1,
            'company_total_yield': 96.6,
            'mp_targets': {'M': 88.0, 'P': 92.0},
            'quality_status': 'ready',
            'delivery_scopes': ['factory'],
        },
    )

    payload = report_service.build_statistics_dashboard(StatisticsDashboardDB(), target_date=date(2026, 4, 9))

    assert payload['delivery_ready'] is True
    assert payload['contract_lane']['snapshot_count'] == 1
    assert payload['yield_matrix_lane']['snapshot_count'] == 1
    assert payload['yield_matrix_lane']['company_total_yield'] == 96.6
    assert payload['yield_matrix_lane']['mp_targets']['P'] == 92.0


def test_build_history_digest_tracks_daily_trend_and_period_archives(tmp_path, monkeypatch) -> None:
    db, workshop, shift = build_history_session(tmp_path)
    target_date = date(2026, 4, 17)
    seeded_output = [112.0, 126.0, 118.0, 132.0, 141.0, 137.0, 145.0]
    try:
        for offset, output_weight in enumerate(seeded_output):
            business_date = date(2026, 4, 11 + offset)
            db.add(
                ShiftProductionData(
                    business_date=business_date,
                    shift_config_id=shift.id,
                    workshop_id=workshop.id,
                    output_weight=output_weight,
                    data_source='manual',
                    data_status='confirmed',
                )
            )
        db.add(
            ShiftProductionData(
                business_date=target_date,
                shift_config_id=shift.id,
                workshop_id=workshop.id,
                output_weight=999.0,
                data_source='manual',
                data_status='voided',
            )
        )
        db.commit()

        monkeypatch.setattr(
            'app.services.report_service.mobile_report_service.summarize_mobile_inventory',
            lambda *_args, **kwargs: [
                {
                    'storage_finished': float(kwargs['target_date'].day * 2),
                    'shipment_weight': float(kwargs['target_date'].day),
                    'storage_inbound_area': float(kwargs['target_date'].day * 10),
                },
            ],
        )
        monkeypatch.setattr(
            'app.services.report_service.build_contract_projection',
            lambda *_args, **kwargs: {
                'daily_contract_weight': float(kwargs['target_date'].day * 3),
            },
        )
        monkeypatch.setattr(
            'app.services.report_service.energy_service.summarize_energy_for_date',
            lambda *_args, **kwargs: {
                'energy_per_ton': round(kwargs['business_date'].day / 10, 2),
            },
        )

        payload = report_service._build_history_digest(db, target_date=target_date)

        assert [item['date'] for item in payload['daily_snapshots']] == [
            '2026-04-11',
            '2026-04-12',
            '2026-04-13',
            '2026-04-14',
            '2026-04-15',
            '2026-04-16',
            '2026-04-17',
        ]
        assert [item['output_weight'] for item in payload['daily_snapshots']] == seeded_output
        assert payload['daily_snapshots'][-1]['storage_finished_weight'] == 34.0
        assert payload['daily_snapshots'][-1]['shipment_weight'] == 17.0
        assert payload['daily_snapshots'][-1]['storage_inbound_area'] == 170.0
        assert payload['daily_snapshots'][-1]['contract_weight'] == 51.0
        assert payload['daily_snapshots'][-1]['energy_per_ton'] == 1.7
        assert payload['month_archive']['total_output'] == round(sum(seeded_output), 2)
        assert payload['month_archive']['reported_days'] == 7
        assert payload['month_archive']['average_daily_output'] == round(sum(seeded_output) / 7, 2)
        assert payload['year_archive']['total_output'] == round(sum(seeded_output), 2)
        assert payload['year_archive']['reported_days'] == 7
        assert payload['year_archive']['active_months'] == 1
        assert payload['year_archive']['average_monthly_output'] == round(sum(seeded_output), 2)
    finally:
        db.close()


def test_build_factory_dashboard_recomputes_leader_summary_from_current_lanes(monkeypatch) -> None:
    latest_report = SimpleNamespace(
        report_data={},
        final_text_summary='旧摘要',
        published_at=None,
        text_summary=None,
        final_confirmed_at=None,
        final_confirmed_by=None,
        is_final_version=False,
        generated_at=None,
        id=1,
    )
    monkeypatch.setattr(
        'app.services.report_service._generate_production_report',
        lambda *_args, **_kwargs: {
            'total_output_weight': 180.5,
            'shift_count': 3,
            'auto_confirmed_shifts': 2,
            'pending_or_unreported_shifts': 0,
            'returned_shifts': 0,
            'energy_per_ton': 5.2,
        },
    )
    monkeypatch.setattr(
        'app.services.report_service.energy_service.summarize_energy_for_date',
        lambda *_args, **_kwargs: {
            'total_energy': 1250.0,
            'energy_per_ton': 5.2,
            'electricity_value': 1000.0,
            'gas_value': 200.0,
            'rows': [],
        },
    )
    monkeypatch.setattr('app.services.report_service.build_delivery_status', lambda *_args, **_kwargs: {'delivery_ready': True})
    monkeypatch.setattr(
        'app.services.report_service.mobile_report_service.summarize_mobile_reporting',
        lambda *_args, **_kwargs: {
            'reporting_rate': 100.0,
            'expected_count': 3,
            'reported_count': 3,
            'returned_count': 0,
            'draft_count': 0,
            'submitted_count': 0,
            'unreported_count': 0,
        },
    )
    monkeypatch.setattr(
        'app.services.report_service.build_contract_projection',
        lambda *_args, **_kwargs: {'daily_contract_weight': 59.0},
    )
    monkeypatch.setattr(
        'app.services.report_service.build_contract_progress_projection',
        lambda *_args, **_kwargs: {'active_contract_count': 1, 'stalled_contract_count': 0, 'active_coil_count': 0, 'today_advanced_weight': 0.0, 'remaining_weight': 0.0},
    )
    monkeypatch.setattr(
        'app.services.report_service.mobile_report_service.summarize_mobile_inventory',
        lambda *_args, **_kwargs: [{'storage_prepared': 12.0, 'storage_finished': 320.0, 'shipment_weight': 184.0, 'storage_inbound_area': 1800.0}],
    )
    monkeypatch.setattr(
        'app.services.report_service._build_exception_lane',
        lambda *_args, **_kwargs: {'mobile_exception_count': 0, 'production_exception_count': 0, 'unreported_shift_count': 0, 'reminder_late_count': 0, 'pending_report_publish_count': 0, 'reconciliation_open_count': 0},
    )
    monkeypatch.setattr('app.services.report_service.mobile_reminder_service.summarize_reminders', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        'app.services.report_service._safe_latest_mes_sync_status',
        lambda *_args, **_kwargs: {'last_run_status': 'failed', 'lag_seconds': 7200},
    )
    monkeypatch.setattr('app.services.report_service.quality_service.blocker_summary', lambda *_args, **_kwargs: '仍有 1 条质量阻塞')
    monkeypatch.setattr('app.services.report_service._month_to_date_output', lambda *_args, **_kwargs: 1000.0)
    monkeypatch.setattr('app.services.report_service._build_factory_boss_summary', lambda *_args, **_kwargs: '旧老板摘要')
    monkeypatch.setattr('app.services.report_service.build_management_estimate', lambda *_args, **_kwargs: {})
    monkeypatch.setattr('app.services.report_service._build_history_digest', lambda *_args, **_kwargs: {'daily_snapshots': [], 'month_archive': {}, 'year_archive': {}})
    monkeypatch.setattr('app.services.report_service._build_production_lane', lambda *_args, **_kwargs: [])
    monkeypatch.setattr('app.services.report_service._build_energy_lane', lambda *_args, **_kwargs: [])
    monkeypatch.setattr('app.services.report_service._build_canonical_workshop_output_summary', lambda *_args, **_kwargs: [])
    monkeypatch.setattr('app.services.report_service.build_workshop_attendance_summary', lambda *_args, **_kwargs: [])
    monkeypatch.setattr('app.services.report_service._build_workshop_reporting_status', lambda *_args, **_kwargs: [])

    payload = report_service.build_factory_dashboard(FactoryDashboardDB(latest_report), target_date=date(2026, 4, 17))

    assert '发货 184.00 吨' in payload['leader_summary']['summary_text']
    assert '入库面积 1800.00 ㎡' in payload['leader_summary']['summary_text']
    assert payload['leader_summary']['summary_text'] != '旧摘要'
    assert payload['blocker_summary'] == {
        'has_blockers': True,
        'digest': '仍有 1 条质量阻塞',
    }
    assert payload['analysis_handoff']['surface'] == 'factory'
    assert payload['analysis_handoff']['readiness'] is False
    assert payload['analysis_handoff']['priority'] == 'high'
    assert 'quality_blocker' in payload['analysis_handoff']['attention_flags']
    assert 'quality_blocker' in payload['analysis_handoff']['blocking_reasons']
    assert payload['analysis_handoff']['data_gaps'] == ['report_unpublished', 'history_unavailable', 'sync_stale']
    assert payload['analysis_handoff']['section_matrix'] == {
        'healthy_sections': ['reporting', 'delivery', 'energy', 'contracts'],
        'warning_sections': [],
        'blocked_sections': ['risk'],
        'idle_sections': [],
    }
    assert payload['analysis_handoff']['section_reasons'] == {
        'reporting': [],
        'delivery': [],
        'energy': [],
        'contracts': [],
        'risk': ['quality_blocker'],
    }
    assert payload['analysis_handoff']['source_matrix'] == {
        'reporting': ['主操直录'],
        'delivery': ['系统汇总', '结果发布'],
        'energy': ['专项补录', '系统汇总'],
        'contracts': ['专项补录', '系统汇总'],
        'risk': ['系统汇总'],
    }
    assert payload['analysis_handoff']['source_variants'] == {
        'reporting': ['mobile'],
        'delivery': ['system', 'publish'],
        'energy': ['owner_only', 'system'],
        'contracts': ['owner_only', 'system'],
        'risk': ['system'],
    }
    assert payload['analysis_handoff']['action_matrix'] == {
        'reporting': ['watch_reporting_arrivals'],
        'delivery': ['publish_daily_report'],
        'energy': ['watch_energy_baseline'],
        'contracts': ['watch_contract_progress'],
        'risk': ['clear_quality_blockers', 'refresh_pipeline_sync'],
    }
    assert payload['analysis_handoff']['freshness'] == {
        'freshness_status': 'stale',
        'sync_status': 'failed',
        'sync_lag_seconds': 7200,
        'history_points': 0,
        'published_report_at': None,
    }
    assert payload['analysis_handoff']['trend']['current_output'] == 180.5
    assert payload['analysis_handoff']['contracts']['daily_contract_weight'] == 59.0


def test_build_factory_dashboard_recomputes_stale_llm_summary_when_metrics_drift(monkeypatch) -> None:
    latest_report = SimpleNamespace(
        report_data={
            'leader_summary': {
                'summary_text': '旧的 llm 摘要',
                'summary_source': 'llm',
                'metrics': {'contract_weight': 1.0, 'shipment_weight': 2.0},
            }
        },
        final_text_summary='旧摘要',
        published_at=datetime(2026, 4, 17, 18, 0, tzinfo=UTC),
        text_summary=None,
        final_confirmed_at=None,
        final_confirmed_by=None,
        is_final_version=False,
        generated_at=None,
        id=1,
    )
    monkeypatch.setattr(
        'app.services.report_service._generate_production_report',
        lambda *_args, **_kwargs: {
            'total_output_weight': 180.5,
            'shift_count': 3,
            'auto_confirmed_shifts': 2,
            'pending_or_unreported_shifts': 0,
            'returned_shifts': 0,
            'energy_per_ton': 5.2,
        },
    )
    monkeypatch.setattr(
        'app.services.report_service.energy_service.summarize_energy_for_date',
        lambda *_args, **_kwargs: {
            'total_energy': 1250.0,
            'energy_per_ton': 5.2,
            'electricity_value': 1000.0,
            'gas_value': 200.0,
            'rows': [],
        },
    )
    monkeypatch.setattr('app.services.report_service.build_delivery_status', lambda *_args, **_kwargs: {'delivery_ready': True})
    monkeypatch.setattr(
        'app.services.report_service.mobile_report_service.summarize_mobile_reporting',
        lambda *_args, **_kwargs: {
            'reporting_rate': 100.0,
            'expected_count': 3,
            'reported_count': 3,
            'returned_count': 0,
            'draft_count': 0,
            'submitted_count': 0,
            'unreported_count': 0,
        },
    )
    monkeypatch.setattr('app.services.report_service.build_contract_projection', lambda *_args, **_kwargs: {'daily_contract_weight': 59.0})
    monkeypatch.setattr(
        'app.services.report_service.build_contract_progress_projection',
        lambda *_args, **_kwargs: {'active_contract_count': 1, 'stalled_contract_count': 0, 'active_coil_count': 0, 'today_advanced_weight': 0.0, 'remaining_weight': 0.0},
    )
    monkeypatch.setattr(
        'app.services.report_service.mobile_report_service.summarize_mobile_inventory',
        lambda *_args, **_kwargs: [{'storage_prepared': 12.0, 'storage_finished': 320.0, 'shipment_weight': 184.0, 'storage_inbound_area': 1800.0}],
    )
    monkeypatch.setattr(
        'app.services.report_service._build_exception_lane',
        lambda *_args, **_kwargs: {'mobile_exception_count': 0, 'production_exception_count': 0, 'unreported_shift_count': 0, 'reminder_late_count': 0, 'pending_report_publish_count': 0, 'reconciliation_open_count': 0},
    )
    monkeypatch.setattr('app.services.report_service.mobile_reminder_service.summarize_reminders', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        'app.services.report_service._safe_latest_mes_sync_status',
        lambda *_args, **_kwargs: {'last_run_status': 'success', 'lag_seconds': 30},
    )
    monkeypatch.setattr(
        'app.services.report_service.quality_service.blocker_summary',
        lambda *_args, **_kwargs: {'digest': '无异常', 'has_blockers': False},
    )
    monkeypatch.setattr('app.services.report_service._month_to_date_output', lambda *_args, **_kwargs: 1000.0)
    monkeypatch.setattr('app.services.report_service._build_factory_boss_summary', lambda *_args, **_kwargs: '旧老板摘要')
    monkeypatch.setattr('app.services.report_service.build_management_estimate', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        'app.services.report_service._build_history_digest',
        lambda *_args, **_kwargs: {
            'daily_snapshots': [{'date': '2026-04-17', 'output_weight': 180.5}],
            'month_archive': {},
            'year_archive': {},
        },
    )
    monkeypatch.setattr('app.services.report_service._build_production_lane', lambda *_args, **_kwargs: [])
    monkeypatch.setattr('app.services.report_service._build_energy_lane', lambda *_args, **_kwargs: [])
    monkeypatch.setattr('app.services.report_service._build_canonical_workshop_output_summary', lambda *_args, **_kwargs: [])
    monkeypatch.setattr('app.services.report_service.build_workshop_attendance_summary', lambda *_args, **_kwargs: [])
    monkeypatch.setattr('app.services.report_service._build_workshop_reporting_status', lambda *_args, **_kwargs: [])

    payload = report_service.build_factory_dashboard(FactoryDashboardDB(latest_report), target_date=date(2026, 4, 17))

    assert payload['leader_summary']['summary_source'] == 'deterministic'
    assert payload['leader_summary']['summary_text'] != '旧的 llm 摘要'
    assert '发货 184.00 吨' in payload['leader_summary']['summary_text']
    assert payload['blocker_summary'] == {
        'has_blockers': False,
        'digest': '无异常',
    }
    assert payload['analysis_handoff']['surface'] == 'factory'
    assert payload['analysis_handoff']['readiness'] is True
    assert payload['analysis_handoff']['priority'] == 'low'
    assert payload['analysis_handoff']['attention_flags'] == []
    assert payload['analysis_handoff']['data_gaps'] == []
    assert payload['analysis_handoff']['section_matrix'] == {
        'healthy_sections': ['reporting', 'delivery', 'energy', 'contracts', 'risk'],
        'warning_sections': [],
        'blocked_sections': [],
        'idle_sections': [],
    }
    assert payload['analysis_handoff']['section_reasons'] == {
        'reporting': [],
        'delivery': [],
        'energy': [],
        'contracts': [],
        'risk': [],
    }
    assert payload['analysis_handoff']['source_matrix'] == {
        'reporting': ['主操直录'],
        'delivery': ['系统汇总', '结果发布'],
        'energy': ['专项补录', '系统汇总'],
        'contracts': ['专项补录', '系统汇总'],
        'risk': ['系统汇总'],
    }
    assert payload['analysis_handoff']['source_variants'] == {
        'reporting': ['mobile'],
        'delivery': ['system', 'publish'],
        'energy': ['owner_only', 'system'],
        'contracts': ['owner_only', 'system'],
        'risk': ['system'],
    }
    assert payload['analysis_handoff']['action_matrix'] == {
        'reporting': ['watch_reporting_arrivals'],
        'delivery': ['watch_delivery_release'],
        'energy': ['watch_energy_baseline'],
        'contracts': ['watch_contract_progress'],
        'risk': ['watch_risk_signals'],
    }
    assert payload['analysis_handoff']['freshness'] == {
        'freshness_status': 'fresh',
        'sync_status': 'success',
        'sync_lag_seconds': 30,
        'history_points': 1,
        'published_report_at': '2026-04-17T18:00:00+00:00',
    }
    assert payload['analysis_handoff']['risk']['blocker_digest'] == '无异常'
    assert payload['analysis_handoff']['trend']['current_output'] == 180.5
