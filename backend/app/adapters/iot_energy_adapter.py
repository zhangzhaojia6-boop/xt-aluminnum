from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import re
from typing import Any, Callable, Mapping

from app.core.redaction import filter_sensitive_mapping


QueryRunner = Callable[..., list[Mapping[str, Any]]]

_WRITE_SQL_PATTERN = re.compile(
    r'\b(insert|update|delete|merge|drop|alter|create|truncate|exec|execute|grant|revoke|deny|backup|restore)\b',
    re.IGNORECASE,
)


@dataclass(slots=True)
class IotEnergyReading:
    meter_code: str
    reading_at: datetime
    meter_name: str | None = None
    electricity_kwh: float | None = None
    gas_m3: float | None = None
    water_m3: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class IotEnergyAdapter:
    def list_readings(self, *, business_date: date, limit: int = 500) -> list[IotEnergyReading]:
        _ = (business_date, limit)
        return []


class NullIotEnergyAdapter(IotEnergyAdapter):
    pass


class SqlServerIotEnergyAdapter(IotEnergyAdapter):
    """Read-only adapter for an external IoT energy database."""

    def __init__(
        self,
        *,
        host: str = '',
        port: int = 1433,
        database: str = '',
        username: str = '',
        password: str = '',
        query: str = '',
        timeout_seconds: float = 8.0,
        encrypt: bool = False,
        query_runner: QueryRunner | None = None,
    ) -> None:
        self._host = host.strip()
        self._port = int(port)
        self._database = database.strip()
        self._username = username.strip()
        self._password = password
        self._query = query.strip()
        self._timeout_seconds = float(timeout_seconds)
        self._encrypt = bool(encrypt)
        self._query_runner = query_runner

    def list_readings(self, *, business_date: date, limit: int = 500) -> list[IotEnergyReading]:
        bounded_limit = max(1, min(int(limit), 2000))
        if self._query_runner is not None:
            rows = self._query_runner(business_date=business_date, limit=bounded_limit)
        else:
            if not self._query:
                return []
            query = self._query.format(limit=bounded_limit)
            rows = _run_pymssql_query(
                host=self._host,
                port=self._port,
                database=self._database,
                username=self._username,
                password=self._password,
                timeout_seconds=self._timeout_seconds,
                encrypt=self._encrypt,
                query=query,
                params=(business_date,),
            )
        return [_reading_from_row(row) for row in rows if _text(_value(row, 'meter_code', 'MeterCode', 'PointCode'))]


def _ensure_read_only_query(query: str) -> None:
    normalized = query.strip()
    if not re.match(r'(?is)^select\b', normalized):
        raise ValueError('IoT energy adapter only allows read-only SELECT queries')
    if ';' in normalized:
        raise ValueError('IoT energy adapter does not allow stacked SQL statements')
    query_without_literals = re.sub(r"(?is)N?'(?:''|[^'])*'", "''", normalized)
    if _WRITE_SQL_PATTERN.search(query_without_literals):
        raise ValueError('IoT energy adapter rejected a non-read-only SQL keyword')


def _run_pymssql_query(
    *,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    timeout_seconds: float,
    encrypt: bool,
    query: str,
    params: tuple[Any, ...] = (),
) -> list[Mapping[str, Any]]:
    _ensure_read_only_query(query)
    _ = encrypt
    import pymssql

    with pymssql.connect(
        server=host,
        port=port,
        user=username,
        password=password,
        database=database,
        login_timeout=int(timeout_seconds),
        timeout=int(timeout_seconds),
        as_dict=True,
    ) as connection:
        with connection.cursor(as_dict=True) as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())


def _reading_from_row(row: Mapping[str, Any]) -> IotEnergyReading:
    return IotEnergyReading(
        meter_code=_text(_value(row, 'meter_code', 'MeterCode', 'PointCode')) or '',
        meter_name=_text(_value(row, 'meter_name', 'MeterName', 'PointName')),
        reading_at=_datetime(_value(row, 'reading_at', 'ReadingAt', 'CollectTime', 'CreateDate')) or datetime.now(),
        electricity_kwh=_float(_value(row, 'electricity_kwh', 'ElectricityKwh', 'PowerKwh', 'Kwh')),
        gas_m3=_float(_value(row, 'gas_m3', 'GasM3', 'GasValue')),
        water_m3=_float(_value(row, 'water_m3', 'WaterM3', 'WaterValue')),
        metadata=filter_sensitive_mapping(row),
    )


def _value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    lower_map = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lower_map.get(key.lower())
        if value is not None:
            return value
    return None


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


def _datetime(value: Any) -> datetime | None:
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
