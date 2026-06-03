from __future__ import annotations

from datetime import datetime
import hashlib
from html import unescape
import json
import re
from typing import Any, Callable, Mapping

import httpx

from app.adapters.mes_adapter import (
    CardInfo,
    CoilSnapshot,
    MesCraft,
    MesAdapter,
    MesDevice,
    MesMachineLineSource,
    MesSourceRecord,
    MesStockItem,
    MesWipTotal,
    ScheduleItem,
)
from app.utils.tracking_cards import tracking_card_lookup_key


_PRESERVED_DISPATCH_KEYS = (
    'CurrentWorkShop',
    'CurrentProcess',
    'NextWorkShop',
    'NextProcess',
    'ProcessRoute',
    'PrintProcessRoute',
    'DelayHour',
    'StatusName',
    'MaterialCode',
)

_READ_ONLY_PATH_HINTS = (
    'GetList',
    'QueryList',
    'Report',
    'Total',
    'GetTreeList',
    'GetBoardList',
    'GetDetailList',
    'GetItem',
    'Index',
)

_WRITE_PATH_HINTS = (
    'Save',
    'Delete',
    'Deleted',
    'Remove',
    'Set',
    'Invalid',
    'Disabled',
    'Enabled',
    'Unbind',
    'Recovery',
    'Revoke',
    'Send',
    'Update',
    'Edit',
    'Add',
    'Upload',
    'Import',
)

_SENSITIVE_KEYS = {
    'Password',
    'NewPassword',
    'NewPasswordConfirm',
    'OldPassword',
    'Mobile',
    'CustomerMobile',
    'Address',
    'CustomerAddress',
    'Email',
}

_WORKSHOP_NAMES = {
    '1450车间',
    '1650车间',
    '1850车间',
    '2050车间',
    '拉矫车间',
    '热轧车间',
    '精整',
    '彩涂',
    '新厂在线车间',
    '园区在线车间',
    '园区淬火车间',
    '园区精整',
    '园区圆片',
    '铣床车间',
}

_TRACKING_CARD_KEYS = (
    'CardNo',
    'FollowCardNo',
    'FollowCardNumber',
    'TrackingCardNo',
    'TrackingCardNumber',
    'FlowCardNo',
    'FlowCardNumber',
    'CirculationCardNo',
    'CirculationCardNumber',
)


def _to_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _identifier(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    normalized = text.lower()
    if normalized in {'0', '00000000-0000-0000-0000-000000000000'}:
        return None
    return text


def _float(value: Any) -> float | None:
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime | None:
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.startswith('/Date(') and text.endswith(')/'):
        milliseconds = _int(text[6:-2])
        if milliseconds is None or milliseconds <= 0:
            return None
        try:
            return datetime.fromtimestamp(milliseconds / 1000)
        except (OSError, OverflowError, ValueError):
            return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _coil_event_time(row: Mapping[str, Any]) -> datetime | None:
    for key in (
        'EventTime',
        'OperateDate',
        'EndDatetime',
        'StrEndDatetime',
        'StrOperateDate',
        'StrFeedingDate',
        'StrCreateDate',
        'CreateTime',
        'CreateDate',
        'UpdateTime',
        'UpdatedAt',
    ):
        parsed = _datetime(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _nested_product_id(row: Mapping[str, Any]) -> str | None:
    product = _to_mapping(row.get('Product'))
    return _text(product.get('Id') or row.get('ProductId') or row.get('ProductID') or row.get('Id'))


def _coil_key(row: Mapping[str, Any]) -> str:
    product_id = _nested_product_id(row)
    if product_id:
        return f'MES:{product_id}'
    batch_no = _text(row.get('BatchNumber') or row.get('BatchNo') or row.get('CardNo')) or 'unknown'
    material_code = _text(row.get('MaterialCode')) or 'unknown'
    return f'fallback:{batch_no}:{material_code}'


def _tracking_card_no(row: Mapping[str, Any]) -> str:
    for key in _TRACKING_CARD_KEYS:
        value = _text(row.get(key))
        if value:
            return value
    return _text(row.get('BatchNumber') or row.get('BatchNo') or row.get('MaterialCode')) or ''


def _safe_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in row.items() if str(key) not in _SENSITIVE_KEYS}


def _record_id(row: Mapping[str, Any], *fallback_keys: str) -> str:
    for key in ('Id', 'ID', *fallback_keys, 'BatchNumber', 'MaterialCode', 'Code', 'Name'):
        text = _identifier(row.get(key))
        if text:
            return text
    payload = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str)
    return f'fallback:{hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]}'


def _ensure_read_only_path(path: str) -> None:
    tail = path.rsplit('/', 1)[-1]
    if any(hint in tail for hint in _WRITE_PATH_HINTS):
        raise ValueError(f'MES MVC path is not read-only: {path}')
    if not any(hint in tail for hint in _READ_ONLY_PATH_HINTS):
        raise ValueError(f'MES MVC path is not in the read-only allowlist: {path}')


def _html_tokens(html: str) -> list[str]:
    text = re.sub(r'<[^>]+>', '\n', html)
    return [
        token.strip()
        for token in re.split(r'[\r\n]+', unescape(text))
        if token.strip()
    ]


def _parse_wip_total_html(html: str) -> list[MesWipTotal]:
    tokens = _html_tokens(html)
    items: list[MesWipTotal] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token not in _WORKSHOP_NAMES and not token.endswith('车间'):
            index += 1
            continue
        workshop_name = token
        index += 1
        total_weight = _float(tokens[index]) if index < len(tokens) else None
        if index < len(tokens):
            index += 1
        process_totals: dict[str, float] = {}
        while index < len(tokens):
            process_name = tokens[index]
            if process_name in _WORKSHOP_NAMES or process_name.endswith('车间'):
                break
            index += 1
            if index >= len(tokens):
                break
            process_weight = _float(tokens[index])
            index += 1
            if process_weight is not None and process_name != '-':
                process_totals[process_name] = process_weight
        if total_weight is not None or process_totals:
            items.append(
                MesWipTotal(
                    workshop_name=workshop_name,
                    doing_weight=total_weight,
                    metadata={
                        'source_path': '/Dispatch/DoingReportTotal',
                        'process_totals': process_totals,
                    },
                )
            )
    return items


class MvcMesAdapter(MesAdapter):
    """Read-only adapter for the vendor MES MVC/DataTables surface."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout_seconds: float = 8.0,
        sender: Callable[..., httpx.Response] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._username = username
        self._password = password
        self._timeout_seconds = timeout_seconds
        self._sender = sender or self._default_sender
        self._cookies: dict[str, str] = {}
        self._request_verification_token: str | None = None
        self._logged_in = False

    def get_tracking_card_info(self, card_no: str) -> CardInfo | None:
        items = self.list_dispatch(limit=50)
        normalized = tracking_card_lookup_key(card_no)
        for item in items:
            if tracking_card_lookup_key(item.tracking_card_no) == normalized:
                return CardInfo(
                    card_no=item.tracking_card_no,
                    alloy_grade=_text(item.metadata.get('AlloyGrade')),
                    batch_no=item.batch_no,
                    qr_code=item.qr_code,
                    metadata=item.metadata,
                )
        return None

    def list_coil_snapshots(
        self,
        *,
        cursor: str | None = None,
        updated_after: datetime | None = None,
        limit: int = 200,
    ) -> tuple[list[CoilSnapshot], str | None]:
        _ = updated_after
        return self.list_dispatch(limit=limit), cursor

    def get_daily_schedule(self, business_date, workshop: str) -> list[ScheduleItem]:
        _ = (business_date, workshop)
        return []

    def push_completion(self, card_no: str, output_weight: float | None, yield_rate: float | None) -> bool:
        _ = (card_no, output_weight, yield_rate)
        return False

    def list_crafts(self) -> list[MesCraft]:
        rows = self._post_table('/Craft/GetList')
        return [
            MesCraft(
                source_id=_text(row.get('Id') or row.get('Code') or row.get('Name')) or '',
                code=_text(row.get('Code')),
                name=_text(row.get('Name') or row.get('CraftName')) or '',
                metadata=dict(row),
            )
            for row in rows
        ]

    def list_devices(self) -> list[MesDevice]:
        rows = self._post_table('/Device/GetList')
        return [
            MesDevice(
                source_id=_text(row.get('Id') or row.get('Code') or row.get('Name')) or '',
                code=_text(row.get('Code')),
                name=_text(row.get('Name') or row.get('DeviceName')) or '',
                workshop_name=_text(row.get('WorkShopName') or row.get('WorkshopName') or row.get('WorkShop')),
                metadata=dict(row),
            )
            for row in rows
        ]

    def list_follow_cards(self, *, limit: int = 200) -> list[CoilSnapshot]:
        return self._list_coils('/FollowCard/QueryList', limit=limit)

    def list_dispatch(self, *, limit: int = 200) -> list[CoilSnapshot]:
        return self._list_coils('/Dispatch/QueryList', limit=limit)

    def list_wip_totals(self) -> list[MesWipTotal]:
        response = self._get_response('/Dispatch/DoingReportTotal')
        payload = self._payload(response)
        rows = self._extract_rows(payload)
        if rows:
            return [
                MesWipTotal(
                    workshop_name=_text(row.get('WorkShopName') or row.get('WorkshopName')) or '',
                    doing_count=_int(row.get('DoingCount') or row.get('Count')),
                    doing_weight=_float(row.get('DoingWeight') or row.get('Weight')),
                    metadata=_safe_metadata(row),
                )
                for row in rows
            ]
        return _parse_wip_total_html(response.text or '')

    def list_stock(self, *, limit: int = 200) -> list[MesStockItem]:
        rows = self._post_table('/Stock/GetList', limit=limit)
        return [
            MesStockItem(
                coil_key=_coil_key(row),
                tracking_card_no=_tracking_card_no(row),
                weight=_float(row.get('Weight') or row.get('NetWeight') or row.get('GrossWeight')),
                destination=_text(row.get('Destination') or row.get('StockName') or row.get('StatusName')),
                metadata=dict(row),
            )
            for row in rows
        ]

    def list_workshop_process_records(self, *, limit: int = 200, page_size: int = 100) -> list[MesSourceRecord]:
        return self._list_source_records('/Report/ProductionWorkshopReport', limit=limit, page_size=page_size)

    def list_stock_records(self, *, limit: int = 200, page_size: int = 100) -> list[MesSourceRecord]:
        return self._list_source_records('/Stock/GetList', limit=limit, page_size=page_size)

    def list_material_records(self, *, limit: int = 200, page_size: int = 100) -> list[MesSourceRecord]:
        return self._list_source_records('/Material/GetList', limit=limit, page_size=page_size, fallback_key='MaterialCode')

    def list_yield_records(self, *, limit: int = 200, page_size: int = 100) -> list[MesSourceRecord]:
        return self._list_source_records('/Report/YieldReport', limit=limit, page_size=page_size)

    def list_reference_items(self) -> list[MesSourceRecord]:
        records: list[MesSourceRecord] = []
        for path in ('/Craft/GetList', '/Device/GetList', '/Dict/GetTreeList', '/Material/GetBoardList'):
            rows = self._post_table_pages(path, limit=500, page_size=100)
            records.extend(self._source_record(path, row) for row in rows)
        return records

    def list_machine_line_sources(self) -> list[MesMachineLineSource]:
        devices = self.list_devices()
        items: list[MesMachineLineSource] = []
        for device in devices:
            slot_no = _extract_slot_no(device.name)
            items.append(
                MesMachineLineSource(
                    line_code=_stable_line_code(device.workshop_name, device.name, slot_no),
                    line_name=device.name,
                    workshop_name=device.workshop_name,
                    slot_no=slot_no,
                    metadata=device.metadata,
                )
            )
        return items

    def _list_source_records(
        self,
        path: str,
        *,
        limit: int,
        page_size: int,
        fallback_key: str | None = None,
    ) -> list[MesSourceRecord]:
        rows = self._post_table_pages(path, limit=limit, page_size=page_size)
        return [self._source_record(path, row, fallback_key=fallback_key) for row in rows]

    def _source_record(self, path: str, row: Mapping[str, Any], *, fallback_key: str | None = None) -> MesSourceRecord:
        metadata = _safe_metadata(row)
        return MesSourceRecord(
            source_id=_record_id(metadata, *(key for key in (fallback_key,) if key)) or 'unknown',
            source_path=path,
            event_time=_coil_event_time(metadata),
            metadata=metadata,
        )

    def _list_coils(self, path: str, *, limit: int = 200) -> list[CoilSnapshot]:
        rows = self._post_table(path, limit=limit)
        return [self._build_snapshot(row) for row in rows]

    def _build_snapshot(self, row: Mapping[str, Any]) -> CoilSnapshot:
        metadata = dict(row)
        for key in _PRESERVED_DISPATCH_KEYS:
            if key == 'DelayHour':
                metadata[key] = _float(row.get(key))
            elif key in row:
                metadata[key] = row.get(key)
        event_time = _coil_event_time(row)
        return CoilSnapshot(
            coil_id=_coil_key(row),
            tracking_card_no=_tracking_card_no(row),
            qr_code=_text(row.get('QrCode') or row.get('QRCode')),
            batch_no=_text(row.get('BatchNumber') or row.get('BatchNo')),
            contract_no=_text(row.get('ContractNo') or row.get('ContractNumber') or row.get('ContractCode')),
            workshop_code=_text(row.get('CurrentWorkShop') or row.get('WorkShopName')),
            process_code=_text(row.get('CurrentProcess') or row.get('ProcessName')),
            machine_code=_text(row.get('DeviceName') or row.get('MachineName')),
            shift_code=_text(row.get('ShiftName') or row.get('ShiftCode')),
            status=_text(row.get('StatusName') or row.get('Status')),
            event_time=event_time,
            updated_at=_datetime(row.get('UpdateTime') or row.get('UpdatedAt')) or event_time,
            metadata=metadata,
        )

    def _post_table(self, path: str, *, limit: int = 200) -> list[Mapping[str, Any]]:
        return self._post_table_pages(path, limit=limit, page_size=limit)

    def _post_table_pages(self, path: str, *, limit: int = 200, page_size: int = 100) -> list[Mapping[str, Any]]:
        _ensure_read_only_path(path)
        bounded_limit = max(0, int(limit))
        bounded_page_size = max(1, min(int(page_size), bounded_limit or int(page_size)))
        rows: list[Mapping[str, Any]] = []
        start = 0
        total: int | None = None
        while len(rows) < bounded_limit:
            current_length = min(bounded_page_size, bounded_limit - len(rows))
            payload = self._post_table_payload(path, start=start, length=current_length)
            page_rows = self._extract_rows(payload)
            rows.extend(page_rows)
            total = self._extract_total(payload, default=total)
            if not page_rows or len(page_rows) < current_length:
                break
            start += len(page_rows)
            if total is not None and start >= total:
                break
        return rows[:bounded_limit]

    def _post_table_payload(self, path: str, *, start: int, length: int) -> Mapping[str, Any]:
        data = {
            'draw': 1,
            'start': start,
            'length': length,
        }
        response = self._request(
            'POST',
            path,
            data=data,
        )
        payload = self._payload(response)
        if self._looks_like_login_page(response=response, payload=payload):
            self._reset_session()
            response = self._request(
                'POST',
                path,
                data=data,
            )
            payload = self._payload(response)
            if self._looks_like_login_page(response=response, payload=payload):
                raise RuntimeError(f'MES MVC request failed after relogin: {path}')
        return payload

    def _get_response(self, path: str):
        _ensure_read_only_path(path)
        response = self._request('GET', path, data={})
        payload = self._payload(response)
        if self._looks_like_login_page(response=response, payload=payload):
            self._reset_session()
            response = self._request('GET', path, data={})
            payload = self._payload(response)
            if self._looks_like_login_page(response=response, payload=payload):
                raise RuntimeError(f'MES MVC request failed after relogin: {path}')
        return response

    def _request(self, method: str, path: str, *, data: Mapping[str, Any] | None = None) -> httpx.Response:
        if not self._logged_in and path not in {'/Login/Index', '/Login/CheckLogin', '/Login/QueryLogin'}:
            self._login()
        request_data = dict(data or {})
        if method.upper() == 'POST' and self._request_verification_token and not path.startswith('/Login'):
            request_data.setdefault('__RequestVerificationToken', self._request_verification_token)
        response = self._sender(
            method=method,
            url=f'{self._base_url}{path}',
            data=request_data,
            cookies=dict(self._cookies),
            headers=self._headers(path),
            timeout=self._timeout_seconds,
        )
        self._store_cookies(response)
        response.raise_for_status()
        return response

    def _login(self) -> None:
        token = self._ensure_request_verification_token()
        response = self._sender(
            method='POST',
            url=f'{self._base_url}/Login/CheckLogin',
            data={
                '__RequestVerificationToken': token,
                'Account': self._username,
                'Password': self._password,
                'MAC': '',
                'ktsn': '',
            },
            cookies=dict(self._cookies),
            headers=self._headers('/Login/CheckLogin'),
            timeout=self._timeout_seconds,
        )
        self._store_cookies(response)
        response.raise_for_status()
        payload = self._payload(response)
        if not self._is_success_payload(payload):
            message = _text(payload.get('message') or payload.get('Message')) or 'unknown error'
            raise RuntimeError(f'MES MVC login failed: {message}')

        query_login = self._sender(
            method='POST',
            url=f'{self._base_url}/Login/QueryLogin',
            data={
                '__RequestVerificationToken': token,
                'Account': self._username,
                'Password': self._password,
            },
            cookies=dict(self._cookies),
            headers=self._headers('/Login/QueryLogin'),
            timeout=self._timeout_seconds,
        )
        self._store_cookies(query_login)
        query_login.raise_for_status()
        query_payload = self._payload(query_login)
        if not self._is_success_payload(query_payload):
            message = _text(query_payload.get('message') or query_payload.get('Message')) or 'unknown error'
            raise RuntimeError(f'MES MVC login failed: {message}')

        for path in ('/Right/GetUserRightList',):
            followup = self._sender(
                method='POST',
                url=f'{self._base_url}{path}',
                data={'__RequestVerificationToken': token},
                cookies=dict(self._cookies),
                headers=self._headers(path),
                timeout=self._timeout_seconds,
            )
            self._store_cookies(followup)
            followup.raise_for_status()
        self._logged_in = True

    def _ensure_request_verification_token(self) -> str:
        if self._request_verification_token:
            return self._request_verification_token
        response = self._sender(
            method='GET',
            url=f'{self._base_url}/Login/Index',
            data={},
            cookies=dict(self._cookies),
            headers=self._headers('/Login/Index'),
            timeout=self._timeout_seconds,
        )
        self._store_cookies(response)
        response.raise_for_status()
        match = re.search(r'name=["\']__RequestVerificationToken["\'][^>]*value=["\']([^"\']+)["\']', response.text)
        if not match:
            raise RuntimeError('MES MVC login failed: missing request verification token')
        self._request_verification_token = match.group(1)
        return self._request_verification_token

    def _reset_session(self) -> None:
        self._cookies.clear()
        self._request_verification_token = None
        self._logged_in = False

    def _headers(self, path: str) -> dict[str, str]:
        return {
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self._base_url}/Login/Index' if path.startswith('/Login') else f'{self._base_url}/',
        }

    def _store_cookies(self, response: httpx.Response) -> None:
        cookies = getattr(response, 'cookies', None)
        if cookies:
            self._cookies.update(dict(cookies))

    @staticmethod
    def _payload(response: httpx.Response) -> Mapping[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            return {}
        if isinstance(payload, list):
            return {'data': payload}
        return payload if isinstance(payload, Mapping) else {}

    @staticmethod
    def _looks_like_login_page(*, response: httpx.Response, payload: Mapping[str, Any]) -> bool:
        if payload:
            return False
        text = str(getattr(response, 'text', '') or '')
        if not text:
            return False
        lowered = text.lower()
        return '__requestverificationtoken' in lowered or '/login/checklogin' in lowered

    @staticmethod
    def _extract_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        rows = payload.get('data') or payload.get('Data') or payload.get('aaData') or payload.get('rows')
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, Mapping)]

    @staticmethod
    def _extract_total(payload: Mapping[str, Any], *, default: int | None = None) -> int | None:
        for key in ('recordsTotal', 'recordsFiltered', 'total', 'Total'):
            value = _int(payload.get(key))
            if value is not None:
                return value
        return default

    @staticmethod
    def _is_success_payload(payload: Mapping[str, Any]) -> bool:
        for key in ('status', 'Status', 'success', 'Success'):
            if key in payload:
                return payload.get(key) is True
        return False

    @staticmethod
    def _default_sender(**kwargs) -> httpx.Response:
        with httpx.Client() as client:
            return client.request(**kwargs)


def _extract_slot_no(name: str) -> int | None:
    text = name.strip()
    if '#' not in text:
        return None
    prefix = text.split('#', 1)[0]
    return _int(prefix)


def _stable_line_code(workshop_name: str | None, line_name: str, slot_no: int | None) -> str:
    workshop = (workshop_name or 'unknown').strip().lower().replace(' ', '_')
    if slot_no is not None:
        return f'{workshop}:{slot_no:02d}'
    return f"{workshop}:{line_name.strip().lower().replace(' ', '_')}"
