from app.services.deterministic_orchestration_service import build_runtime_orchestration_snapshot


def _worker_statuses(snapshot: dict) -> dict[str, str]:
    return {item['key']: item['status'] for item in snapshot['workers']}


def test_runtime_orchestration_snapshot_marks_clean_inputs_healthy() -> None:
    snapshot = build_runtime_orchestration_snapshot(
        mobile_summary={
            'reporting_rate': 100,
            'unreported_count': 0,
            'returned_count': 0,
            'late_count': 0,
        },
        exception_lane={
            'mobile_exception_count': 0,
            'production_exception_count': 0,
            'reconciliation_open_count': 0,
        },
        delivery_status={
            'delivery_ready': True,
            'missing_steps': [],
            'blocker_count': 0,
        },
        reminder_summary={'today_reminder_count': 0},
    )

    assert snapshot['reliability_score'] == 100.0
    assert snapshot['risk_level'] == 'low'
    assert snapshot['blocking_count'] == 0
    assert snapshot['bottlenecks'] == []
    assert snapshot['scores'] == {
        'coverage': 100.0,
        'quality': 100.0,
        'delivery': 100.0,
    }
    assert _worker_statuses(snapshot) == {
        'algorithm_pipeline': 'healthy',
        'analysis_agent': 'healthy',
        'execution_agent': 'healthy',
    }


def test_runtime_orchestration_snapshot_surfaces_blocking_bottlenecks() -> None:
    snapshot = build_runtime_orchestration_snapshot(
        mobile_summary={
            'reporting_rate': 92,
            'unreported_count': 2,
            'returned_count': 1,
            'late_count': 3,
        },
        exception_lane={
            'mobile_exception_count': 1,
            'production_exception_count': 2,
            'reconciliation_open_count': 1,
        },
        delivery_status={
            'delivery_ready': False,
            'missing_steps': ['report_unpublished', 'quality_open'],
            'blocker_count': 1,
        },
        reminder_summary={'today_reminder_count': 5},
    )

    assert snapshot['reliability_score'] == 62.7
    assert snapshot['risk_level'] == 'high'
    assert snapshot['blocking_count'] == 5
    assert snapshot['bottlenecks'] == [
        '班次缺报',
        '自动校验退回',
        '异常待清理',
        '差异未闭环',
        '交付链路未完成',
    ]
    assert snapshot['scores'] == {
        'coverage': 72.0,
        'quality': 79.0,
        'delivery': 25.0,
    }
    assert _worker_statuses(snapshot) == {
        'algorithm_pipeline': 'blocked',
        'analysis_agent': 'blocked',
        'execution_agent': 'blocked',
    }


def test_runtime_orchestration_snapshot_coerces_invalid_numeric_inputs() -> None:
    snapshot = build_runtime_orchestration_snapshot(
        mobile_summary={
            'reporting_rate': 'invalid',
            'unreported_count': 'invalid',
            'returned_count': None,
            'late_count': '2',
        },
        exception_lane={
            'mobile_exception_count': 'invalid',
            'production_exception_count': '3.5',
            'reconciliation_open_count': None,
        },
        delivery_status={
            'delivery_ready': True,
            'missing_steps': ['', None, 'archive_missing'],
            'blocker_count': 'invalid',
        },
        reminder_summary={'today_reminder_count': 'invalid'},
    )

    assert snapshot['reliability_score'] == 47.8
    assert snapshot['risk_level'] == 'high'
    assert snapshot['blocking_count'] == 1
    assert snapshot['bottlenecks'] == ['交付链路未完成']
    assert snapshot['scores'] == {
        'coverage': 0.0,
        'quality': 100.0,
        'delivery': 51.0,
    }
    assert _worker_statuses(snapshot) == {
        'algorithm_pipeline': 'alert',
        'analysis_agent': 'healthy',
        'execution_agent': 'blocked',
    }
