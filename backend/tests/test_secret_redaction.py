import logging
import sys
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.core.logging import JsonLogFormatter
from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.services import mes_sync_service


def test_redact_secret_text_masks_connection_style_values() -> None:
    text = 'server=db;uid=readonly;password=secret-pass;token=abc123'

    redacted = redact_secret_text(text)

    assert 'secret-pass' not in redacted
    assert 'readonly' not in redacted
    assert 'abc123' not in redacted
    assert 'password=<redacted>' in redacted
    assert 'uid=<redacted>' in redacted
    assert 'token=<redacted>' in redacted


def test_redact_secret_text_masks_uri_connection_passwords() -> None:
    text = (
        'postgresql://user:secretpass@db.example.com/app '
        'mysql://readonly:mysqlpass@db.example.com/app '
        'mssql+pyodbc://user:driver-secret@db.example.com/app '
        'mysql+pymysql://user:pymysql-secret@db.example.com/app '
        'https://api-user:http-secret@example.com/token '
        'https://example.com/docs '
        'https://example.com/public'
    )

    redacted = redact_secret_text(text)

    assert 'secretpass' not in redacted
    assert 'mysqlpass' not in redacted
    assert 'driver-secret' not in redacted
    assert 'pymysql-secret' not in redacted
    assert 'http-secret' not in redacted
    assert 'postgresql://user:secretpass@db.example.com/app' not in redacted
    assert 'mysql://readonly:mysqlpass@db.example.com/app' not in redacted
    assert 'mssql+pyodbc://user:driver-secret@db.example.com/app' not in redacted
    assert 'mysql+pymysql://user:pymysql-secret@db.example.com/app' not in redacted
    assert 'https://api-user:http-secret@example.com/token' not in redacted
    assert 'postgresql://' not in redacted
    assert 'mysql://' not in redacted
    assert 'mssql+pyodbc://' not in redacted
    assert 'mysql+pymysql://' not in redacted
    assert 'https://api-user:' not in redacted
    assert '<redacted-connection-uri>' in redacted
    assert 'https://example.com/docs' in redacted
    assert 'https://example.com/public' in redacted


def test_filter_sensitive_mapping_removes_private_customer_and_secret_fields() -> None:
    payload = filter_sensitive_mapping({
        'TrackingCardNo': 'S-2-085-2',
        'password': 'secret-pass',
        'CustomerMobile': '13800000000',
        'CustomerAddress': 'private address',
        'Email': 'a@example.com',
    })

    assert payload == {'TrackingCardNo': 'S-2-085-2'}


def test_filter_sensitive_mapping_converts_values_to_json_safe_types() -> None:
    payload = filter_sensitive_mapping({
        'Id': UUID('00000000-0000-0000-0000-000000000001'),
        'OperateDate': datetime(2026, 6, 5, 7, 23, 58),
        'NetWeight': Decimal('1200.5'),
        'Items': [{'CreateDate': datetime(2026, 6, 5, 8, 0), 'Password': 'secret-pass'}],
    })

    assert payload == {
        'Id': '00000000-0000-0000-0000-000000000001',
        'OperateDate': '2026-06-05T07:23:58',
        'NetWeight': 1200.5,
        'Items': [{'CreateDate': '2026-06-05T08:00:00'}],
    }


def test_json_log_formatter_redacts_message_and_exception() -> None:
    formatter = JsonLogFormatter()
    logger = logging.getLogger('test-redaction')

    try:
        raise RuntimeError('connect failed password=secret-pass uid=readonly')
    except RuntimeError:
        record = logger.makeRecord(
            'test-redaction',
            logging.ERROR,
            __file__,
            1,
            'failed with pwd=secret-pass',
            (),
            exc_info=sys.exc_info(),
        )

    text = formatter.format(record)

    assert 'secret-pass' not in text
    assert 'readonly' not in text
    assert 'pwd=<redacted>' in text
    assert 'uid=<redacted>' in text


def test_mes_sync_status_redacts_last_run_error(monkeypatch) -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace

    class _Query:
        def __init__(self, value):
            self._value = value

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return self._value

    class _DB:
        def query(self, model):
            if model is mes_sync_service.MesSyncCursor:
                return _Query(SimpleNamespace(cursor_value='c1', last_event_at=None, last_synced_at=None))
            if model is mes_sync_service.MesSyncRunLog:
                return _Query(
                    SimpleNamespace(
                        status='failed',
                        started_at=datetime(2026, 6, 4, 8, 0, tzinfo=UTC),
                        finished_at=datetime(2026, 6, 4, 8, 1, tzinfo=UTC),
                        fetched_count=0,
                        upserted_count=0,
                        replayed_count=0,
                        error_message='driver error password=secret-pass uid=readonly',
                    )
                )
            raise AssertionError(model)

    monkeypatch.setattr(mes_sync_service.settings, 'MES_ADAPTER', 'sqlserver')
    monkeypatch.setattr(mes_sync_service, 'compute_sync_lag_seconds', lambda db, cursor_key, now: None)

    payload = mes_sync_service.latest_sync_status(_DB())

    assert 'secret-pass' not in repr(payload)
    assert 'readonly' not in repr(payload)
    assert payload['last_error'] == 'driver error password=<redacted> uid=<redacted>'
