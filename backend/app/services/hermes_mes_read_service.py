from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any

from app.adapters.mes_adapter import MesAdapter
from app.core.business_time import production_business_window
from app.core.redaction import filter_sensitive_mapping, redact_secret_text


class UnsupportedMesQueryKeyError(ValueError):
    pass


class MesReadTimeoutError(RuntimeError):
    pass


QueryRunner = Callable[[MesAdapter, datetime, datetime, int], list[Any]]


def _run_workshop_process_records(adapter: MesAdapter, start_at: datetime, end_at: datetime, limit: int) -> list[Any]:
    return adapter.list_workshop_process_records_between(start_at=start_at, end_at=end_at, limit=limit, offset=0)


def _run_stock_records(adapter: MesAdapter, start_at: datetime, end_at: datetime, limit: int) -> list[Any]:
    return adapter.list_stock_records_between(start_at=start_at, end_at=end_at, limit=limit, offset=0)


def _run_finished_inbound_records(adapter: MesAdapter, start_at: datetime, end_at: datetime, limit: int) -> list[Any]:
    return adapter.list_finished_inbound_records_between(start_at=start_at, end_at=end_at, limit=limit, offset=0)


def _run_delivery_records(adapter: MesAdapter, start_at: datetime, end_at: datetime, limit: int) -> list[Any]:
    return adapter.list_delivery_records_between(start_at=start_at, end_at=end_at, limit=limit, offset=0)


def _run_material_records(adapter: MesAdapter, start_at: datetime, end_at: datetime, limit: int) -> list[Any]:
    return adapter.list_material_records_between(start_at=start_at, end_at=end_at, limit=limit, offset=0)


def _run_wip_totals(adapter: MesAdapter, start_at: datetime, end_at: datetime, limit: int) -> list[Any]:
    _ = (start_at, end_at, limit)
    return adapter.list_wip_totals()


def _run_stock(adapter: MesAdapter, start_at: datetime, end_at: datetime, limit: int) -> list[Any]:
    _ = (start_at, end_at)
    return adapter.list_stock(limit=limit)


def _run_yield_records(adapter: MesAdapter, start_at: datetime, end_at: datetime, limit: int) -> list[Any]:
    _ = (start_at, end_at)
    return adapter.list_yield_records(limit=limit)


_QUERY_SPECS: dict[str, tuple[str, QueryRunner]] = {
    'workshop_process_records': ('list_workshop_process_records_between', _run_workshop_process_records),
    'stock_records': ('list_stock_records_between', _run_stock_records),
    'finished_inbound_records': ('list_finished_inbound_records_between', _run_finished_inbound_records),
    'delivery_records': ('list_delivery_records_between', _run_delivery_records),
    'material_records': ('list_material_records_between', _run_material_records),
    'wip_totals': ('list_wip_totals', _run_wip_totals),
    'stock': ('list_stock', _run_stock),
    'yield_records': ('list_yield_records', _run_yield_records),
}


class HermesMesReadService:
    DEFAULT_LIMIT = 5000
    MAX_LIMIT = 20000

    def __init__(self, adapter: MesAdapter) -> None:
        self._adapter = adapter

    def read_sources(
        self,
        *,
        business_date: date,
        query_keys: Sequence[str],
        limit: int = DEFAULT_LIMIT,
        workshop_name: str | None = None,
    ) -> dict[str, Any]:
        validated_query_keys = self._validate_query_keys(query_keys)
        bounded_limit = self._bounded_limit(limit)
        start_at, end_at = production_business_window(business_date, workshop_name=workshop_name)

        records: dict[str, list[Any]] = {}
        source_errors: dict[str, str] = {}
        source_states: dict[str, dict[str, int | str]] = {}
        failed_sources = 0
        non_empty_sources = 0

        for query_key in validated_query_keys:
            required_method_name, runner = _QUERY_SPECS[query_key]
            if not self._adapter_overrides(required_method_name):
                failed_sources += 1
                source_states[query_key] = {'status': 'failed', 'count': 0}
                source_errors[query_key] = redact_secret_text(
                    f'unsupported_adapter_capability:{query_key}:{required_method_name}'
                )
                continue
            try:
                result = runner(self._adapter, start_at, end_at, bounded_limit)
            except TimeoutError as exc:
                failed_sources += 1
                source_states[query_key] = {'status': 'failed', 'count': 0}
                source_errors[query_key] = redact_secret_text(str(MesReadTimeoutError(str(exc))))
                continue
            except Exception as exc:
                failed_sources += 1
                source_states[query_key] = {'status': 'failed', 'count': 0}
                source_errors[query_key] = redact_secret_text(str(exc))
                continue

            serialized = self._to_plain_data(result)
            count = self._count_items(serialized)
            records[query_key] = serialized
            source_states[query_key] = {'status': 'ok' if count else 'empty', 'count': count}
            if count:
                non_empty_sources += 1

        return {
            'business_date': business_date.isoformat(),
            'window': {
                'start_at': start_at.isoformat(),
                'end_at': end_at.isoformat(),
            },
            'records': records,
            'source_status': {
                'mes': self._mes_status(
                    requested_count=len(validated_query_keys),
                    failed_count=failed_sources,
                    non_empty_count=non_empty_sources,
                ),
                'sources': source_states,
            },
            'source_errors': source_errors,
        }

    @staticmethod
    def _validate_query_keys(query_keys: Sequence[str]) -> list[str]:
        validated = [str(query_key).strip() for query_key in query_keys]
        unsupported = [query_key for query_key in validated if query_key not in _QUERY_SPECS]
        if unsupported:
            joined = ', '.join(unsupported)
            raise UnsupportedMesQueryKeyError(f'Unsupported MES query key: {joined}')
        return validated

    def _adapter_overrides(self, method_name: str) -> bool:
        adapter_method = getattr(type(self._adapter), method_name, None)
        base_method = getattr(MesAdapter, method_name, None)
        return adapter_method is not None and adapter_method is not base_method

    @classmethod
    def _bounded_limit(cls, limit: int) -> int:
        return max(1, min(int(limit), cls.MAX_LIMIT))

    @staticmethod
    def _count_items(value: Any) -> int:
        if isinstance(value, list):
            return len(value)
        if value is None:
            return 0
        return 1

    @staticmethod
    def _mes_status(*, requested_count: int, failed_count: int, non_empty_count: int) -> str:
        if requested_count and failed_count == requested_count:
            return 'failed'
        if failed_count:
            return 'partial_failed'
        if non_empty_count:
            return 'ok'
        return 'empty'

    @classmethod
    def _to_plain_data(cls, value: Any) -> Any:
        if is_dataclass(value):
            return cls._to_plain_data(asdict(value))
        if isinstance(value, Mapping):
            sanitized = filter_sensitive_mapping(value)
            return {str(key): cls._to_plain_data(item) for key, item in sanitized.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._to_plain_data(item) for item in value]
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)
