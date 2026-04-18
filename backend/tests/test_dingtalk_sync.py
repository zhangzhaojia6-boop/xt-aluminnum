from app.services import dingtalk_service


def test_sync_clock_records_gracefully_handles_api_unavailable(monkeypatch) -> None:
    warnings = []

    monkeypatch.setattr(
        'app.services.dingtalk_service.service.fetch_clock_records',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('dingtalk down')),
    )
    monkeypatch.setattr('app.services.dingtalk_service.logger.warning', lambda message, *args: warnings.append(message % args))

    summary = dingtalk_service.sync_clock_records(
        object(),
        start_date='2026-03-27',
        end_date='2026-03-27',
    )

    assert summary == {'synced': 0, 'skipped': 0, 'failed': 0}
    assert warnings
    assert 'dingtalk down' in warnings[0]
