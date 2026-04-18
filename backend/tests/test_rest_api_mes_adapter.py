from datetime import UTC, datetime

from app.adapters.rest_api_mes_adapter import RestApiMesAdapter


class _Response:
    def __init__(self, *, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 404:
            raise RuntimeError(f'http_{self.status_code}')

    def json(self):
        return self._payload


def test_rest_api_mes_adapter_reads_tracking_card_info():
    calls = []

    def sender(**kwargs):
        calls.append(kwargs)
        return _Response(
            payload={
                'card_no': 'ra260001',
                'process_route_code': 'MES-RA',
                'alloy_grade': 'A3003',
                'batch_no': 'B-1',
                'qr_code': 'QR-1',
                'metadata': {'customer_name': 'ACME'},
            }
        )

    adapter = RestApiMesAdapter(base_url='https://mes.example.com/api', api_key='secret', sender=sender)
    payload = adapter.get_tracking_card_info('RA260001')

    assert payload is not None
    assert payload.card_no == 'RA260001'
    assert payload.batch_no == 'B-1'
    assert payload.qr_code == 'QR-1'
    assert calls[0]['headers']['Authorization'] == 'Bearer secret'


def test_rest_api_mes_adapter_reads_coil_snapshots():
    def sender(**kwargs):
        return _Response(
            payload={
                'items': [
                    {
                        'coil_id': 'coil-1',
                        'tracking_card_no': 'RA260001',
                        'batch_no': 'B-1',
                        'qr_code': 'QR-1',
                        'contract_no': 'HT-1',
                        'workshop_code': 'ZR2',
                        'process_code': 'casting',
                        'machine_code': 'ZD-1',
                        'shift_code': 'A',
                        'status': 'in_progress',
                        'event_time': '2026-04-11T10:00:00Z',
                        'updated_at': '2026-04-11T10:00:10Z',
                    }
                ],
                'next_cursor': 'cursor-2',
            }
        )

    adapter = RestApiMesAdapter(base_url='https://mes.example.com/api', sender=sender)
    items, cursor = adapter.list_coil_snapshots(
        cursor='cursor-1',
        updated_after=datetime(2026, 4, 11, 10, 0, tzinfo=UTC),
        limit=50,
    )

    assert cursor == 'cursor-2'
    assert len(items) == 1
    assert items[0].coil_id == 'coil-1'
    assert items[0].tracking_card_no == 'RA260001'
    assert items[0].updated_at == datetime(2026, 4, 11, 10, 0, 10, tzinfo=UTC)


def test_rest_api_mes_adapter_returns_none_for_404_tracking_card():
    adapter = RestApiMesAdapter(
        base_url='https://mes.example.com/api',
        sender=lambda **kwargs: _Response(status_code=404),
    )

    assert adapter.get_tracking_card_info('RA404') is None

