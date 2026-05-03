from __future__ import annotations

from app.services import dingtalk_service


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
