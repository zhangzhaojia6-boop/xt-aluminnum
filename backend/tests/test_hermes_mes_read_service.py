from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.adapters.mes_adapter import MesSourceRecord, MesStockItem, MesWipTotal, NullMesAdapter
from app.services.hermes_mes_read_service import HermesMesReadService, UnsupportedMesQueryKeyError


SHANGHAI = ZoneInfo('Asia/Shanghai')


@dataclass
class _Call:
    name: str
    kwargs: dict


class _AdapterSpy:
    def __init__(self) -> None:
        self.calls: list[_Call] = []
        self.results: dict[str, object] = {}

    def _record(self, name: str, **kwargs):
        self.calls.append(_Call(name=name, kwargs=kwargs))
        result = self.results.get(name, [])
        if isinstance(result, Exception):
            raise result
        return result

    def list_workshop_process_records_between(self, *, start_at, end_at, limit, offset):
        return self._record(
            'list_workshop_process_records_between',
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            offset=offset,
        )

    def list_stock_records_between(self, *, start_at, end_at, limit, offset):
        return self._record(
            'list_stock_records_between',
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            offset=offset,
        )

    def list_finished_inbound_records_between(self, *, start_at, end_at, limit, offset):
        return self._record(
            'list_finished_inbound_records_between',
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            offset=offset,
        )

    def list_delivery_records_between(self, *, start_at, end_at, limit, offset):
        return self._record(
            'list_delivery_records_between',
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            offset=offset,
        )

    def list_material_records_between(self, *, start_at, end_at, limit, offset):
        return self._record(
            'list_material_records_between',
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            offset=offset,
        )

    def list_wip_totals(self):
        return self._record('list_wip_totals')

    def list_stock(self, *, limit):
        return self._record('list_stock', limit=limit)

    def list_yield_records(self, *, limit):
        return self._record('list_yield_records', limit=limit)


def test_read_sources_uses_business_window_and_fixed_adapter_methods() -> None:
    adapter = _AdapterSpy()
    adapter.results['list_workshop_process_records_between'] = [
        MesSourceRecord(
            source_id='workshop-1',
            source_path='sqlserver:workshop_process_records',
            event_time=datetime(2026, 6, 18, 8, 1, tzinfo=SHANGHAI),
            metadata={'Id': 'workshop-1'},
        )
    ]
    adapter.results['list_wip_totals'] = [
        MesWipTotal(
            workshop_name='冷轧',
            doing_count=3,
            doing_weight=18.5,
            metadata={'updated_at': datetime(2026, 6, 18, 9, 0, tzinfo=SHANGHAI)},
        )
    ]

    payload = HermesMesReadService(adapter).read_sources(
        business_date=date(2026, 6, 18),
        query_keys=['workshop_process_records', 'wip_totals'],
    )

    assert payload['business_date'] == '2026-06-18'
    assert payload['window'] == {
        'start_at': '2026-06-18T07:50:00+08:00',
        'end_at': '2026-06-19T07:50:00+08:00',
    }
    assert adapter.calls == [
        _Call(
            name='list_workshop_process_records_between',
            kwargs={
                'start_at': datetime(2026, 6, 18, 7, 50, tzinfo=SHANGHAI),
                'end_at': datetime(2026, 6, 19, 7, 50, tzinfo=SHANGHAI),
                'limit': 5000,
                'offset': 0,
            },
        ),
        _Call(name='list_wip_totals', kwargs={}),
    ]
    assert payload['records']['workshop_process_records'][0]['event_time'] == '2026-06-18T08:01:00+08:00'
    assert payload['records']['wip_totals'][0]['metadata']['updated_at'] == '2026-06-18T09:00:00+08:00'
    assert payload['source_status']['mes'] == 'ok'
    assert payload['source_status']['sources']['workshop_process_records'] == {'status': 'ok', 'count': 1}
    assert payload['source_status']['sources']['wip_totals'] == {'status': 'ok', 'count': 1}


def test_read_sources_rejects_unsupported_query_key_before_calling_adapter() -> None:
    adapter = _AdapterSpy()

    with pytest.raises(UnsupportedMesQueryKeyError):
        HermesMesReadService(adapter).read_sources(
            business_date=date(2026, 6, 18),
            query_keys=['workshop_process_records', 'drop_table_now'],
        )

    assert adapter.calls == []


def test_read_sources_caps_limit_at_20000_and_serializes_dataclasses_to_plain_data() -> None:
    adapter = _AdapterSpy()
    adapter.results['list_stock'] = [
        MesStockItem(
            coil_key='coil-1',
            tracking_card_no='R2-7283-1',
            weight=12.3,
            destination='成品库',
            metadata={
                'CreateDate': datetime(2026, 6, 18, 8, 30, tzinfo=SHANGHAI),
                'BusinessDate': date(2026, 6, 18),
            },
        )
    ]

    payload = HermesMesReadService(adapter).read_sources(
        business_date=date(2026, 6, 18),
        query_keys=['stock'],
        limit=999999,
    )

    assert adapter.calls == [_Call(name='list_stock', kwargs={'limit': 20000})]
    assert payload['records']['stock'] == [
        {
            'coil_key': 'coil-1',
            'tracking_card_no': 'R2-7283-1',
            'weight': 12.3,
            'destination': '成品库',
            'metadata': {
                'CreateDate': '2026-06-18T08:30:00+08:00',
                'BusinessDate': '2026-06-18',
            },
        }
    ]


def test_read_sources_marks_all_empty_sources_as_empty() -> None:
    adapter = _AdapterSpy()
    adapter.results['list_stock_records_between'] = []
    adapter.results['list_yield_records'] = []

    payload = HermesMesReadService(adapter).read_sources(
        business_date=date(2026, 6, 18),
        query_keys=['stock_records', 'yield_records'],
    )

    assert payload['records'] == {
        'stock_records': [],
        'yield_records': [],
    }
    assert payload['source_status'] == {
        'mes': 'empty',
        'sources': {
            'stock_records': {'status': 'empty', 'count': 0},
            'yield_records': {'status': 'empty', 'count': 0},
        },
    }
    assert payload['source_errors'] == {}


def test_read_sources_marks_timeout_and_redacts_sensitive_error_text() -> None:
    adapter = _AdapterSpy()
    adapter.results['list_stock_records_between'] = TimeoutError(
        'MES timed out password=secret-pass token=abc123'
    )

    payload = HermesMesReadService(adapter).read_sources(
        business_date=date(2026, 6, 18),
        query_keys=['stock_records'],
    )

    assert payload['records'] == {}
    assert payload['source_status'] == {
        'mes': 'failed',
        'sources': {
            'stock_records': {'status': 'failed', 'count': 0},
        },
    }
    assert 'secret-pass' not in payload['source_errors']['stock_records']
    assert 'abc123' not in payload['source_errors']['stock_records']
    assert payload['source_errors']['stock_records'] == 'MES timed out password=<redacted> token=<redacted>'


def test_read_sources_marks_partial_failed_when_some_sources_fail() -> None:
    adapter = _AdapterSpy()
    adapter.results['list_material_records_between'] = RuntimeError(
        'driver exploded password=driver-secret'
    )
    adapter.results['list_stock'] = [
        MesStockItem(
            coil_key='coil-1',
            tracking_card_no='MC-1',
            weight=6.5,
            destination='成品库',
        )
    ]

    payload = HermesMesReadService(adapter).read_sources(
        business_date=date(2026, 6, 18),
        query_keys=['material_records', 'stock'],
        workshop_name='冷轧车间',
    )

    assert payload['source_status']['mes'] == 'partial_failed'
    assert payload['source_status']['sources']['material_records'] == {'status': 'failed', 'count': 0}
    assert payload['source_status']['sources']['stock'] == {'status': 'ok', 'count': 1}
    assert payload['records']['stock'][0]['tracking_card_no'] == 'MC-1'
    assert payload['window'] == {
        'start_at': '2026-06-18T07:50:00+08:00',
        'end_at': '2026-06-19T07:50:00+08:00',
    }
    assert payload['source_errors']['material_records'] == 'driver exploded password=<redacted>'


def test_read_sources_marks_unimplemented_adapter_capability_as_failed() -> None:
    payload = HermesMesReadService(NullMesAdapter()).read_sources(
        business_date=date(2026, 6, 18),
        query_keys=['stock_records'],
    )

    assert payload['records'] == {}
    assert payload['source_status'] == {
        'mes': 'failed',
        'sources': {
            'stock_records': {'status': 'failed', 'count': 0},
        },
    }
    assert 'unsupported_adapter_capability' in payload['source_errors']['stock_records']


def test_read_sources_filters_sensitive_mapping_keys_recursively() -> None:
    adapter = _AdapterSpy()
    adapter.results['list_stock'] = [
        MesStockItem(
            coil_key='coil-2',
            tracking_card_no='R2-7283-2',
            weight=8.6,
            destination='成品库',
            metadata={
                'token': 'abc123',
                'nested': {
                    'password': 'secret-pass',
                    'mobile': '13800000000',
                    'ok': 'visible',
                },
                'rows': [
                    {'email': 'a@example.com', 'keep': 'row-1'},
                    {'address': 'private address', 'keep': 'row-2'},
                ],
            },
        )
    ]

    payload = HermesMesReadService(adapter).read_sources(
        business_date=date(2026, 6, 18),
        query_keys=['stock'],
    )

    stock_row = payload['records']['stock'][0]
    assert 'token' not in stock_row['metadata']
    assert stock_row['metadata']['nested'] == {'ok': 'visible'}
    assert stock_row['metadata']['rows'] == [
        {'keep': 'row-1'},
        {'keep': 'row-2'},
    ]
