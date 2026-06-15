from __future__ import annotations

from app.services import dingtalk_service
from app.services.dingtalk_templates import build_anomaly_alert, build_approval_notice, build_fill_reminder


def _configured_service(monkeypatch):
    service = dingtalk_service.DingTalkService()
    service.config = dingtalk_service.DingTalkConfig(
        corp_id='corp',
        app_key='app',
        app_secret='secret',
        agent_id='1001',
    )
    monkeypatch.setattr(dingtalk_service.settings, 'DINGTALK_ENABLED', True, raising=False)
    monkeypatch.setattr(dingtalk_service.settings, 'DINGTALK_NOTIFY_DRY_RUN', False, raising=False)
    return service


def test_exchange_code_uses_mocked_http_client(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    calls = []

    def fake_request_json(*, method, url, payload=None):
        calls.append((method, url, payload))
        if 'gettoken' in url:
            return {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200}
        return {'errcode': 0, 'result': {'userid': 'dt_100', 'unionid': 'union_100'}}

    monkeypatch.setattr(service, '_request_json', fake_request_json)

    identity = service.exchange_code('abc')

    assert identity == {'userid': 'dt_100', 'unionid': 'union_100'}
    assert calls[0][0] == 'GET'
    assert 'gettoken' in calls[0][1]
    assert calls[1][0] == 'POST'
    assert calls[1][2] == {'code': 'abc'}


def test_fetch_access_token_uses_cache(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    calls = []

    def fake_request_json(*, method, url, payload=None):
        calls.append((method, url, payload))
        return {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200}

    monkeypatch.setattr(service, '_request_json', fake_request_json)

    assert service.fetch_access_token() == 'access_token_1'
    assert service.fetch_access_token() == 'access_token_1'
    assert len(calls) == 1


def test_fetch_access_token_refreshes_after_expiry(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    now = {'value': 0.0}
    calls = []

    def fake_request_json(*, method, url, payload=None):
        calls.append((method, url, payload))
        return {'errcode': 0, 'access_token': f"access_token_{len(calls)}", 'expires_in': 1}

    monkeypatch.setattr(dingtalk_service.time, 'monotonic', lambda: now['value'])
    monkeypatch.setattr(service, '_request_json', fake_request_json)

    assert service.fetch_access_token() == 'access_token_1'
    now['value'] = 61.0
    assert service.fetch_access_token() == 'access_token_2'


def test_send_work_notification_calls_dingtalk_asyncsend(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    calls = []

    def fake_request_json(*, method, url, payload=None):
        calls.append((method, url, payload))
        if 'gettoken' in url:
            return {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200}
        return {'errcode': 0, 'task_id': 42}

    monkeypatch.setattr(service, '_request_json', fake_request_json)

    ok, detail = service.send_work_notification('dt_100', '日报内容')

    assert ok is True
    assert detail == 'dingtalk_sent'
    assert calls[1][0] == 'POST'
    assert 'corpconversation/asyncsend_v2' in calls[1][1]
    assert calls[1][2]['userid_list'] == 'dt_100'
    assert calls[1][2]['msg']['text']['content'] == '日报内容'


def test_send_work_notification_accepts_template_message(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    calls = []

    def fake_request_json(*, method, url, payload=None):
        calls.append((method, url, payload))
        if 'gettoken' in url:
            return {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200}
        return {'errcode': 0, 'task_id': 42}

    monkeypatch.setattr(service, '_request_json', fake_request_json)
    message = build_fill_reminder('张三', '白班', '12:00')

    ok, detail = service.send_work_notification('dt_100', message)

    assert ok is True
    assert detail == 'dingtalk_sent'
    assert calls[1][2]['msg'] == message


def test_send_work_notification_preserves_dingtalk_failure_payload(monkeypatch) -> None:
    service = _configured_service(monkeypatch)

    def fake_request_json(*, method, url, payload=None):
        if 'gettoken' in url:
            return {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200}
        return {
            'errcode': 33012,
            'errmsg': 'invalid userid',
            'request_id': 'work-req-failed-001',
            'task_id': 0,
        }

    monkeypatch.setattr(service, '_request_json', fake_request_json)

    ok, detail = service.send_work_notification('dt_100', '日报内容')

    assert ok is False
    assert detail == {
        'detail': 'invalid userid',
        'provider_message_id': '0',
        'response_payload': {
            'errcode': 33012,
            'errmsg': 'invalid userid',
            'request_id': 'work-req-failed-001',
            'task_id': 0,
        },
    }


def test_send_group_message_calls_dingtalk_chat_send(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    calls = []

    def fake_request_json(*, method, url, payload=None):
        calls.append((method, url, payload))
        if 'gettoken' in url:
            return {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200}
        return {'errcode': 0, 'messageId': 'ding-msg-001'}

    monkeypatch.setattr(service, '_request_json', fake_request_json)
    message = build_approval_notice(12, '李四', '通过')

    ok, detail = service.send_group_message('chat-1', message)

    assert ok is True
    assert detail == {
        'detail': 'dingtalk_sent',
        'provider_message_id': 'ding-msg-001',
        'response_payload': {'errcode': 0, 'messageId': 'ding-msg-001'},
    }
    assert 'chat/send' in calls[1][1]
    assert calls[1][2] == {'chatid': 'chat-1', 'msg': message}


def test_send_group_message_preserves_dingtalk_failure_payload(monkeypatch) -> None:
    service = _configured_service(monkeypatch)

    def fake_request_json(*, method, url, payload=None):
        if 'gettoken' in url:
            return {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200}
        return {
            'errcode': 310000,
            'errmsg': 'invalid robot code',
            'request_id': 'req-failed-001',
        }

    monkeypatch.setattr(service, '_request_json', fake_request_json)
    message = build_approval_notice(12, '李四', '通过')

    ok, detail = service.send_group_message('chat-1', message)

    assert ok is False
    assert detail == {
        'detail': 'invalid robot code',
        'provider_message_id': None,
        'response_payload': {
            'errcode': 310000,
            'errmsg': 'invalid robot code',
            'request_id': 'req-failed-001',
        },
    }


def test_dingtalk_message_templates() -> None:
    fill = build_fill_reminder('张三', '白班', '12:00')
    anomaly = build_anomaly_alert('冷轧', '成材率', 92.5, 95)
    approval = build_approval_notice(12, '李四', '通过')

    assert fill['msgtype'] == 'action_card'
    assert '张三' in fill['action_card']['markdown']
    assert anomaly['msgtype'] == 'action_card'
    assert '冷轧' in anomaly['action_card']['markdown']
    assert approval == {'msgtype': 'text', 'text': {'content': '报表 #12（李四提交）已通过'}}


def test_work_notification_rate_limit_waits_after_twenty_messages_per_second(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    now = {'value': 100.0}
    sleeps = []

    def fake_request_json(*, method, url, payload=None):
        if 'gettoken' in url:
            return {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200}
        return {'errcode': 0, 'task_id': 42}

    def fake_sleep(seconds):
        sleeps.append(seconds)
        now['value'] += seconds

    monkeypatch.setattr(dingtalk_service.time, 'monotonic', lambda: now['value'])
    monkeypatch.setattr(dingtalk_service.time, 'sleep', fake_sleep)
    monkeypatch.setattr(service, '_request_json', fake_request_json)

    for index in range(21):
        ok, _detail = service.send_work_notification(f'dt_{index}', '日报内容')
        assert ok is True

    assert sleeps
    assert sleeps[0] > 0


def test_send_work_notification_dry_run_skips_http(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    monkeypatch.setattr(dingtalk_service.settings, 'DINGTALK_NOTIFY_DRY_RUN', True, raising=False)
    monkeypatch.setattr(
        service,
        '_request_json',
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError('dry run should not call DingTalk')),
    )

    ok, detail = service.send_work_notification('dt_100', '日报内容')

    assert ok is True
    assert detail == 'dingtalk_dry_run'


def test_fetch_department_users_stops_when_dingtalk_has_more_string_is_false(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    calls = []

    def fake_request_json(*, method, url, payload=None):
        calls.append((method, url, payload))
        if 'gettoken' in url:
            return {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200}
        if len(calls) == 2:
            return {
                'errcode': 0,
                'result': {
                    'has_more': 'true',
                    'next_cursor': '100',
                    'list': [{'userid': 'dt_100', 'unionid': 'union_100', 'mobile': '13900001000'}],
                },
            }
        if len(calls) == 3:
            return {
                'errcode': 0,
                'result': {
                    'has_more': 'false',
                    'next_cursor': '200',
                    'list': [{'userid': 'dt_101', 'unionid': 'union_101', 'mobile': '13900001001'}],
                },
            }
        raise AssertionError('string false should stop pagination')

    monkeypatch.setattr(service, '_request_json', fake_request_json)

    rows = service.fetch_department_users(1)

    assert [row['userid'] for row in rows] == ['dt_100', 'dt_101']
    assert calls[1][2]['dept_id'] == 1
    assert calls[1][2]['cursor'] == 0
    assert calls[2][2]['cursor'] == '100'
