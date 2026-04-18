from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping

import httpx

from app.adapters.mes_adapter import CardInfo, CoilSnapshot, MesAdapter, ScheduleItem


def _normalize_datetime(value: Any) -> datetime | None:
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _to_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


class RestApiMesAdapter(MesAdapter):
    """Minimal Phase 1 REST adapter for MES pull synchronization."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 8.0,
        tracking_card_info_path: str = '/tracking-cards/{card_no}',
        coil_snapshots_path: str = '/coil-snapshots',
        sender: Callable[..., httpx.Response] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._api_key = (api_key or '').strip()
        self._timeout_seconds = timeout_seconds
        self._tracking_card_info_path = tracking_card_info_path
        self._coil_snapshots_path = coil_snapshots_path
        self._sender = sender or self._default_sender

    def get_tracking_card_info(self, card_no: str) -> CardInfo | None:
        response = self._request(
            method='GET',
            path=self._tracking_card_info_path.format(card_no=card_no),
        )
        payload = self._extract_payload(response)
        if not payload:
            return None
        return CardInfo(
            card_no=str(payload.get('card_no') or card_no).strip().upper(),
            process_route_code=str(payload.get('process_route_code') or '').strip() or None,
            alloy_grade=str(payload.get('alloy_grade') or '').strip() or None,
            batch_no=str(payload.get('batch_no') or '').strip() or None,
            qr_code=str(payload.get('qr_code') or '').strip() or None,
            metadata=dict(_to_mapping(payload.get('metadata'))),
        )

    def list_coil_snapshots(
        self,
        *,
        cursor: str | None = None,
        updated_after: datetime | None = None,
        limit: int = 200,
    ) -> tuple[list[CoilSnapshot], str | None]:
        params = {
            'limit': limit,
        }
        if cursor:
            params['cursor'] = cursor
        if updated_after:
            params['updated_after'] = updated_after.isoformat()
        response = self._request(
            method='GET',
            path=self._coil_snapshots_path,
            params=params,
        )
        payload = self._extract_payload(response)
        items = payload.get('items')
        if not isinstance(items, list):
            items = []
        snapshots = [self._build_snapshot(item) for item in items if isinstance(item, Mapping)]
        next_cursor = str(payload.get('next_cursor') or '').strip() or cursor
        return snapshots, next_cursor

    def get_daily_schedule(self, business_date, workshop: str) -> list[ScheduleItem]:
        response = self._request(
            method='GET',
            path='/daily-schedule',
            params={
                'business_date': business_date.isoformat(),
                'workshop': workshop,
            },
        )
        payload = self._extract_payload(response)
        items = payload.get('items')
        if not isinstance(items, list):
            items = []
        return [
            ScheduleItem(
                tracking_card_no=str(item.get('tracking_card_no') or '').strip().upper(),
                workshop=str(item.get('workshop') or workshop).strip(),
                machine=str(item.get('machine') or '').strip() or None,
                shift=str(item.get('shift') or '').strip() or None,
                planned_input_weight=item.get('planned_input_weight'),
                planned_output_weight=item.get('planned_output_weight'),
                metadata=dict(_to_mapping(item.get('metadata'))),
            )
            for item in items
            if isinstance(item, Mapping)
        ]

    def push_completion(self, card_no: str, output_weight: float | None, yield_rate: float | None) -> bool:
        response = self._request(
            method='POST',
            path='/completions',
            json={
                'card_no': card_no,
                'output_weight': output_weight,
                'yield_rate': yield_rate,
            },
        )
        payload = self._extract_payload(response)
        accepted = payload.get('accepted')
        if accepted is None:
            return response.status_code < 400
        return bool(accepted)

    def _request(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        headers = {'Accept': 'application/json'}
        if self._api_key:
            headers['Authorization'] = f'Bearer {self._api_key}'
        return self._sender(
            method=method,
            url=f'{self._base_url}{path}',
            headers=headers,
            params=params,
            json=json,
            timeout=self._timeout_seconds,
        )

    def _extract_payload(self, response: httpx.Response) -> Mapping[str, Any]:
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return {'items': payload}
        if not isinstance(payload, Mapping):
            return {}
        if isinstance(payload.get('data'), Mapping):
            return _to_mapping(payload.get('data'))
        return payload

    @staticmethod
    def _build_snapshot(item: Mapping[str, Any]) -> CoilSnapshot:
        metadata = dict(_to_mapping(item.get('metadata')))
        for key in ('input_weight', 'output_weight', 'scrap_weight'):
            if item.get(key) is not None and key not in metadata:
                metadata[key] = item.get(key)
        return CoilSnapshot(
            coil_id=str(item.get('coil_id') or item.get('id') or item.get('tracking_card_no') or '').strip(),
            tracking_card_no=str(item.get('tracking_card_no') or '').strip().upper(),
            qr_code=str(item.get('qr_code') or '').strip() or None,
            batch_no=str(item.get('batch_no') or '').strip() or None,
            contract_no=str(item.get('contract_no') or '').strip() or None,
            workshop_code=str(item.get('workshop_code') or '').strip() or None,
            process_code=str(item.get('process_code') or '').strip() or None,
            machine_code=str(item.get('machine_code') or '').strip() or None,
            shift_code=str(item.get('shift_code') or '').strip() or None,
            status=str(item.get('status') or '').strip() or None,
            event_time=_normalize_datetime(item.get('event_time')),
            updated_at=_normalize_datetime(item.get('updated_at') or item.get('event_time')),
            metadata=metadata,
        )

    @staticmethod
    def _default_sender(**kwargs) -> httpx.Response:
        with httpx.Client() as client:
            return client.request(**kwargs)
