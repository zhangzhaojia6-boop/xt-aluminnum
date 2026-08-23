from __future__ import annotations

import logging

import pytest

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


def test_download_robot_message_file_reuses_access_token_and_sends_download_request(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    monkeypatch.setattr(dingtalk_service.settings, 'DINGTALK_ROBOT_CODE', 'robot-default', raising=False)
    token_calls = []
    download_calls = []

    def fake_request_json(*, method, url, payload=None):
        token_calls.append((method, url, payload))
        return {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200}

    def fake_request_json_with_headers(*, method, url, payload=None, headers=None, timeout=20):
        download_calls.append((method, url, payload, headers, timeout))
        return {'downloadUrl': 'https://static.dingtalk.com/file-1.xlsx?signature=secret'}

    monkeypatch.setattr(service, '_request_json', fake_request_json)
    monkeypatch.setattr(service, '_request_json_with_headers', fake_request_json_with_headers)
    monkeypatch.setattr(
        service,
        '_request_bytes',
        lambda **_kwargs: (b'first-file', 'application/vnd.ms-excel'),
    )

    first = service.download_robot_message_file(download_code='code-1')
    second = service.download_robot_message_file(download_code='code-2')

    assert len(token_calls) == 1
    assert download_calls == [
        (
            'POST',
            'https://api.dingtalk.com/v1.0/robot/messageFiles/download',
            {'downloadCode': 'code-1', 'robotCode': 'robot-default'},
            {'x-acs-dingtalk-access-token': 'access_token_1'},
            20,
        ),
        (
            'POST',
            'https://api.dingtalk.com/v1.0/robot/messageFiles/download',
            {'downloadCode': 'code-2', 'robotCode': 'robot-default'},
            {'x-acs-dingtalk-access-token': 'access_token_1'},
            20,
        ),
    ]
    assert first.download_url_host == 'static.dingtalk.com'
    assert second.content == b'first-file'


def test_download_robot_message_file_fetches_bytes_from_returned_url(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    monkeypatch.setattr(dingtalk_service.settings, 'DINGTALK_ROBOT_CODE', 'robot-default', raising=False)
    calls = []

    monkeypatch.setattr(
        service,
        '_request_json',
        lambda **_kwargs: {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200},
    )
    monkeypatch.setattr(
        service,
        '_request_json_with_headers',
        lambda **_kwargs: {'downloadUrl': 'https://files.dingtalk.com/archive/report.csv?signature=secret'},
    )

    def fake_request_bytes(*, url, headers=None, timeout=20):
        calls.append((url, headers, timeout))
        return b'col1,col2\n1,2\n', 'text/csv'

    monkeypatch.setattr(service, '_request_bytes', fake_request_bytes)

    result = service.download_robot_message_file(download_code='code-1', robot_code='robot-1')

    assert calls == [('https://files.dingtalk.com/archive/report.csv?signature=secret', None, 20)]
    assert result == dingtalk_service.DingTalkDownloadedFile(
        download_url_host='files.dingtalk.com',
        content=b'col1,col2\n1,2\n',
        content_type='text/csv',
        size=14,
    )


def test_download_robot_message_file_redacts_signed_url_in_error_and_logs_host_only(monkeypatch, caplog) -> None:
    service = _configured_service(monkeypatch)
    monkeypatch.setattr(dingtalk_service.settings, 'DINGTALK_ROBOT_CODE', 'robot-default', raising=False)
    signed_url = 'https://files.dingtalk.com/archive/report.csv?signature=secret&token=signed'

    monkeypatch.setattr(
        service,
        '_request_json',
        lambda **_kwargs: {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200},
    )
    monkeypatch.setattr(
        service,
        '_request_json_with_headers',
        lambda **_kwargs: {'downloadUrl': signed_url},
    )

    def fake_request_bytes(*, url, headers=None, timeout=20):
        raise RuntimeError(f'failed to fetch {url}')

    monkeypatch.setattr(service, '_request_bytes', fake_request_bytes)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(dingtalk_service.DingTalkFileDownloadError) as excinfo:
            service.download_robot_message_file(download_code='code-1')

    assert str(excinfo.value) == 'dingtalk_file_download_fetch_failed host=files.dingtalk.com'
    assert signed_url not in str(excinfo.value)
    assert 'host=files.dingtalk.com' in caplog.text
    assert signed_url not in caplog.text


def test_download_robot_message_file_missing_download_url_raises(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    monkeypatch.setattr(dingtalk_service.settings, 'DINGTALK_ROBOT_CODE', 'robot-default', raising=False)
    monkeypatch.setattr(
        service,
        '_request_json',
        lambda **_kwargs: {'errcode': 0, 'access_token': 'access_token_1', 'expires_in': 7200},
    )
    monkeypatch.setattr(service, '_request_json_with_headers', lambda **_kwargs: {'requestId': 'req-1'})
    monkeypatch.setattr(
        service,
        '_request_bytes',
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError('missing downloadUrl should stop before fetch')),
    )

    with pytest.raises(
        dingtalk_service.DingTalkFileDownloadError,
        match='dingtalk_file_download_missing_url',
    ):
        service.download_robot_message_file(download_code='code-1')


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


def test_send_robot_direct_message_uses_openapi_oto_endpoint(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    calls = []
    monkeypatch.setattr(dingtalk_service.settings, 'DINGTALK_ROBOT_CODE', 'robot-code-1', raising=False)
    monkeypatch.setattr(service, 'fetch_access_token', lambda: 'access-token-1')

    def fake_request(*, method, url, payload=None, headers=None, timeout=30):
        calls.append((method, url, payload, headers))
        return {'processQueryKey': 'query-1'}

    monkeypatch.setattr(service, '_request_json_with_headers', fake_request)
    message = {'msgtype': 'markdown', 'markdown': {'title': '日报', 'text': '日报内容'}}

    ok, detail = service.send_robot_direct_message('dt_100', message)

    assert ok is True
    assert detail['detail'] == 'dingtalk_robot_direct_sent'
    assert calls == [
        (
            'POST',
            'https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend',
            {
                'robotCode': 'robot-code-1',
                'userIds': ['dt_100'],
                'msgKey': 'sampleMarkdown',
                'msgParam': '{"title": "日报", "text": "日报内容"}',
            },
            {'x-acs-dingtalk-access-token': 'access-token-1'},
        )
    ]


def test_send_user_message_falls_back_to_work_notice(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    monkeypatch.setattr(service, 'send_robot_direct_message', lambda *_args: (False, 'direct-denied'))
    monkeypatch.setattr(service, 'send_work_notification', lambda *_args: (True, 'work-sent'))

    ok, detail = service.send_user_message('dt_100', {'msgtype': 'text', 'text': {'content': '补录'}})

    assert ok is True
    assert detail['detail'] == 'dingtalk_work_notice_fallback_sent'
    assert detail['response_payload'] == {
        'direct_delivery': 'direct-denied',
        'fallback_delivery': 'work-sent',
    }


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


def test_signed_robot_webhook_appends_timestamp_and_sign_without_mutating_webhook() -> None:
    signed = dingtalk_service._signed_robot_webhook(
        'https://oapi.dingtalk.com/robot/send?access_token=token-1',
        'SEC-test-secret',
        now_ms=1234567890,
    )

    assert signed.startswith('https://oapi.dingtalk.com/robot/send?access_token=token-1&timestamp=1234567890&sign=')
    assert 'SEC-test-secret' not in signed


def test_send_custom_robot_message_resolves_webhook_and_secret_refs(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    calls = []
    monkeypatch.setenv('DINGTALK_ROBOT_TEST_WEBHOOK', 'https://oapi.dingtalk.com/robot/send?access_token=token-1')
    monkeypatch.setenv('DINGTALK_ROBOT_TEST_SECRET', 'SEC-test-secret')

    def fake_request_json(*, method, url, payload=None):
        calls.append((method, url, payload))
        return {'errcode': 0, 'errmsg': 'ok'}

    monkeypatch.setattr(service, '_request_json', fake_request_json)

    ok, detail = service.send_custom_robot_message(
        'DINGTALK_ROBOT_TEST_WEBHOOK',
        {'msgtype': 'markdown', 'markdown': {'title': '测试', 'text': '测试内容'}},
        secret_ref='DINGTALK_ROBOT_TEST_SECRET',
    )

    assert ok is True
    assert detail['detail'] == 'dingtalk_custom_robot_sent'
    assert calls[0][0] == 'POST'
    assert 'access_token=token-1' in calls[0][1]
    assert 'timestamp=' in calls[0][1]
    assert 'sign=' in calls[0][1]
    assert 'SEC-test-secret' not in calls[0][1]
    assert calls[0][2]['markdown']['title'] == '测试'


def test_send_custom_robot_message_dry_run_skips_http(monkeypatch) -> None:
    service = _configured_service(monkeypatch)
    monkeypatch.setenv('DINGTALK_ROBOT_TEST_WEBHOOK', 'https://oapi.dingtalk.com/robot/send?access_token=token-1')
    monkeypatch.setenv('DINGTALK_ROBOT_TEST_SECRET', 'SEC-test-secret')
    monkeypatch.setattr(dingtalk_service.settings, 'DINGTALK_NOTIFY_DRY_RUN', True, raising=False)
    monkeypatch.setattr(
        service,
        '_request_json',
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError('dry run should not call DingTalk')),
    )

    ok, detail = service.send_custom_robot_message(
        'DINGTALK_ROBOT_TEST_WEBHOOK',
        {'msgtype': 'text', 'text': {'content': '测试'}},
        secret_ref='DINGTALK_ROBOT_TEST_SECRET',
    )

    assert ok is True
    assert detail == 'dingtalk_dry_run'


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
