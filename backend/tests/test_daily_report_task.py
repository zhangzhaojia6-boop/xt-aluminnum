from datetime import date

from app.tasks import daily_report


class FakeSession:
    def __init__(self, events: list | None = None) -> None:
        self.commits = 0
        self.events = events if events is not None else []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1
        self.events.append(('commit', self.commits))


def test_generate_forecast_daily_report_defaults_to_last_completed_business_day(monkeypatch) -> None:
    session = FakeSession()
    calls: list[dict] = []

    monkeypatch.setattr(daily_report, 'last_completed_production_business_date', lambda: date(2026, 6, 1))
    monkeypatch.setattr(daily_report, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(
        daily_report.report_service,
        'generate_production_stage_report',
        lambda **kwargs: calls.append(kwargs),
    )

    result = daily_report.generate_forecast_daily_report()

    assert result == {'status': 'ok', 'business_date': '2026-06-01', 'stage': 'forecast'}
    assert calls == [{
        'db': session,
        'report_date': date(2026, 6, 1),
        'stage': 'forecast',
        'scope': 'auto_confirmed',
        'output_mode': 'both',
        'operator': None,
    }]
    assert session.commits == 0


def test_generate_forecast_daily_report_respects_explicit_target_date(monkeypatch) -> None:
    session = FakeSession()
    calls: list[dict] = []

    monkeypatch.setattr(
        daily_report,
        'last_completed_production_business_date',
        lambda: (_ for _ in ()).throw(AssertionError('default business date should not be used')),
    )
    monkeypatch.setattr(daily_report, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(
        daily_report.report_service,
        'generate_production_stage_report',
        lambda **kwargs: calls.append(kwargs),
    )

    result = daily_report.generate_forecast_daily_report(target_date=date(2026, 5, 30))

    assert result == {'status': 'ok', 'business_date': '2026-05-30', 'stage': 'forecast'}
    assert calls[0]['report_date'] == date(2026, 5, 30)
    assert calls[0]['stage'] == 'forecast'


def test_generate_final_daily_report_runs_chain_in_order(monkeypatch) -> None:
    events: list[tuple] = []
    session = FakeSession(events)

    monkeypatch.setattr(daily_report, 'last_completed_production_business_date', lambda: date(2026, 6, 1))
    monkeypatch.setattr(daily_report, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(
        daily_report.aggregator_agent,
        'execute',
        lambda *, db, target_date: events.append(('aggregator', target_date, db)),
    )
    monkeypatch.setattr(
        daily_report.report_service,
        'generate_production_stage_report',
        lambda **kwargs: events.append((
            'stage',
            kwargs['stage'],
            kwargs['report_date'],
            kwargs['db'],
            kwargs['scope'],
            kwargs['output_mode'],
            kwargs['operator'],
        )),
    )
    monkeypatch.setattr(
        daily_report.reporter_agent,
        'execute',
        lambda *, db, target_date: events.append(('reporter', target_date, db)),
    )

    result = daily_report.generate_final_daily_report()

    assert result == {'status': 'ok', 'business_date': '2026-06-01', 'stage': 'final'}
    assert events == [
        ('aggregator', date(2026, 6, 1), session),
        ('commit', 1),
        ('stage', 'final', date(2026, 6, 1), session, 'auto_confirmed', 'both', None),
        ('reporter', date(2026, 6, 1), session),
        ('commit', 2),
    ]
    assert session.commits == 2


def test_generate_final_daily_report_respects_explicit_target_date(monkeypatch) -> None:
    session = FakeSession()
    seen: list[date] = []

    monkeypatch.setattr(
        daily_report,
        'last_completed_production_business_date',
        lambda: (_ for _ in ()).throw(AssertionError('default business date should not be used')),
    )
    monkeypatch.setattr(daily_report, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(daily_report.aggregator_agent, 'execute', lambda *, db, target_date: seen.append(target_date))
    monkeypatch.setattr(
        daily_report.report_service,
        'generate_production_stage_report',
        lambda **kwargs: seen.append(kwargs['report_date']),
    )
    monkeypatch.setattr(daily_report.reporter_agent, 'execute', lambda *, db, target_date: seen.append(target_date))

    result = daily_report.generate_final_daily_report(target_date=date(2026, 5, 30))

    assert result == {'status': 'ok', 'business_date': '2026-05-30', 'stage': 'final'}
    assert seen == [date(2026, 5, 30), date(2026, 5, 30), date(2026, 5, 30)]


def test_generate_daily_reports_calls_final_compatibility_wrapper(monkeypatch) -> None:
    seen: list[date | None] = []

    def fake_generate_final_daily_report(target_date=None):
        seen.append(target_date)
        return {'status': 'ok', 'business_date': '2026-05-30', 'stage': 'final'}

    monkeypatch.setattr(daily_report, 'generate_final_daily_report', fake_generate_final_daily_report)

    result = daily_report.generate_daily_reports(target_date=date(2026, 5, 30))

    assert result == {'status': 'ok', 'business_date': '2026-05-30', 'stage': 'final'}
    assert seen == [date(2026, 5, 30)]
