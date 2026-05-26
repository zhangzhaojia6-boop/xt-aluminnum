from __future__ import annotations

from datetime import datetime

import pytest

from app.adapters.mvc_mes_adapter import MvcMesAdapter


_UNSET = object()


class _Response:
    def __init__(self, *, payload=_UNSET, status_code=200, cookies=None, text='', headers=None):
        self._payload = payload
        self.status_code = status_code
        self.cookies = cookies or {}
        self.text = text
        self.headers = headers or {'content-type': 'application/json; charset=utf-8'}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'http_{self.status_code}')

    def json(self):
        if self._payload is _UNSET:
            raise ValueError('not json')
        return self._payload


def _sender_for(payloads, calls):
    queue = list(payloads)

    def sender(**kwargs):
        calls.append(kwargs)
        if not queue:
            raise AssertionError(f'unexpected request: {kwargs}')
        return queue.pop(0)

    return sender


def test_mvc_mes_adapter_logs_in_and_reads_dispatch_rows_from_settings_credentials():
    calls = []
    adapter = MvcMesAdapter(
        base_url='https://mes.example.com/',
        username='mes-user',
        password='mes-pass',
        sender=_sender_for(
            [
                _Response(text='<input name="__RequestVerificationToken" type="hidden" value="token-1" />', cookies={'csrf': 'one'}),
                _Response(payload={'status': True, 'message': '验证成功!'}, cookies={'sid': 'abc'}),
                _Response(payload={'status': True, 'message': '登录成功!'}),
                _Response(payload={'aaData': [{'name': 'dispatch'}]}),
                _Response(
                    payload={
                        'aaData': [
                            {
                                'BatchNumber': 'BN-2601',
                                'Id': 8842,
                                'CurrentWorkShop': '冷轧',
                                'CurrentProcess': '轧制',
                                'NextWorkShop': '退火',
                                'NextProcess': '退火',
                                'ProcessRoute': '铸轧-冷轧-退火',
                                'PrintProcessRoute': '铸轧 > 冷轧 > 退火',
                                'DelayHour': '2.5',
                                'StatusName': '生产中',
                                'MaterialCode': '3003-H24',
                            }
                        ],
                        'recordsTotal': 1,
                    }
                ),
            ],
            calls,
        ),
    )

    items = adapter.list_dispatch(limit=25)

    assert len(items) == 1
    assert items[0].coil_id == 'MES:8842'
    assert items[0].tracking_card_no == 'BN-2601'
    assert items[0].metadata['CurrentWorkShop'] == '冷轧'
    assert items[0].metadata['CurrentProcess'] == '轧制'
    assert items[0].metadata['NextWorkShop'] == '退火'
    assert items[0].metadata['NextProcess'] == '退火'
    assert items[0].metadata['ProcessRoute'] == '铸轧-冷轧-退火'
    assert items[0].metadata['PrintProcessRoute'] == '铸轧 > 冷轧 > 退火'
    assert items[0].metadata['DelayHour'] == 2.5
    assert items[0].metadata['StatusName'] == '生产中'
    assert items[0].metadata['MaterialCode'] == '3003-H24'

    assert [call['url'] for call in calls] == [
        'https://mes.example.com/Login/Index',
        'https://mes.example.com/Login/CheckLogin',
        'https://mes.example.com/Login/QueryLogin',
        'https://mes.example.com/Right/GetUserRightList',
        'https://mes.example.com/Dispatch/QueryList',
    ]
    assert calls[0]['method'] == 'GET'
    login_payload = calls[1]['data']
    assert login_payload['__RequestVerificationToken'] == 'token-1'
    assert login_payload['Account'] == 'mes-user'
    assert login_payload['Password'] == 'mes-pass'
    assert login_payload['MAC'] == ''
    assert login_payload['ktsn'] == ''
    assert calls[-1]['data']['length'] == 25
    assert calls[-1]['data']['__RequestVerificationToken'] == 'token-1'
    assert 'Password' not in calls[-1]['data']
    assert 'Account' not in calls[-1]['data']


def test_mvc_mes_adapter_matches_tracking_card_separator_variants():
    adapter = MvcMesAdapter(
        base_url='https://mes.example.com/',
        username='mes-user',
        password='mes-pass',
        sender=_sender_for(
            [
                _Response(text='<input name="__RequestVerificationToken" type="hidden" value="token-1" />'),
                _Response(payload={'status': True}),
                _Response(payload={'status': True}),
                _Response(payload={'data': []}),
                _Response(
                    payload={
                        'aaData': [
                            {
                                'BatchNumber': 'S-2-054-1',
                                'Product': {'Id': 9001},
                                'AlloyGrade': '3003',
                            }
                        ]
                    }
                ),
            ],
            [],
        ),
    )

    card_info = adapter.get_tracking_card_info('S一2一054一1')

    assert card_info is not None
    assert card_info.card_no == 'S-2-054-1'
    assert card_info.alloy_grade == '3003'


def test_mvc_mes_adapter_relogs_when_table_request_returns_login_page():
    calls = []
    login_page = '<input name="__RequestVerificationToken" type="hidden" value="token-2" />'
    adapter = MvcMesAdapter(
        base_url='https://mes.example.com',
        username='mes-user',
        password='mes-pass',
        sender=_sender_for(
            [
                _Response(text='<input name="__RequestVerificationToken" type="hidden" value="token-1" />', cookies={'csrf': 'one'}),
                _Response(payload={'status': True}, cookies={'sid': 'old'}),
                _Response(payload={'status': True}),
                _Response(payload={'data': []}),
                _Response(text=login_page, headers={'content-type': 'text/html; charset=utf-8'}),
                _Response(text=login_page, cookies={'csrf': 'two'}),
                _Response(payload={'status': True}, cookies={'sid': 'new'}),
                _Response(payload={'status': True}),
                _Response(payload={'data': []}),
                _Response(payload={'aaData': [{'BatchNumber': 'BN-2603', 'Product': {'Id': 9903}}]}),
            ],
            calls,
        ),
    )

    items = adapter.list_dispatch()

    assert len(items) == 1
    assert items[0].coil_id == 'MES:9903'
    assert [call['url'] for call in calls] == [
        'https://mes.example.com/Login/Index',
        'https://mes.example.com/Login/CheckLogin',
        'https://mes.example.com/Login/QueryLogin',
        'https://mes.example.com/Right/GetUserRightList',
        'https://mes.example.com/Dispatch/QueryList',
        'https://mes.example.com/Login/Index',
        'https://mes.example.com/Login/CheckLogin',
        'https://mes.example.com/Login/QueryLogin',
        'https://mes.example.com/Right/GetUserRightList',
        'https://mes.example.com/Dispatch/QueryList',
    ]
    assert calls[-1]['data']['__RequestVerificationToken'] == 'token-2'


def test_mvc_mes_adapter_reads_master_stock_and_wip_lists():
    calls = []
    adapter = MvcMesAdapter(
        base_url='https://mes.example.com',
        username='mes-user',
        password='mes-pass',
        sender=_sender_for(
            [
                _Response(text='<input name="__RequestVerificationToken" type="hidden" value="token-1" />'),
                _Response(payload={'status': True}),
                _Response(payload={'status': True}),
                _Response(payload={'data': []}),
                _Response(payload={'data': [{'Id': 1, 'Name': '冷轧'}]}),
                _Response(payload={'data': [{'Id': 2, 'Name': '1#轧机', 'WorkShop': '冷轧'}]}),
                _Response(payload={'data': [{'BatchNumber': 'BN-2602', 'Product': {'Id': 9901}, 'Weight': '12.4'}]}),
                _Response(payload={'data': [{'WorkShopName': '冷轧', 'DoingCount': 8, 'DoingWeight': '24.6'}]}),
            ],
            calls,
        ),
    )

    crafts = adapter.list_crafts()
    devices = adapter.list_devices()
    stock = adapter.list_stock()
    wip = adapter.list_wip_totals()

    assert crafts[0].source_id == '1'
    assert crafts[0].name == '冷轧'
    assert devices[0].source_id == '2'
    assert devices[0].name == '1#轧机'
    assert devices[0].workshop_name == '冷轧'
    assert stock[0].coil_key == 'MES:9901'
    assert stock[0].tracking_card_no == 'BN-2602'
    assert stock[0].weight == 12.4
    assert wip[0].workshop_name == '冷轧'
    assert wip[0].doing_count == 8
    assert wip[0].doing_weight == 24.6
    assert calls[-4]['url'].endswith('/Craft/GetList')
    assert calls[-3]['url'].endswith('/Device/GetList')
    assert calls[-2]['url'].endswith('/Stock/GetList')
    assert calls[-1]['url'].endswith('/Dispatch/DoingReportTotal')


def test_mvc_mes_adapter_returns_empty_lists_for_empty_data():
    calls = []
    adapter = MvcMesAdapter(
        base_url='https://mes.example.com',
        username='mes-user',
        password='mes-pass',
        sender=_sender_for(
            [
                _Response(text='<input name="__RequestVerificationToken" type="hidden" value="token-1" />'),
                _Response(payload={'status': True}),
                _Response(payload={'status': True}),
                _Response(payload={'data': []}),
                _Response(payload={'data': []}),
            ],
            calls,
        ),
    )

    assert adapter.list_dispatch() == []


def test_mvc_mes_adapter_raises_on_login_failure():
    adapter = MvcMesAdapter(
        base_url='https://mes.example.com',
        username='mes-user',
        password='bad-pass',
        sender=_sender_for(
            [
                _Response(text='<input name="__RequestVerificationToken" type="hidden" value="token-1" />'),
                _Response(payload={'status': False, 'message': 'bad credentials'}),
            ],
            [],
        ),
    )

    with pytest.raises(RuntimeError, match='MES MVC login failed'):
        adapter.list_dispatch()


def test_mvc_mes_adapter_writeback_is_disabled():
    adapter = MvcMesAdapter(
        base_url='https://mes.example.com',
        username='mes-user',
        password='mes-pass',
        sender=lambda **kwargs: _Response(payload={'success': True}),
    )

    assert adapter.push_completion('BN-2601', 10.5, 98.0) is False


def _logged_in_adapter(rows: list[dict], calls: list) -> MvcMesAdapter:
    return MvcMesAdapter(
        base_url='https://mes.example.com',
        username='mes-user',
        password='mes-pass',
        sender=_sender_for(
            [
                _Response(text='<input name="__RequestVerificationToken" type="hidden" value="t" />', cookies={'csrf': 'c'}),
                _Response(payload={'status': True, 'message': '验证成功!'}, cookies={'sid': 'a'}),
                _Response(payload={'status': True, 'message': '登录成功!'}),
                _Response(payload={'aaData': [{'name': 'dispatch'}]}),
                _Response(payload={'aaData': rows, 'recordsTotal': len(rows)}),
            ],
            calls,
        ),
    )


def test_mvc_mes_adapter_resolves_event_time_from_str_create_date():
    rows = [
        {
            'BatchNumber': '26RA04358',
            'Id': 1,
            'CurrentWorkShop': '2050车间',
            'CurrentProcess': '冷轧',
            'StatusName': '生产中',
            'StrCreateDate': '2026-05-26 11:01',
        }
    ]
    items = _logged_in_adapter(rows, []).list_dispatch(limit=10)
    assert items[0].event_time == datetime(2026, 5, 26, 11, 1)
    assert items[0].updated_at == datetime(2026, 5, 26, 11, 1)


def test_mvc_mes_adapter_resolves_event_time_from_dotnet_date_string():
    rows = [
        {
            'BatchNumber': 'B-1',
            'Id': 2,
            'CurrentWorkShop': 'WS',
            'StatusName': '在库',
            'CreateDate': '/Date(1779764483310)/',
        }
    ]
    items = _logged_in_adapter(rows, []).list_dispatch(limit=10)
    assert items[0].event_time is not None
    assert items[0].event_time.year == 2026


def test_mvc_mes_adapter_prefers_str_feeding_date_over_str_create_date():
    rows = [
        {
            'BatchNumber': 'B-2',
            'Id': 3,
            'CurrentWorkShop': 'WS',
            'StatusName': '生产中',
            'StrCreateDate': '2026-05-26 11:01',
            'StrFeedingDate': '2026-05-26 14:30:00',
        }
    ]
    items = _logged_in_adapter(rows, []).list_dispatch(limit=10)
    assert items[0].event_time == datetime(2026, 5, 26, 14, 30, 0)


def test_mvc_mes_adapter_event_time_is_none_when_no_date_fields_present():
    rows = [
        {
            'BatchNumber': 'B-3',
            'Id': 4,
            'CurrentWorkShop': 'WS',
            'StatusName': '生产中',
        }
    ]
    items = _logged_in_adapter(rows, []).list_dispatch(limit=10)
    assert items[0].event_time is None
    assert items[0].updated_at is None
