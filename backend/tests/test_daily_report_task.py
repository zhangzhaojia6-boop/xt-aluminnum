from datetime import date

from app.tasks import daily_report


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1


def test_generate_daily_reports_defaults_to_last_completed_business_day(monkeypatch) -> None:
    session = FakeSession()
    calls: list[tuple[str, date, FakeSession]] = []

    monkeypatch.setattr(daily_report, 'last_completed_production_business_date', lambda: date(2026, 6, 1))
    monkeypatch.setattr(daily_report, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(
        daily_report.aggregator_agent,
        'execute',
        lambda *, db, target_date: calls.append(('aggregator', target_date, db)),
    )
    monkeypatch.setattr(
        daily_report.reporter_agent,
        'execute',
        lambda *, db, target_date: calls.append(('reporter', target_date, db)),
    )
    monkeypatch.setattr(
        daily_report,
        'build_daily_report_product',
        lambda db, target_date: calls.append(('product', target_date, db)) or {'status': 'ready', 'text': '日报成品正文'},
    )
    monkeypatch.setattr(
        daily_report.hermes_rag_service,
        'archive_latest_daily_report_to_rag',
        lambda db, report_date, generated_by: calls.append(('archive', report_date, db)),
    )

    result = daily_report.generate_daily_reports()

    assert result == {'status': 'ok', 'business_date': '2026-06-01', 'report_status': 'ready', 'text': '日报成品正文'}
    assert calls == [
        ('aggregator', date(2026, 6, 1), session),
        ('product', date(2026, 6, 1), session),
        ('archive', date(2026, 6, 1), session),
        ('reporter', date(2026, 6, 1), session),
    ]
    assert session.commits == 4


def test_generate_daily_reports_respects_explicit_target_date(monkeypatch) -> None:
    session = FakeSession()
    seen: list[date] = []

    monkeypatch.setattr(daily_report, 'last_completed_production_business_date', lambda: date(2026, 6, 1))
    monkeypatch.setattr(daily_report, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(daily_report.aggregator_agent, 'execute', lambda *, db, target_date: seen.append(target_date))
    monkeypatch.setattr(daily_report.reporter_agent, 'execute', lambda *, db, target_date: seen.append(target_date))
    monkeypatch.setattr(
        daily_report,
        'build_daily_report_product',
        lambda db, target_date: seen.append(target_date) or {'status': 'ready', 'text': '日报成品正文'},
    )
    monkeypatch.setattr(
        daily_report.hermes_rag_service,
        'archive_latest_daily_report_to_rag',
        lambda db, report_date, generated_by: seen.append(report_date),
    )

    result = daily_report.generate_daily_reports(target_date=date(2026, 5, 30))

    assert result == {'status': 'ok', 'business_date': '2026-05-30', 'report_status': 'ready', 'text': '日报成品正文'}
    assert seen == [date(2026, 5, 30), date(2026, 5, 30), date(2026, 5, 30), date(2026, 5, 30)]
