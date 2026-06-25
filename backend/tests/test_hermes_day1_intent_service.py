from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services import hermes_day1_intent_service as day1


@pytest.fixture(autouse=True)
def _clear_day1_env(monkeypatch) -> None:
    for name in (
        'HERMES_OWNER_DINGTALK_USER_IDS',
        'HERMES_ALLOWED_DINGTALK_USER_IDS',
        'HERMES_ALLOWED_GROUP_IDS',
    ):
        monkeypatch.delenv(name, raising=False)


def _user(
    *,
    user_id: int = 1,
    name: str = '授权用户',
    dingtalk_user_id: str | None = 'dt-user',
    dingtalk_union_id: str | None = 'union-user',
):
    return SimpleNamespace(
        id=user_id,
        name=name,
        dingtalk_user_id=dingtalk_user_id,
        dingtalk_union_id=dingtalk_union_id,
        is_active=True,
    )


@pytest.mark.parametrize(
    ('text', 'expected_date'),
    [
        ('生成 6月19日 root_owner 完整版三段式日报', date(2026, 6, 19)),
        ('生成 6月19日正式日报', date(2026, 6, 19)),
        ('/日报 2026-06-19', date(2026, 6, 19)),
        ('生成 2026-06-19 日报', date(2026, 6, 19)),
    ],
)
def test_parse_day1_command_recognizes_report_requests(text: str, expected_date: date) -> None:
    command = day1.parse_day1_command(text, default_year=2026)

    assert command is not None
    assert command.business_date == expected_date
    assert command.report_type == 'daily_report'
    assert command.audience == 'root_owner'
    assert command.output_format == 'three_part'


def test_parse_day1_command_ignores_non_report_chat() -> None:
    assert day1.parse_day1_command('今天辛苦了', default_year=2026) is None


def test_parse_day1_command_rejects_invalid_chinese_date() -> None:
    with pytest.raises(day1.Day1CommandParseError) as exc_info:
        day1.parse_day1_command('生成 6月32日正式日报', default_year=2026)

    assert exc_info.value.code == 'invalid_date'
    assert '6月32日' in str(exc_info.value)


def test_classify_day1_actor_uses_configured_user_id_before_name(monkeypatch) -> None:
    monkeypatch.setattr(day1.settings, 'APP_ENV', 'production', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_DINGTALK_USER_IDS', '', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_GROUP_IDS', '', raising=False)

    decision = day1.classify_day1_actor(
        _user(name='不是张兆嘉', dingtalk_user_id='dt-root'),
        sender_user_id='dt-root',
        sender_union_id='',
        channel='dingtalk_private',
        group_id='',
    )

    assert decision.is_root_owner is True
    assert decision.is_allowed_day1_query is True
    assert decision.reason == 'root_owner'
    assert decision.conversation_key == 'user:1'


def test_classify_day1_actor_uses_configured_union_id(monkeypatch) -> None:
    monkeypatch.setattr(day1.settings, 'APP_ENV', 'production', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_OWNER_DINGTALK_USER_IDS', 'union-root', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_DINGTALK_USER_IDS', '', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_GROUP_IDS', '', raising=False)

    decision = day1.classify_day1_actor(
        _user(name='不是张兆嘉', dingtalk_user_id='dt-user', dingtalk_union_id='union-root'),
        sender_user_id='dt-user',
        sender_union_id='union-root',
        channel='dingtalk_private',
        group_id='',
    )

    assert decision.is_root_owner is True
    assert decision.reason == 'root_owner'


def test_classify_day1_actor_name_fallback_is_dev_only(monkeypatch) -> None:
    monkeypatch.setattr(day1.settings, 'HERMES_OWNER_DINGTALK_USER_IDS', '', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_DINGTALK_USER_IDS', '', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_GROUP_IDS', '', raising=False)

    monkeypatch.setattr(day1.settings, 'APP_ENV', 'development', raising=False)
    dev_decision = day1.classify_day1_actor(
        _user(name='张兆嘉', dingtalk_user_id='dt-local'),
        sender_user_id='dt-local',
        sender_union_id='',
        channel='dingtalk_private',
        group_id='',
    )
    assert dev_decision.is_root_owner is True
    assert dev_decision.reason == 'root_owner_dev_name_fallback'

    monkeypatch.setattr(day1.settings, 'APP_ENV', 'production', raising=False)
    prod_decision = day1.classify_day1_actor(
        _user(name='张兆嘉', dingtalk_user_id='dt-local'),
        sender_user_id='dt-local',
        sender_union_id='',
        channel='dingtalk_private',
        group_id='',
    )
    assert prod_decision.is_root_owner is False
    assert prod_decision.reason == 'user_not_allowed'


def test_allowed_dingtalk_user_can_query_but_cannot_run_root_owner_report(monkeypatch) -> None:
    monkeypatch.setattr(day1.settings, 'APP_ENV', 'production', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_DINGTALK_USER_IDS', 'dt-allowed', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_GROUP_IDS', '', raising=False)

    decision = day1.classify_day1_actor(
        _user(name='授权用户', dingtalk_user_id='dt-allowed'),
        sender_user_id='dt-allowed',
        sender_union_id='',
        channel='dingtalk_private',
        group_id='',
    )

    assert decision.is_root_owner is False
    assert decision.is_allowed_dingtalk_user is True
    assert decision.is_allowed_day1_query is True
    with pytest.raises(PermissionError, match='owner_required'):
        day1.require_root_owner_for_day1_report(decision)


def test_allowed_group_can_query_but_cannot_run_root_owner_report(monkeypatch) -> None:
    monkeypatch.setattr(day1.settings, 'APP_ENV', 'production', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_DINGTALK_USER_IDS', '', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_GROUP_IDS', 'cid-authorized', raising=False)

    decision = day1.classify_day1_actor(
        _user(name='群内普通用户', dingtalk_user_id='dt-group-user'),
        sender_user_id='dt-group-user',
        sender_union_id='',
        channel='dingtalk_group',
        group_id='cid-authorized',
    )

    assert decision.is_root_owner is False
    assert decision.is_authorized_group is True
    assert decision.is_allowed_day1_query is True
    assert decision.conversation_key == 'cid-authorized'
    with pytest.raises(PermissionError, match='owner_required'):
        day1.require_root_owner_for_day1_report(decision)


def test_classify_day1_actor_requires_dingtalk_identity(monkeypatch) -> None:
    monkeypatch.setattr(day1.settings, 'APP_ENV', 'production', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_DINGTALK_USER_IDS', '', raising=False)
    monkeypatch.setattr(day1.settings, 'HERMES_ALLOWED_GROUP_IDS', '', raising=False)

    decision = day1.classify_day1_actor(
        _user(name='张兆嘉', dingtalk_user_id='dt-root'),
        sender_user_id='',
        sender_union_id='',
        channel='dingtalk_private',
        group_id='',
    )

    assert decision.is_root_owner is False
    assert decision.is_allowed_day1_query is False
    assert decision.reason == 'dingtalk_identity_required'
