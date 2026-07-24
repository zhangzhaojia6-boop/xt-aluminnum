from datetime import date
from types import SimpleNamespace

from app.services import hermes_rag_service
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
        daily_report,
        'build_daily_report_product',
        lambda db, target_date: calls.append(('product', target_date, db)) or {'status': 'ready', 'text': '日报成品正文'},
    )
    monkeypatch.setattr(
        daily_report.hermes_rag_service,
        'archive_latest_daily_report_to_rag',
        lambda db, report_date, generated_by: calls.append(('archive', report_date, db)),
    )
    monkeypatch.setattr(
        daily_report.daily_report_delivery_service,
        'deliver_completed_daily_report',
        lambda db, target_date: calls.append(('delivery', target_date, db)) or {'status': 'sent', 'outbox_message_id': 9},
    )

    result = daily_report.generate_daily_reports()

    assert result == {
        'status': 'ok',
        'business_date': '2026-06-01',
        'report_status': 'ready',
        'text': '日报成品正文',
        'delivery': {'status': 'sent', 'outbox_message_id': 9},
    }
    assert calls == [
        ('aggregator', date(2026, 6, 1), session),
        ('product', date(2026, 6, 1), session),
        ('archive', date(2026, 6, 1), session),
        ('delivery', date(2026, 6, 1), session),
    ]
    assert session.commits == 4


def test_generate_daily_reports_respects_explicit_target_date(monkeypatch) -> None:
    session = FakeSession()
    seen: list[date] = []

    monkeypatch.setattr(daily_report, 'last_completed_production_business_date', lambda: date(2026, 6, 1))
    monkeypatch.setattr(daily_report, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(daily_report.aggregator_agent, 'execute', lambda *, db, target_date: seen.append(target_date))
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
    monkeypatch.setattr(
        daily_report.daily_report_delivery_service,
        'deliver_completed_daily_report',
        lambda db, target_date: seen.append(target_date) or {'status': 'sent'},
    )

    result = daily_report.generate_daily_reports(target_date=date(2026, 5, 30))

    assert result == {
        'status': 'ok',
        'business_date': '2026-05-30',
        'report_status': 'ready',
        'text': '日报成品正文',
        'delivery': {'status': 'sent'},
    }
    assert seen == [date(2026, 5, 30), date(2026, 5, 30), date(2026, 5, 30), date(2026, 5, 30)]


def test_build_daily_report_product_blocks_stale_text_when_template_missing_fields(monkeypatch) -> None:
    report = SimpleNamespace(
        id=7,
        report_data={'template_daily_report': {'status': 'ready', 'text': '旧日报正文'}},
        final_text_summary='旧日报正文',
        text_summary='旧摘要',
        generated_at=None,
        delivery_ready=True,
        status='draft',
        published_at=None,
    )
    db = SimpleNamespace(flush=lambda: None)
    monkeypatch.setattr(daily_report, '_ensure_daily_report', lambda *_args, **_kwargs: report)
    monkeypatch.setattr(
        daily_report.template_daily_report,
        'apply_template_daily_report_to_report',
        lambda *_args, **_kwargs: {
            'status': 'blocked',
            'text': None,
            'missing_fields': ['total_output_daily'],
            'conflicts': [],
        },
    )

    result = daily_report.build_daily_report_product(db, target_date=date(2026, 6, 1))

    assert result['status'] == 'blocked'
    assert result['text'] == ''
    assert result['missing_fields'] == ['total_output_daily']
    assert report.final_text_summary is None
    assert report.text_summary == '旧摘要'
    assert report.delivery_ready is False
    assert report.status == 'draft'


def test_build_daily_report_product_disables_final_report_reference_adoption(monkeypatch) -> None:
    report = SimpleNamespace(
        id=7,
        report_data={},
        final_text_summary=None,
        text_summary=None,
        generated_at=None,
        delivery_ready=False,
        status='draft',
        published_at=None,
    )
    db = SimpleNamespace(flush=lambda: None)
    captured = {}
    monkeypatch.setattr(daily_report, '_ensure_daily_report', lambda *_args, **_kwargs: report)

    def fake_apply(*_args, **kwargs):
        captured.update(kwargs)
        return {'status': 'blocked', 'text': None, 'missing_fields': ['total_output_daily'], 'conflicts': []}

    monkeypatch.setattr(daily_report.template_daily_report, 'apply_template_daily_report_to_report', fake_apply)

    daily_report.build_daily_report_product(db, target_date=date(2026, 6, 1))

    assert captured['allow_datahub_final_reference'] is False


def test_build_daily_report_product_clears_previous_template_text_summary_when_blocked(monkeypatch) -> None:
    report = SimpleNamespace(
        id=7,
        report_data={'template_daily_report': {'status': 'ready', 'text': '旧日报正文'}},
        final_text_summary='旧日报正文',
        text_summary='旧日报正文',
        generated_at=None,
        delivery_ready=True,
        status='draft',
        published_at=None,
    )
    db = SimpleNamespace(flush=lambda: None)
    monkeypatch.setattr(daily_report, '_ensure_daily_report', lambda *_args, **_kwargs: report)
    monkeypatch.setattr(
        daily_report.template_daily_report,
        'apply_template_daily_report_to_report',
        lambda *_args, **_kwargs: {
            'status': 'blocked',
            'text': None,
            'missing_fields': ['total_output_daily'],
            'conflicts': [],
        },
    )

    daily_report.build_daily_report_product(db, target_date=date(2026, 6, 1))

    assert report.final_text_summary is None
    assert report.text_summary is None


def test_build_daily_report_product_unpublishes_report_when_template_becomes_blocked(monkeypatch) -> None:
    report = SimpleNamespace(
        id=7,
        report_data={'template_daily_report': {'status': 'ready', 'text': '旧日报正文'}},
        final_text_summary='旧日报正文',
        text_summary='旧日报正文',
        generated_at=None,
        delivery_ready=True,
        status='published',
        published_at='2026-06-18T08:00:00Z',
        published_by=3,
        reviewed_at='2026-06-18T07:50:00Z',
        reviewed_by=2,
        final_confirmed_at='2026-06-18T08:10:00Z',
        final_confirmed_by=4,
        is_final_version=True,
    )
    db = SimpleNamespace(flush=lambda: None)
    monkeypatch.setattr(daily_report, '_ensure_daily_report', lambda *_args, **_kwargs: report)
    monkeypatch.setattr(
        daily_report.template_daily_report,
        'apply_template_daily_report_to_report',
        lambda *_args, **_kwargs: {
            'status': 'blocked',
            'text': None,
            'missing_fields': ['total_output_daily'],
            'conflicts': [],
        },
    )

    daily_report.build_daily_report_product(db, target_date=date(2026, 6, 1))

    assert report.status == 'draft'
    assert report.published_at is None
    assert report.published_by is None
    assert report.reviewed_at is None
    assert report.reviewed_by is None
    assert report.final_confirmed_at is None
    assert report.final_confirmed_by is None
    assert report.is_final_version is False
    assert report.delivery_ready is False


def test_archive_daily_report_to_rag_skips_blocked_template_payload(monkeypatch) -> None:
    report = SimpleNamespace(
        report_data={'template_daily_report': {'status': 'blocked', 'missing_fields': ['total_output_daily']}},
        final_text_summary='旧日报正文',
        text_summary='旧摘要',
    )
    monkeypatch.setattr(
        hermes_rag_service,
        'create_document_from_bytes',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('blocked report must not be archived')),
    )

    assert hermes_rag_service.archive_daily_report_to_rag(SimpleNamespace(), report=report) is None
