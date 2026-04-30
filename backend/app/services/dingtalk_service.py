from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from urllib import parse, request

from app.config import settings
from app.database import get_sessionmaker
from app.core.scope import build_scope_summary, scope_to_dict
from app.models.attendance import AttendanceClockRecord
from app.models.master import Employee
from app.models.system import User


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DingTalkConfig:
    corp_id: str | None
    app_key: str | None
    app_secret: str | None
    agent_id: str | None


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

    @property
    def enabled(self) -> bool:
        return bool(self.config.corp_id and self.config.app_key and self.config.app_secret and self.config.agent_id)

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

    def _get_access_token(self) -> str:
        if not self.enabled:
            raise RuntimeError('DingTalk is not configured')
        query = parse.urlencode(
            {
                'appkey': self.config.app_key or '',
                'appsecret': self.config.app_secret or '',
            }
        )
        payload = self._request_json(method='GET', url=f'https://oapi.dingtalk.com/gettoken?{query}')
        access_token = payload.get('access_token') or payload.get('accessToken')
        if access_token:
            return str(access_token)
        raise RuntimeError(payload.get('errmsg') or payload.get('message') or 'failed to obtain DingTalk access token')

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

    def send_text(self, title: str, content: str) -> dict[str, str | bool]:
        if not self.enabled:
            return {'success': False, 'message': 'DingTalk is not configured'}
        return {'success': True, 'message': f'queued: {title}', 'content': content[:120]}


service = DingTalkService()


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
