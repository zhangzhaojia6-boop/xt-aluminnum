from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import check_mes_readonly_reliability as script


def _report(*, status: str = 'pass') -> dict:
    return {
        'status': status,
        'business_date_count': 3,
        'business_dates': ['2026-07-15', '2026-07-16', '2026-07-17'],
        'query_results': [],
        'blockers': [] if status == 'pass' else [{'code': 'mes_sync_stale'}],
    }


def test_output_path_must_stay_below_acceptance_root(tmp_path: Path) -> None:
    allowed = script.resolve_output_path('phase3/report.json', output_root=tmp_path)

    assert allowed == (tmp_path / 'phase3' / 'report.json').resolve()
    with pytest.raises(ValueError, match='acceptance output root'):
        script.resolve_output_path('../outside.json', output_root=tmp_path)


def test_run_writes_sanitized_json_for_three_explicit_dates(monkeypatch, tmp_path: Path, capsys) -> None:
    captured = {}

    def fake_build(_db, **kwargs):
        captured.update(kwargs)
        return _report()

    monkeypatch.setattr(script, 'build_mes_readonly_reliability_report', fake_build)
    output_path = tmp_path / 'phase3.json'
    session = type('Session', (), {'close': lambda self: None})()

    code = script.run(
        [
            '--business-date',
            '2026-07-15',
            '--business-date',
            '2026-07-16',
            '--business-date',
            '2026-07-17',
            '--json',
            '--fault-drill',
            '--output',
            output_path.name,
        ],
        session_factory=lambda: session,
        adapter=object(),
        now=datetime(2026, 7, 18, 12, 0, tzinfo=ZoneInfo('Asia/Shanghai')),
        output_root=tmp_path,
    )

    assert code == 0
    assert captured['business_dates'] == (
        script.date(2026, 7, 15),
        script.date(2026, 7, 16),
        script.date(2026, 7, 17),
    )
    assert captured['run_fault_drills'] is True
    assert json.loads(output_path.read_text(encoding='utf-8'))['status'] == 'pass'
    assert json.loads(capsys.readouterr().out)['status'] == 'pass'


def test_run_returns_nonzero_for_blocked_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(script, 'build_mes_readonly_reliability_report', lambda *_args, **_kwargs: _report(status='blocked'))
    session = type('Session', (), {'close': lambda self: None})()

    code = script.run(
        ['--days', '3', '--json'],
        session_factory=lambda: session,
        adapter=object(),
        now=datetime(2026, 7, 18, 12, 0, tzinfo=ZoneInfo('Asia/Shanghai')),
        output_root=tmp_path,
    )

    assert code == 1


def test_run_initializes_configured_adapter_when_not_injected(monkeypatch, tmp_path: Path) -> None:
    configured_adapter = object()
    selected = []
    captured = {}
    session = type('Session', (), {'close': lambda self: None})()

    monkeypatch.setattr(script, 'create_mes_adapter', lambda: configured_adapter)
    monkeypatch.setattr(script, 'set_mes_adapter', selected.append)

    def fake_build(_db, **kwargs):
        captured.update(kwargs)
        return _report()

    monkeypatch.setattr(script, 'build_mes_readonly_reliability_report', fake_build)

    code = script.run(
        ['--days', '3', '--json'],
        session_factory=lambda: session,
        now=datetime(2026, 7, 18, 12, 0, tzinfo=ZoneInfo('Asia/Shanghai')),
        output_root=tmp_path,
    )

    assert code == 0
    assert selected == [configured_adapter]
    assert captured['adapter'] is configured_adapter
