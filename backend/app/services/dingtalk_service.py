from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import time
from urllib import parse, request

from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.auth import create_access_token
from app.database import get_sessionmaker
from app.core.scope import build_scope_summary, scope_to_dict
from app.models.attendance import AttendanceClockRecord
from app.models.master import Employee
from app.models.system import User


logger = logging.getLogger(__name__)

_MESSAGE_RATE_LIMIT = 20
_MESSAGE_RATE_WINDOW_SECONDS = 1.0


@dataclass(slots=True)
class DingTalkConfig:
    corp_id: str | None
    app_key: str | None
    app_secret: str | None
    agent_id: str | None


class DingTalkNotConfigured(RuntimeError):
    pass


class DingTalkCodeInvalid(RuntimeError):
    pass


class DingTalkUserNotBound(RuntimeError):
    def __init__(self, dingtalk_user_id: str, dingtalk_union_id: str | None = None) -> None:
        self.dingtalk_user_id = dingtalk_user_id
        self.dingtalk_union_id = dingtalk_union_id
        super().__init__('dingtalk_user_not_bound')


class DingTalkUserAmbiguous(RuntimeError):
    def __init__(self, dingtalk_user_id: str, dingtalk_union_id: str | None = None) -> None:
        self.dingtalk_user_id = dingtalk_user_id
        self.dingtalk_union_id = dingtalk_union_id
        super().__init__('dingtalk_user_ambiguous')


def _active_users_by_dingtalk_field(db, column, value: str) -> list[User]:
    query = db.query(User).filter(column == value, User.is_active.is_(True))
    if hasattr(query, 'limit'):
        return list(query.limit(2).all())
    return list(query.all())


def resolve_unique_dingtalk_user(
    db,
    *,
    dingtalk_user_id: str | None,
    dingtalk_union_id: str | None = None,
) -> User | None:
    user_id = str(dingtalk_user_id or '').strip()
    union_id = str(dingtalk_union_id or '').strip() or None
    matches: dict[int, User] = {}

    if user_id:
        for user in _active_users_by_dingtalk_field(db, User.dingtalk_user_id, user_id):
            matches[int(user.id)] = user
    if union_id:
        for user in _active_users_by_dingtalk_field(db, User.dingtalk_union_id, union_id):
            matches[int(user.id)] = user

    if len(matches) > 1:
        raise DingTalkUserAmbiguous(user_id, union_id)
    if not matches:
        return None

    user = next(iter(matches.values()))
    if user_id and user.dingtalk_user_id and user.dingtalk_user_id != user_id:
        raise DingTalkUserAmbiguous(user_id, union_id)
    if union_id and user.dingtalk_union_id and user.dingtalk_union_id != union_id:
        raise DingTalkUserAmbiguous(user_id, union_id)
    return user


def has_dingtalk_binding_conflict(
    db,
    *,
    dingtalk_user_id: str | None,
    dingtalk_union_id: str | None = None,
    target_user_id: int | None = None,
) -> bool:
    values = (
        (User.dingtalk_user_id, str(dingtalk_user_id or '').strip()),
        (User.dingtalk_union_id, str(dingtalk_union_id or '').strip()),
    )
    for column, value in values:
        if not value:
            continue
        query = db.query(User).filter(column == value)
        if target_user_id is not None:
            query = query.filter(User.id != target_user_id)
        if query.first() is not None:
            return True
    return False


def ensure_dingtalk_binding_available(
    db,
    user: User,
    *,
    dingtalk_user_id: str | None,
    dingtalk_union_id: str | None = None,
) -> None:
    user_id = str(dingtalk_user_id or '').strip()
    union_id = str(dingtalk_union_id or '').strip() or None
    if user_id and user.dingtalk_user_id and user.dingtalk_user_id != user_id:
        raise DingTalkUserAmbiguous(user_id, union_id)
    if union_id and user.dingtalk_union_id and user.dingtalk_union_id != union_id:
        raise DingTalkUserAmbiguous(user_id, union_id)
    if has_dingtalk_binding_conflict(
        db,
        dingtalk_user_id=user_id,
        dingtalk_union_id=union_id,
        target_user_id=int(user.id),
    ):
        raise DingTalkUserAmbiguous(user_id, union_id)


class DingTalkService:
    """Placeholder for future DingTalk integration.

    The current round keeps file import as the data bridge, while reserving
    the entry structure needed by a DingTalk H5 micro app.
    """

    def __init__(self) -> None:
        self.config = DingTalkConfig(
            corp_id=settings.DINGTALK_CORP_ID,
            app_key=settings.DINGTALK_APP_KEY,
            app_secret=settings.DINGTALK_APP_SECRET,
            agent_id=settings.DINGTALK_AGENT_ID,
        )
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        self._message_send_times: deque[float] = deque()

    @property
    def enabled(self) -> bool:
        return bool(
            settings.DINGTALK_ENABLED
            and self.config.corp_id
            and self.config.app_key
            and self.config.app_secret
            and self.config.agent_id
        )

    def is_h5_configured(self) -> bool:
        return bool(self.config.corp_id and self.config.app_key and self.config.app_secret)

    def resolve_mobile_identity(self, user: User | None) -> dict[str, str | bool | None]:
        has_user_binding = bool(user and (user.dingtalk_user_id or user.dingtalk_union_id))
        if self.enabled and has_user_binding:
            return {
                'entry_channel': 'dingtalk_h5',
                'dingtalk_ready': True,
                'dingtalk_hint': '已预留钉钉身份，可继续接入免登与工作台入口。',
                'current_identity_source': 'dingtalk_binding',
            }
        if has_user_binding:
            return {
                'entry_channel': 'web_debug',
                'dingtalk_ready': False,
                'dingtalk_hint': '已绑定钉钉身份，但当前环境仍以网页入口调试为主。',
                'current_identity_source': 'dingtalk_binding',
            }
        return {
            'entry_channel': 'web_debug',
            'dingtalk_ready': False,
            'dingtalk_hint': '当前使用网页调试入口，后续可切换到钉钉工作台 H5 入口。',
            'current_identity_source': 'dev_fallback',
        }

    def build_mobile_entry(self, path: str = '/mobile') -> dict[str, str | bool | None]:
        return {
            'path': path,
            'enabled': self.enabled,
            'agent_id': self.config.agent_id,
            'corp_id': self.config.corp_id,
            'mode': 'dingtalk_h5' if self.enabled else 'web_debug',
        }

    def resolve_auth_code(self, auth_code: str | None) -> dict[str, str | bool | None]:
        if not auth_code:
            return {'resolved': False, 'message': 'auth code missing'}
        if not self.enabled:
            return {'resolved': False, 'message': 'dingtalk pre-integration only, env not fully configured'}
        return {
            'resolved': True,
            'identity_source': 'dingtalk_auth_code_reserved',
            'message': 'auth code flow reserved for future integration',
        }

    def build_mobile_bootstrap(self, user: User) -> dict:
        identity = self.resolve_mobile_identity(user)
        return {
            'entry_mode': 'dingtalk_h5' if self.enabled else 'web_debug',
            'dingtalk_enabled': self.enabled,
            'user_has_dingtalk_binding': bool(user.dingtalk_user_id or user.dingtalk_union_id),
            'current_identity_source': identity.get('current_identity_source', 'dev_fallback'),
            'current_scope_summary': scope_to_dict(build_scope_summary(user)),
        }

    def fetch_attendance_schedules(self, start_date: str, end_date: str) -> list[dict]:
        return []

    def _request_json(self, *, method: str, url: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        req = request.Request(
            url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            method=method.upper(),
        )
        with request.urlopen(req, timeout=20) as response:  # noqa: S310
            charset = response.headers.get_content_charset('utf-8')
            raw = response.read().decode(charset)
        return json.loads(raw or '{}')

    @staticmethod
    def _ensure_success(payload: dict) -> None:
        errcode = payload.get('errcode')
        code = payload.get('code')
        if errcode not in {None, 0, '0'}:
            raise RuntimeError(str(payload.get('errmsg') or payload))
        if code not in {None, 0, '0'}:
            raise RuntimeError(str(payload.get('message') or payload))

    def fetch_access_token(self) -> str:
        if not (self.config.app_key and self.config.app_secret):
            raise DingTalkNotConfigured('dingtalk_not_configured')

        now = time.monotonic()
        if self._access_token and self._access_token_expires_at > now:
            return self._access_token

        query = parse.urlencode(
            {
                'appkey': self.config.app_key or '',
                'appsecret': self.config.app_secret or '',
            }
        )
        payload = self._request_json(method='GET', url=f'https://oapi.dingtalk.com/gettoken?{query}')
        try:
            self._ensure_success(payload)
        except RuntimeError as exc:
            raise DingTalkCodeInvalid(str(exc)) from exc

        access_token = payload.get('access_token') or payload.get('accessToken')
        if not access_token:
            raise DingTalkCodeInvalid(str(payload.get('errmsg') or payload.get('message') or 'dingtalk_code_invalid'))
        expires_in = int(payload.get('expires_in') or payload.get('expiresIn') or 7200)
        self._access_token = str(access_token)
        self._access_token_expires_at = now + max(expires_in - 300, 60)
        return self._access_token

    def exchange_code(self, code: str) -> dict[str, str]:
        if not self.is_h5_configured():
            raise DingTalkNotConfigured('dingtalk_not_configured')
        auth_code = str(code or '').strip()
        if not auth_code:
            raise DingTalkCodeInvalid('dingtalk_code_invalid')

        access_token = self.fetch_access_token()
        try:
            payload = self._request_json(
                method='POST',
                url=f'https://oapi.dingtalk.com/topapi/v2/user/getuserinfo?access_token={parse.quote(access_token)}',
                payload={'code': auth_code},
            )
            self._ensure_success(payload)
        except Exception as exc:  # noqa: BLE001
            raise DingTalkCodeInvalid(str(exc)) from exc

        result = payload.get('result') if isinstance(payload.get('result'), dict) else payload
        userid = str(result.get('userid') or result.get('userId') or result.get('user_id') or '').strip()
        unionid = str(result.get('unionid') or result.get('unionId') or result.get('union_id') or '').strip()
        if not userid:
            raise DingTalkCodeInvalid('dingtalk_code_invalid')
        return {'userid': userid, 'unionid': unionid}

    def issue_jwt_for_dingtalk_user(
        self,
        db,
        dingtalk_user_id: str,
        dingtalk_union_id: str | None = None,
    ) -> tuple[User, str]:
        user_id = str(dingtalk_user_id or '').strip()
        union_id = str(dingtalk_union_id or '').strip() or None
        if not user_id:
            raise DingTalkUserNotBound(user_id, union_id)

        user = resolve_unique_dingtalk_user(
            db,
            dingtalk_user_id=user_id,
            dingtalk_union_id=union_id,
        )
        if user is None:
            raise DingTalkUserNotBound(user_id, union_id)

        ensure_dingtalk_binding_available(
            db,
            user,
            dingtalk_user_id=user_id,
            dingtalk_union_id=union_id,
        )
        if user_id and not user.dingtalk_user_id:
            user.dingtalk_user_id = user_id
        if union_id and not user.dingtalk_union_id:
            user.dingtalk_union_id = union_id
        user.last_login = datetime.now(timezone.utc)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise DingTalkUserAmbiguous(user_id, union_id) from exc
        db.refresh(user)
        return user, create_access_token(subject=str(user.id))

    def _get_access_token(self) -> str:
        if not self.enabled:
            raise RuntimeError('DingTalk is not configured')
        return self.fetch_access_token()

    @staticmethod
    def _build_message(content: str | dict) -> dict:
        if isinstance(content, dict):
            return content
        return {
            'msgtype': 'text',
            'text': {'content': str(content or '')},
        }

    def _throttle_message_send(self) -> None:
        now = time.monotonic()
        cutoff = now - _MESSAGE_RATE_WINDOW_SECONDS
        while self._message_send_times and self._message_send_times[0] <= cutoff:
            self._message_send_times.popleft()
        if len(self._message_send_times) >= _MESSAGE_RATE_LIMIT:
            wait_seconds = self._message_send_times[0] + _MESSAGE_RATE_WINDOW_SECONDS - now
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            now = time.monotonic()
            cutoff = now - _MESSAGE_RATE_WINDOW_SECONDS
            while self._message_send_times and self._message_send_times[0] <= cutoff:
                self._message_send_times.popleft()
        self._message_send_times.append(now)

    def _load_bound_dingtalk_user_ids(self) -> list[str]:
        sessionmaker = get_sessionmaker()
        db = sessionmaker()
        try:
            rows = (
                db.query(Employee.dingtalk_user_id)
                .filter(
                    Employee.is_active.is_(True),
                    Employee.dingtalk_user_id.is_not(None),
                )
                .all()
            )
            return [str(row.dingtalk_user_id).strip() for row in rows if getattr(row, 'dingtalk_user_id', None)]
        finally:
            db.close()

    @staticmethod
    def _normalize_date_range(start_date: str, end_date: str) -> tuple[str, str]:
        start_value = str(start_date).strip()
        end_value = str(end_date).strip()
        if ' ' not in start_value:
            start_value = f'{start_value} 00:00:00'
        if ' ' not in end_value:
            end_value = f'{end_value} 23:59:59'
        return start_value, end_value

    @staticmethod
    def _chunked(values: list[str], size: int) -> list[list[str]]:
        return [values[index : index + size] for index in range(0, len(values), size)]

    @staticmethod
    def _extract_rows(payload: dict) -> tuple[list[dict], bool]:
        if not isinstance(payload, dict):
            return [], False
        if payload.get('errcode') not in {None, 0}:
            raise RuntimeError(str(payload.get('errmsg') or payload))
        if payload.get('code') not in {None, 0, '0'}:
            raise RuntimeError(str(payload.get('message') or payload))

        result = payload.get('result')
        rows = payload.get('recordresult')
        has_more = bool(payload.get('hasMore'))
        if isinstance(result, dict):
            rows = rows or result.get('recordresult') or result.get('records') or result.get('list')
            has_more = has_more or bool(result.get('hasMore'))
        elif isinstance(result, list):
            rows = rows or result
        if not isinstance(rows, list):
            return [], has_more
        return [item for item in rows if isinstance(item, dict)], has_more

    @staticmethod
    def _normalize_clock_time(value) -> str | None:
        if value in {None, ''}:
            return None
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        if isinstance(value, str):
            return value
        return None

    def fetch_clock_records(self, start_date: str, end_date: str) -> list[dict]:
        if not self.enabled:
            return []

        user_ids = self._load_bound_dingtalk_user_ids()
        if not user_ids:
            return []

        access_token = self._get_access_token()
        start_value, end_value = self._normalize_date_range(start_date, end_date)
        collected: list[dict] = []
        seen_ids: set[str] = set()

        for user_chunk in self._chunked(user_ids, 50):
            offset = 0
            while True:
                payload = {
                    'userIds': user_chunk,
                    'checkDateFrom': start_value,
                    'checkDateTo': end_value,
                    'offset': offset,
                    'limit': 50,
                    'isI18n': False,
                }
                response = self._request_json(
                    method='POST',
                    url=f'https://oapi.dingtalk.com/attendance/listRecord?access_token={parse.quote(access_token)}',
                    payload=payload,
                )
                rows, has_more = self._extract_rows(response)
                for row in rows:
                    dingtalk_id = str(row.get('recordId') or row.get('record_id') or row.get('id') or '').strip()
                    if not dingtalk_id or dingtalk_id in seen_ids:
                        continue
                    seen_ids.add(dingtalk_id)
                    collected.append(
                        {
                            'dingtalk_id': dingtalk_id,
                            'dingtalk_user_id': row.get('userId') or row.get('userid') or row.get('user_id'),
                            'clock_type': row.get('checkType') or row.get('check_type') or row.get('clock_type'),
                            'clock_time': self._normalize_clock_time(
                                row.get('userCheckTime')
                                or row.get('checkTime')
                                or row.get('baseCheckTime')
                                or row.get('clockTime')
                                or row.get('gmtCreate')
                            ),
                            'raw_data': row,
                        }
                    )
                if not has_more or not rows:
                    break
                offset += len(rows)
        return collected

    def fetch_department_users(self, department_id: int = 1) -> list[dict]:
        if not self.enabled:
            raise DingTalkNotConfigured('dingtalk_not_configured')

        access_token = self.fetch_access_token()
        cursor: int | str = 0
        collected: list[dict] = []

        while True:
            payload = {
                'dept_id': int(department_id),
                'cursor': cursor,
                'size': 100,
                'contain_access_limit': False,
                'language': 'zh_CN',
            }
            response = self._request_json(
                method='POST',
                url=f'https://oapi.dingtalk.com/topapi/v2/user/list?access_token={parse.quote(access_token)}',
                payload=payload,
            )
            self._ensure_success(response)

            result = response.get('result') if isinstance(response.get('result'), dict) else {}
            rows = result.get('list') if isinstance(result, dict) else []
            if isinstance(rows, list):
                collected.extend(item for item in rows if isinstance(item, dict))

            has_more_value = result.get('has_more') if isinstance(result, dict) else False
            if isinstance(has_more_value, str):
                has_more = has_more_value.strip().lower() in {'true', '1', 'yes'}
            else:
                has_more = bool(has_more_value)
            next_cursor = result.get('next_cursor') if isinstance(result, dict) else None
            if not has_more or next_cursor in {None, ''}:
                break
            cursor = next_cursor

        return collected

    def send_text(self, title: str, content: str) -> dict[str, str | bool]:
        if not self.enabled:
            return {'success': False, 'message': 'DingTalk is not configured'}
        return {'success': True, 'message': f'queued: {title}', 'content': content[:120]}

    def send_work_notification(self, userid: str, content: str | dict) -> tuple[bool, str]:
        user_id = str(userid or '').strip()
        if not user_id:
            return False, 'dingtalk_user_missing'
        if getattr(settings, 'DINGTALK_NOTIFY_DRY_RUN', False):
            logger.info('[notify] dingtalk dry-run %s | %s', user_id, content)
            return True, 'dingtalk_dry_run'
        if not self.enabled:
            return False, 'dingtalk_not_configured'

        try:
            access_token = self.fetch_access_token()
            self._throttle_message_send()
            payload = {
                'agent_id': int(self.config.agent_id) if str(self.config.agent_id or '').isdigit() else self.config.agent_id,
                'userid_list': user_id,
                'msg': self._build_message(content),
            }
            response = self._request_json(
                method='POST',
                url=f'https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2?access_token={parse.quote(access_token)}',
                payload=payload,
            )
            self._ensure_success(response)
            return True, 'dingtalk_sent'
        except Exception as exc:  # noqa: BLE001
            logger.warning('DingTalk work notification failed: %s', exc)
            return False, str(exc) or 'dingtalk_send_failed'

    def send_group_message(self, chat_id: str, message: dict) -> tuple[bool, str | dict]:
        chat = str(chat_id or '').strip()
        if not chat:
            return False, 'dingtalk_chat_missing'
        if getattr(settings, 'DINGTALK_NOTIFY_DRY_RUN', False):
            logger.info('[notify] dingtalk group dry-run %s | %s', chat, message)
            return True, 'dingtalk_dry_run'
        if not self.enabled:
            return False, 'dingtalk_not_configured'

        response = None
        try:
            access_token = self.fetch_access_token()
            self._throttle_message_send()
            response = self._request_json(
                method='POST',
                url=f'https://oapi.dingtalk.com/chat/send?access_token={parse.quote(access_token)}',
                payload={'chatid': chat, 'msg': message},
            )
            self._ensure_success(response)
            return True, {
                'detail': 'dingtalk_sent',
                'provider_message_id': self._extract_provider_message_id(response),
                'response_payload': response,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning('DingTalk group message failed: %s', exc)
            if isinstance(response, dict):
                return False, {
                    'detail': str(exc) or 'dingtalk_send_failed',
                    'provider_message_id': self._extract_provider_message_id(response),
                    'response_payload': response,
                }
            return False, str(exc) or 'dingtalk_send_failed'

    @staticmethod
    def _extract_provider_message_id(payload: dict) -> str | None:
        for key in ('messageId', 'message_id', 'msgId', 'msg_id', 'openMsgId', 'open_msg_id'):
            value = payload.get(key)
            if value not in (None, ''):
                return str(value)
        result = payload.get('result')
        if isinstance(result, dict):
            for key in ('messageId', 'message_id', 'msgId', 'msg_id', 'openMsgId', 'open_msg_id'):
                value = result.get(key)
                if value not in (None, ''):
                    return str(value)
        return None


service = DingTalkService()


def send_work_notification(userid: str, content: str | dict) -> tuple[bool, str]:
    return service.send_work_notification(userid, content)


def send_group_message(chat_id: str, message: dict) -> tuple[bool, str | dict]:
    return service.send_group_message(chat_id, message)


def _normalize_clock_type(value: str | None) -> str | None:
    mapping = {
        'in': 'in',
        'clock_in': 'in',
        'checkin': 'in',
        'on': 'in',
        'onduty': 'in',
        '上班': 'in',
        'out': 'out',
        'clock_out': 'out',
        'checkout': 'out',
        'off': 'out',
        'offduty': 'out',
        '下班': 'out',
    }
    return mapping.get(str(value or '').strip().lower())


def _resolve_employee_id(db, payload: dict) -> int | None:
    employee_id = payload.get('employee_id')
    if employee_id is not None:
        return int(employee_id)

    query = db.query(Employee)
    dingtalk_user_id = payload.get('dingtalk_user_id')
    dingtalk_union_id = payload.get('dingtalk_union_id')
    employee_no = payload.get('employee_no')
    if dingtalk_user_id:
        employee = query.filter(Employee.dingtalk_user_id == str(dingtalk_user_id)).first()
        if employee is not None:
            return employee.id
    if dingtalk_union_id:
        employee = query.filter(Employee.dingtalk_union_id == str(dingtalk_union_id)).first()
        if employee is not None:
            return employee.id
    if employee_no:
        employee = query.filter(Employee.employee_no == str(employee_no)).first()
        if employee is not None:
            return employee.id
    return None


def sync_clock_records(db, *, start_date: str, end_date: str) -> dict[str, int]:
    try:
        rows = service.fetch_clock_records(start_date, end_date)
    except Exception as exc:  # noqa: BLE001
        logger.warning('DingTalk clock sync skipped: %s', exc)
        return {'synced': 0, 'skipped': 0, 'failed': 0}

    synced = 0
    skipped = 0
    failed = 0
    for row in rows:
        try:
            dingtalk_id = str(row.get('dingtalk_id') or row.get('id') or '').strip()
            clock_type = _normalize_clock_type(row.get('clock_type'))
            clock_time_raw = row.get('clock_time')
            if not dingtalk_id or not clock_type or not clock_time_raw:
                skipped += 1
                continue
            clock_time = clock_time_raw
            if isinstance(clock_time_raw, str):
                clock_time = datetime.fromisoformat(clock_time_raw)
            if clock_time.tzinfo is None:
                clock_time = clock_time.replace(tzinfo=timezone.utc)

            entity = db.query(AttendanceClockRecord).filter(AttendanceClockRecord.dingtalk_id == dingtalk_id).first()
            if entity is None:
                entity = AttendanceClockRecord(
                    dingtalk_id=dingtalk_id,
                    clock_type=clock_type,
                    clock_time=clock_time,
                )
                db.add(entity)
            entity.employee_id = _resolve_employee_id(db, row)
            entity.clock_type = clock_type
            entity.clock_time = clock_time
            entity.synced_at = datetime.now(timezone.utc)
            synced += 1
        except Exception:  # noqa: BLE001
            failed += 1
    if hasattr(db, 'commit'):
        db.commit()
    return {'synced': synced, 'skipped': skipped, 'failed': failed}


def sync_recent_clock_records(now: datetime | None = None) -> dict[str, int]:
    current = now or datetime.now(timezone.utc)
    sessionmaker = get_sessionmaker()
    db = sessionmaker()
    try:
        start_date = (current - timedelta(days=1)).date().isoformat()
        end_date = current.date().isoformat()
        return sync_clock_records(db, start_date=start_date, end_date=end_date)
    finally:
        db.close()


def register_jobs(scheduler) -> None:
    if scheduler is None:
        return
    if scheduler.get_job('dingtalk-clock-sync') is not None:
        return
    scheduler.add_job(
        sync_recent_clock_records,
        'interval',
        minutes=30,
        id='dingtalk-clock-sync',
        replace_existing=True,
    )
