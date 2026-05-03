from __future__ import annotations

from datetime import datetime

import pytest

from app.adapters.mvc_mes_adapter import MvcMesAdapter


class _Response:
    def __init__(self, *, payload=None, status_code=200, cookies=None, text=''):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.cookies = cookies or {}
        self.text = text
        self.headers = {'content-type': 'application/json; charset=utf-8'}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'http_{self.status_code}')

    def json(self):
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
