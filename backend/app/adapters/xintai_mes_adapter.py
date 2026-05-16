from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping

import httpx

from app.adapters.mes_adapter import CardInfo, CoilSnapshot, MesAdapter, ScheduleItem
from app.adapters.rest_api_mes_adapter import _normalize_datetime


def _to_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


class XintaiMesAdapter(MesAdapter):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 10.0,
        sender: Callable[..., httpx.Response] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._sender = sender or self._default_sender

    def get_tracking_card_info(self, card_no: str) -> CardInfo | None:
        response = self._request(method='GET', path=f'/cards/{card_no}')
        if response.status_code == 404:
            return None
        payload = self._extract_payload(response)
        if not payload:
            return None
        return CardInfo(
            card_no=str(payload.get('card_no') or card_no).strip().upper(),
            process_route_code=str(payload.get('process_route_code') or payload.get('process') or '').strip() or None,
            alloy_grade=str(payload.get('alloy_grade') or payload.get('alloy') or '').strip() or None,
            batch_no=str(payload.get('batch_no') or payload.get('batch') or '').strip() or None,
            qr_code=str(payload.get('qr_code') or '').strip() or None,
            metadata={
                key: value
                for key, value in payload.items()
                if key
                not in {
                    'card_no',
                    'process_route_code',
                    'process',
                    'alloy_grade',
                    'alloy',
                    'batch_no',
                    'batch',
                    'qr_code',
                }
            },
        )

    def list_coil_snapshots(
        self,
        *,
        cursor: str | None = None,
        updated_after: datetime | None = None,
        limit: int = 200,
    ) -> tuple[list[CoilSnapshot], str | None]:
        params: dict[str, Any] = {'limit': limit}
        if cursor:
            params['cursor'] = cursor
        if updated_after:
            params['updated_after'] = updated_after.isoformat()
        response = self._request(method='GET', path='/coils', params=params)
        payload = self._extract_payload(response)
        items = payload.get('items') if isinstance(payload, Mapping) else []
        if not isinstance(items, list):
            items = []
        return [self._build_snapshot(item) for item in items if isinstance(item, Mapping)], payload.get('next_cursor')

    def get_daily_schedule(self, business_date, workshop: str) -> list[ScheduleItem]:
        response = self._request(
            method='GET',
            path='/schedule',
            params={'date': business_date.isoformat(), 'workshop': workshop},
        )
        payload = self._extract_payload(response)
        items = payload.get('items') if isinstance(payload, Mapping) else []
        if not isinstance(items, list):
            return []
        return [
            ScheduleItem(
                tracking_card_no=str(item.get('tracking_card_no') or item.get('card_no') or '').strip().upper(),
                workshop=str(item.get('workshop') or workshop).strip(),
                machine=str(item.get('machine') or item.get('machine_code') or '').strip() or None,
                shift=str(item.get('shift') or item.get('shift_code') or '').strip() or None,
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
            json={'card_no': card_no, 'output_weight': output_weight, 'yield_rate': yield_rate},
        )
        if response.status_code in {200, 201, 409}:
            return True
        response.raise_for_status()
        return False

    def _headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self._api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _request(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        return self._sender(
            method=method,
            url=f'{self._base_url}{path}',
            headers=self._headers(),
            params=params,
            json=json,
            timeout=self._timeout_seconds,
        )

    @staticmethod
    def _extract_payload(response: httpx.Response) -> Mapping[str, Any]:
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, Mapping) and isinstance(payload.get('data'), Mapping):
            return _to_mapping(payload.get('data'))
        if isinstance(payload, Mapping):
            return payload
        return {}

    @staticmethod
    def _build_snapshot(item: Mapping[str, Any]) -> CoilSnapshot:
        metadata = dict(_to_mapping(item.get('metadata')))
        for key in ('weight', 'width', 'thickness', 'current_process', 'destination'):
            if item.get(key) is not None and key not in metadata:
                metadata[key] = item.get(key)
        return CoilSnapshot(
            coil_id=str(item.get('coil_id') or item.get('id') or item.get('card_no') or '').strip(),
            tracking_card_no=str(item.get('tracking_card_no') or item.get('card_no') or '').strip().upper(),
            qr_code=str(item.get('qr_code') or '').strip() or None,
            batch_no=str(item.get('batch_no') or item.get('batch') or '').strip() or None,
            contract_no=str(item.get('contract_no') or '').strip() or None,
            workshop_code=str(item.get('workshop_code') or item.get('workshop') or '').strip() or None,
            process_code=str(item.get('process_code') or item.get('process') or '').strip() or None,
            machine_code=str(item.get('machine_code') or item.get('machine') or '').strip() or None,
            shift_code=str(item.get('shift_code') or item.get('shift') or '').strip() or None,
            status=str(item.get('status') or '').strip() or None,
            event_time=_normalize_datetime(item.get('event_time')),
            updated_at=_normalize_datetime(item.get('updated_at') or item.get('event_time')),
            metadata=metadata,
        )

    @staticmethod
    def _default_sender(**kwargs) -> httpx.Response:
        with httpx.Client() as client:
            return client.request(**kwargs)
