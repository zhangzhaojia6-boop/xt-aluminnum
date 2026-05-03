from __future__ import annotations

from datetime import datetime
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
    MesStockItem,
    MesWipTotal,
    ScheduleItem,
)


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


def _to_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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
        normalized = card_no.strip().upper()
        for item in items:
            if item.tracking_card_no.strip().upper() == normalized:
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
        rows = self._post_table('/Dispatch/DoingReportTotal')
        return [
            MesWipTotal(
                workshop_name=_text(row.get('WorkShopName') or row.get('WorkshopName')) or '',
                doing_count=_int(row.get('DoingCount') or row.get('Count')),
                doing_weight=_float(row.get('DoingWeight') or row.get('Weight')),
                metadata=dict(row),
            )
            for row in rows
        ]

    def list_stock(self, *, limit: int = 200) -> list[MesStockItem]:
        rows = self._post_table('/Stock/GetList', limit=limit)
        return [
            MesStockItem(
                coil_key=_coil_key(row),
                tracking_card_no=_text(row.get('BatchNumber') or row.get('CardNo') or row.get('BatchNo')) or '',
                weight=_float(row.get('Weight') or row.get('NetWeight') or row.get('GrossWeight')),
                destination=_text(row.get('Destination') or row.get('StockName') or row.get('StatusName')),
                metadata=dict(row),
            )
            for row in rows
        ]

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
        return CoilSnapshot(
            coil_id=_coil_key(row),
            tracking_card_no=_text(row.get('BatchNumber') or row.get('CardNo') or row.get('BatchNo')) or '',
            qr_code=_text(row.get('QrCode') or row.get('QRCode')),
            batch_no=_text(row.get('BatchNumber') or row.get('BatchNo')),
            contract_no=_text(row.get('ContractNo') or row.get('ContractNumber')),
            workshop_code=_text(row.get('CurrentWorkShop') or row.get('WorkShopName')),
            process_code=_text(row.get('CurrentProcess') or row.get('ProcessName')),
            machine_code=_text(row.get('DeviceName') or row.get('MachineName')),
            shift_code=_text(row.get('ShiftName') or row.get('ShiftCode')),
            status=_text(row.get('StatusName') or row.get('Status')),
            event_time=_datetime(row.get('EventTime') or row.get('CreateTime')),
            updated_at=_datetime(row.get('UpdateTime') or row.get('UpdatedAt') or row.get('CreateTime')),
            metadata=metadata,
        )

    def _post_table(self, path: str, *, limit: int = 200) -> list[Mapping[str, Any]]:
        data = {
            'draw': 1,
            'start': 0,
            'length': limit,
        }
        if self._request_verification_token:
            data['__RequestVerificationToken'] = self._request_verification_token
        response = self._request(
            'POST',
            path,
            data=data,
        )
        payload = self._payload(response)
        return self._extract_rows(payload)

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
    def _extract_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        rows = payload.get('data') or payload.get('Data') or payload.get('aaData') or payload.get('rows')
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, Mapping)]

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
