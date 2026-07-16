from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.config import settings
from app.core.business_time import resolve_yearless_business_date


@dataclass(frozen=True, slots=True)
class HermesDay1Command:
    source_text: str
    business_date: date
    report_type: str = 'daily_report'
    audience: str = 'root_owner'
    output_format: str = 'three_part'


@dataclass(frozen=True, slots=True)
class Day1ActorDecision:
    user: Any | None
    sender_user_id: str
    sender_union_id: str
    channel: str
    group_id: str
    conversation_key: str
    is_root_owner: bool
    is_allowed_dingtalk_user: bool
    is_authorized_group: bool
    is_allowed_day1_query: bool
    reason: str


class Day1CommandParseError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f'{code}:{message}')


def parse_day1_command(
    text: str,
    *,
    default_year: int | None,
    reference_date: date | None = None,
) -> HermesDay1Command | None:
    clean = str(text or '').strip()
    if not clean or '日报' not in clean:
        return None

    business_date = _extract_business_date(
        clean,
        default_year=default_year,
        reference_date=reference_date,
    )
    if business_date is None:
        return None

    return HermesDay1Command(source_text=clean, business_date=business_date)


def classify_day1_actor(
    user: Any | None,
    sender_user_id: str,
    sender_union_id: str,
    channel: str,
    group_id: str,
) -> Day1ActorDecision:
    clean_user_id = _clean(sender_user_id)
    clean_union_id = _clean(sender_union_id)
    clean_group_id = _clean(group_id)
    conversation_key = clean_group_id or f'user:{getattr(user, "id", "unknown")}'

    if not clean_user_id and not clean_union_id:
        return Day1ActorDecision(
            user=user,
            sender_user_id=clean_user_id,
            sender_union_id=clean_union_id,
            channel=_clean(channel),
            group_id=clean_group_id,
            conversation_key=conversation_key,
            is_root_owner=False,
            is_allowed_dingtalk_user=False,
            is_authorized_group=False,
            is_allowed_day1_query=False,
            reason='dingtalk_identity_required',
        )

    identity_values = {
        clean_user_id,
        clean_union_id,
        _clean(getattr(user, 'dingtalk_user_id', None)),
        _clean(getattr(user, 'dingtalk_union_id', None)),
    }
    identity_values.discard('')

    owner_ids = _configured_ids('HERMES_OWNER_DINGTALK_USER_IDS', 'hermes_owner_dingtalk_user_ids')
    allowed_ids = _configured_ids('HERMES_ALLOWED_DINGTALK_USER_IDS', 'hermes_allowed_dingtalk_user_ids')
    allowed_group_ids = _configured_ids('HERMES_ALLOWED_GROUP_IDS', 'hermes_allowed_group_ids')

    is_configured_root_owner = bool(owner_ids & identity_values)
    is_dev_name_fallback = (
        not is_configured_root_owner
        and not settings.is_production_like
        and _clean(getattr(user, 'name', None)) == '张兆嘉'
    )
    is_root_owner = is_configured_root_owner or is_dev_name_fallback
    is_allowed_dingtalk_user = bool(allowed_ids & identity_values)
    is_authorized_group = bool(clean_group_id and clean_group_id in allowed_group_ids)
    is_allowed_day1_query = is_root_owner or is_allowed_dingtalk_user or is_authorized_group

    if is_configured_root_owner:
        reason = 'root_owner'
    elif is_dev_name_fallback:
        reason = 'root_owner_dev_name_fallback'
    elif is_allowed_dingtalk_user:
        reason = 'allowed_dingtalk_user'
    elif is_authorized_group:
        reason = 'authorized_group'
    else:
        reason = 'user_not_allowed'

    return Day1ActorDecision(
        user=user,
        sender_user_id=clean_user_id,
        sender_union_id=clean_union_id,
        channel=_clean(channel),
        group_id=clean_group_id,
        conversation_key=conversation_key,
        is_root_owner=is_root_owner,
        is_allowed_dingtalk_user=is_allowed_dingtalk_user,
        is_authorized_group=is_authorized_group,
        is_allowed_day1_query=is_allowed_day1_query,
        reason=reason,
    )


def require_root_owner_for_day1_report(decision: Day1ActorDecision) -> None:
    if not decision.is_root_owner:
        raise PermissionError('owner_required')


def _extract_business_date(
    text: str,
    *,
    default_year: int | None,
    reference_date: date | None,
) -> date | None:
    iso_match = re.search(r'(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})', text)
    if iso_match:
        return _build_date(
            year=int(iso_match.group('year')),
            month=int(iso_match.group('month')),
            day=int(iso_match.group('day')),
            raw=iso_match.group(0),
        )

    full_chinese_match = re.search(
        r'(?P<year>20\d{2})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日',
        text,
    )
    if full_chinese_match:
        return _build_date(
            year=int(full_chinese_match.group('year')),
            month=int(full_chinese_match.group('month')),
            day=int(full_chinese_match.group('day')),
            raw=full_chinese_match.group(0),
        )

    chinese_match = re.search(r'(?P<month>\d{1,2})月(?P<day>\d{1,2})日', text)
    if chinese_match:
        month = int(chinese_match.group('month'))
        day = int(chinese_match.group('day'))
        if default_year is None:
            _build_date(year=2000, month=month, day=day, raw=chinese_match.group(0))
            raise Day1CommandParseError('missing_event_year', chinese_match.group(0))
        if reference_date is not None:
            try:
                return resolve_yearless_business_date(
                    month=month,
                    day=day,
                    reference_date=reference_date,
                )
            except ValueError as exc:
                raise Day1CommandParseError('invalid_date', chinese_match.group(0)) from exc
        return _build_date(
            year=default_year,
            month=month,
            day=day,
            raw=chinese_match.group(0),
        )

    return None


def _build_date(*, year: int, month: int, day: int, raw: str) -> date:
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise Day1CommandParseError('invalid_date', raw) from exc


def _configured_ids(env_name: str, property_name: str) -> set[str]:
    raw_env = os.getenv(env_name)
    if raw_env is not None:
        return _parse_csv(raw_env)
    value = getattr(settings, property_name)
    if isinstance(value, set):
        return {_clean(item) for item in value if _clean(item)}
    return _parse_csv(str(value or ''))


def _parse_csv(value: str | None) -> set[str]:
    return {item.strip() for item in str(value or '').split(',') if item.strip()}


def _clean(value: Any | None) -> str:
    return str(value or '').strip()
