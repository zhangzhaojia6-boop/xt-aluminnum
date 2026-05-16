from datetime import UTC, date, datetime

from app.adapters.xintai_mes_adapter import XintaiMesAdapter


class _Response:
    def __init__(self, *, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 409:
            raise RuntimeError(f'http_{self.status_code}')

    def json(self):
        return self._payload


def test_xintai_mes_adapter_reads_tracking_card_info() -> None:
    calls = []

    def sender(**kwargs):
        calls.append(kwargs)
        return _Response(
            payload={
                'card_no': 'ra260001',
                'alloy': 'A3003',
                'width': 1250,
                'thickness': 0.8,
                'weight': 9200,
                'process': '冷轧',
                'workshop': '冷轧车间',
            }
        )

    adapter = XintaiMesAdapter(base_url='https://mes.example.com/api', api_key='secret', sender=sender)

    card = adapter.get_tracking_card_info('RA260001')

    assert card is not None
    assert card.card_no == 'RA260001'
    assert card.alloy_grade == 'A3003'
    assert card.process_route_code == '冷轧'
    assert card.metadata['workshop'] == '冷轧车间'
    assert calls[0]['url'].endswith('/cards/RA260001')
    assert calls[0]['headers']['Authorization'] == 'Bearer secret'


def test_xintai_mes_adapter_reads_snapshots_schedule_and_completion() -> None:
    calls = []

    def sender(**kwargs):
        calls.append(kwargs)
        url = kwargs['url']
        if url.endswith('/coils'):
            return _Response(
                payload={
                    'items': [
                        {
                            'id': 'coil-1',
                            'card_no': 'RA260001',
                            'batch': 'B-1',
                            'workshop': 'LZ',
                            'process': 'rolling',
                            'machine': 'LZ-1',
                            'status': 'running',
                            'event_time': '2026-05-16T08:00:00Z',
                            'weight': 9200,
                        }
                    ],
                    'next_cursor': 'cursor-2',
                }
            )
        if url.endswith('/schedule'):
            return _Response(payload={'items': [{'card_no': 'RA260001', 'workshop': 'LZ', 'machine': 'LZ-1'}]})
        if url.endswith('/completions'):
            return _Response(status_code=409, payload={'errcode': 0})
        raise AssertionError(url)

    adapter = XintaiMesAdapter(base_url='https://mes.example.com/api', api_key='secret', sender=sender)

    snapshots, cursor = adapter.list_coil_snapshots(
        cursor='cursor-1',
        updated_after=datetime(2026, 5, 16, 8, tzinfo=UTC),
        limit=50,
    )
    schedule = adapter.get_daily_schedule(date(2026, 5, 16), 'LZ')

    assert cursor == 'cursor-2'
    assert snapshots[0].tracking_card_no == 'RA260001'
    assert snapshots[0].metadata['weight'] == 9200
    assert schedule[0].tracking_card_no == 'RA260001'
    assert adapter.push_completion('RA260001', 9100, 98.9) is True
    assert calls[0]['params']['updated_after'] == '2026-05-16T08:00:00+00:00'
