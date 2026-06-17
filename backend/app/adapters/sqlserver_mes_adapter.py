from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import re
from typing import Any, Callable, Mapping

from app.adapters.mes_adapter import (
    CardInfo,
    CoilSnapshot,
    MesAdapter,
    MesMachineLineSource,
    MesSourceRecord,
    MesStockItem,
    MesWipTotal,
    ScheduleItem,
)
from app.core.redaction import filter_sensitive_mapping
from app.utils.tracking_cards import tracking_card_lookup_key


QueryRunner = Callable[[str], list[Mapping[str, Any]]]


_QUERY_BY_KEY = {
    'card_lookup': (
        'SELECT TOP ({limit}) * FROM MES_Product WHERE '
        "UPPER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(MaterialCode)), N'一', '-'), "
        "N'－', '-'), N'—', '-'), N'–', '-'), N'﹣', '-'), '_', '-'), ' ', '')) = %s "
        'ORDER BY OperateDate DESC, CreateDate DESC'
    ),
    'dispatch': (
        'SELECT TOP ({limit}) * FROM MES_Product '
        'ORDER BY OperateDate DESC, CreateDate DESC'
    ),
    'follow_cards': (
        'SELECT TOP ({limit}) * FROM MES_Product '
        'ORDER BY OperateDate DESC, CreateDate DESC'
    ),
    'wip_totals': (
        'SELECT TOP ({limit}) CurrentWorkShop AS WorkShopName, CurrentProcess AS ProcessName, '
        'COUNT(*) AS DoingCount, SUM(FeedingWeight) AS DoingWeight '
        'FROM MES_Product WHERE InStockDate IS NULL AND DeliveryDate IS NULL '
        "AND CurrentWorkShop IS NOT NULL AND CurrentWorkShop <> '' "
        "AND CurrentProcess IS NOT NULL AND CurrentProcess <> '' "
        'GROUP BY CurrentWorkShop, CurrentProcess ORDER BY CurrentWorkShop, CurrentProcess'
    ),
    'workshop_process_records': (
        'SELECT TOP ({limit}) * FROM MES_ProductProcessRecord '
        'ORDER BY EndDatetime DESC, OperateDate DESC, CreateDate DESC'
    ),
    'stock_records': (
        'SELECT TOP ({limit}) * FROM WMS_InStockDetail '
        'ORDER BY AllocationDate DESC, OperateDate DESC, CreateDate DESC'
    ),
    'material_records': (
        'SELECT TOP ({limit}) * FROM MES_Material '
        'ORDER BY ProductionDate DESC, CreateDate DESC'
    ),
    'yield_records': (
        'SELECT TOP ({limit}) * FROM MES_ProductProcessRecord '
        'ORDER BY OperateDate DESC, CreateDate DESC'
    ),
    'stock': (
        'SELECT TOP ({limit}) * FROM WMS_Stock '
        'ORDER BY OperateDate DESC, CreateDate DESC'
    ),
    'devices': (
        'SELECT TOP ({limit}) * FROM MES_Device '
        'ORDER BY OperateDate DESC, CreateDate DESC'
    ),
}

_WRITE_SQL_PATTERN = re.compile(
    r'\b(insert|update|delete|merge|drop|alter|create|truncate|exec|execute|grant|revoke|deny|backup|restore)\b',
    re.IGNORECASE,
)


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


def _value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    lower_map = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        lower_key = key.lower()
        if lower_key in lower_map:
            return lower_map[lower_key]
    return None


def _safe_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    return filter_sensitive_mapping(row)


def _record_id(row: Mapping[str, Any], *keys: str) -> str:
    for key in ('Id', 'ID', 'ProductId', 'ProductID', *keys, 'TrackingCardNo', 'CardNo', 'MaterialCode', 'BatchNo', 'Name'):
        value = _text(_value(row, key))
        if value and value.lower() not in {'0', '00000000-0000-0000-0000-000000000000'}:
            return value
    payload = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str)
    return f'fallback:{hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]}'


def _ensure_read_only_query(query: str) -> None:
    normalized = query.strip()
    if not re.match(r'(?is)^select\b', normalized):
        raise ValueError('SQL Server MES adapter only allows read-only SELECT queries')
    if ';' in normalized:
        raise ValueError('SQL Server MES adapter does not allow stacked SQL statements')
    query_without_literals = re.sub(r"(?is)N?'(?:''|[^'])*'", "''", normalized)
    if _WRITE_SQL_PATTERN.search(query_without_literals):
        raise ValueError('SQL Server MES adapter rejected a non-read-only SQL keyword')


def _tracking_card_no(row: Mapping[str, Any]) -> str:
    return _text(
        _value(
            row,
            'TrackingCardNo',
            'TrackingCardNumber',
            'FollowCardNo',
            'FollowCardNumber',
            'CardNo',
            'FlowCardNo',
            'MaterialCode',
            'BatchNo',
            'BatchNumber',
        )
    ) or ''


def _coil_snapshot_from_row(row: Mapping[str, Any]) -> CoilSnapshot:
    product_id = _text(_value(row, 'ProductId', 'ProductID', 'Id', 'ID'))
    tracking_card_no = _tracking_card_no(row)
    updated_at = _datetime(_value(row, 'UpdateTime', 'UpdatedAt', 'StrUpdateTime', 'OperateDate', 'CreateTime', 'CreateDate'))
    event_time = _datetime(_value(row, 'EventTime', 'OperateDate', 'EndTime', 'EndDatetime', 'InStockDate')) or updated_at
    metadata = _safe_metadata(row)
    current_process_sort = _int(_value(row, 'CurrentProcessSort'))
    if current_process_sort is not None:
        metadata['CurrentProcessSort'] = current_process_sort
    delay_hours = _float(_value(row, 'DelayHour', 'DelayHours'))
    if delay_hours is not None:
        metadata['DelayHour'] = delay_hours
    return CoilSnapshot(
        coil_id=f'MES:{product_id}' if product_id else f'MES:{_record_id(row)}',
        tracking_card_no=tracking_card_no,
        qr_code=_text(_value(row, 'QrCode', 'QRCode')),
        batch_no=_text(_value(row, 'BatchNo', 'BatchNumber', 'PBatchNumber')),
        contract_no=_text(_value(row, 'ContractNo', 'ContractNumber', 'ContractCode', 'ContractNoticeCode')),
        workshop_code=_text(_value(row, 'CurrentWorkShop', 'WorkShopName', 'WorkshopName')),
        process_code=_text(_value(row, 'CurrentProcess', 'ProcessName')),
        machine_code=_text(_value(row, 'DeviceName', 'MachineName', 'MachineCode')),
        shift_code=_text(_value(row, 'ShiftCode', 'ShiftName')),
        status=_text(_value(row, 'StatusName', 'Status')),
        event_time=event_time,
        updated_at=updated_at,
        metadata=metadata,
    )


def _source_record(query_key: str, row: Mapping[str, Any]) -> MesSourceRecord:
    if query_key == 'stock_records':
        event_keys = ('EventTime', 'AllocationDate', 'InStockDate', 'OperateDate', 'ReportTime', 'UpdateTime', 'CreateDate')
    elif query_key == 'material_records':
        event_keys = ('ProductionDate', 'StrProductionDate', 'EventTime', 'OperateDate', 'UpdateTime', 'CreateDate')
    else:
        event_keys = ('EventTime', 'OperateDate', 'EndTime', 'EndDatetime', 'InStockDate', 'ReportTime', 'UpdateTime', 'CreateDate')
    return MesSourceRecord(
        source_id=_record_id(row),
        source_path=f'sqlserver:{query_key}',
        event_time=_datetime(_value(row, *event_keys)),
        metadata=_safe_metadata(row),
    )


def _wip_total_from_row(row: Mapping[str, Any]) -> MesWipTotal:
    metadata = _safe_metadata(row)
    process_name = _text(_value(row, 'ProcessName', 'CurrentProcess'))
    doing_weight = _float(_value(row, 'DoingWeight', 'WeightTons', 'MaterialWeightTons'))
    if process_name:
        metadata['process_totals'] = {process_name: doing_weight}
    return MesWipTotal(
        workshop_name=_text(_value(row, 'WorkShopName', 'WorkshopName', 'CurrentWorkShop')) or '',
        doing_count=_int(_value(row, 'DoingCount', 'Count', 'CoilCount')),
        doing_weight=doing_weight,
        metadata=metadata,
    )


class SqlServerMesAdapter(MesAdapter):
    """Read-only SQL Server adapter for MES projection.

    The adapter intentionally reads SQL Server into the existing MES projection
    model; management pages still read the local `mes_*` tables.
    """

    def __init__(
        self,
        *,
        host: str = '',
        port: int = 1433,
        database: str = '',
        username: str = '',
        password: str = '',
        timeout_seconds: float = 8.0,
        encrypt: bool = False,
        query_runner: Callable[..., list[Mapping[str, Any]]] | None = None,
    ) -> None:
        self._host = host.strip()
        self._port = int(port)
        self._database = database.strip()
        self._username = username.strip()
        self._password = password
        self._timeout_seconds = float(timeout_seconds)
        self._encrypt = bool(encrypt)
        self._query_runner = query_runner

    def get_tracking_card_info(self, card_no: str) -> CardInfo | None:
        normalized = tracking_card_lookup_key(card_no)
        rows = self._query('card_lookup', limit=1, tracking_card_no=normalized) if normalized else []
        for item in [_coil_snapshot_from_row(row) for row in rows] or self.list_dispatch(limit=200):
            if tracking_card_lookup_key(item.tracking_card_no) == normalized:
                return CardInfo(
                    card_no=item.tracking_card_no,
                    process_route_code=_text(_value(item.metadata, 'ProcessRoute', 'process_route_text')),
                    alloy_grade=_text(_value(item.metadata, 'AlloyGrade', 'Alloy', 'alloy_grade')),
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

    def get_daily_schedule(self, business_date: date, workshop: str) -> list[ScheduleItem]:
        _ = (business_date, workshop)
        return []

    def push_completion(self, card_no: str, output_weight: float | None, yield_rate: float | None) -> bool:
        _ = (card_no, output_weight, yield_rate)
        return False

    def list_follow_cards(self, *, limit: int = 200) -> list[CoilSnapshot]:
        return [_coil_snapshot_from_row(row) for row in self._query('follow_cards', limit=limit)]

    def list_dispatch(self, *, limit: int = 200) -> list[CoilSnapshot]:
        return [_coil_snapshot_from_row(row) for row in self._query('dispatch', limit=limit)]

    def list_wip_totals(self) -> list[MesWipTotal]:
        return [_wip_total_from_row(row) for row in self._query('wip_totals')]

    def list_stock(self, *, limit: int = 200) -> list[MesStockItem]:
        return [
            MesStockItem(
                coil_key=_record_id(row),
                tracking_card_no=_tracking_card_no(row),
                weight=_float(_value(row, 'Weight', 'NetWeight', 'GrossWeight', 'WeightTons')),
                destination=_text(_value(row, 'Destination', 'StockName', 'StatusName')),
                metadata=_safe_metadata(row),
            )
            for row in self._query('stock', limit=limit)
        ]

    def list_workshop_process_records(self, *, limit: int = 200) -> list[MesSourceRecord]:
        return [_source_record('workshop_process_records', row) for row in self._query('workshop_process_records', limit=limit)]

    def list_stock_records(self, *, limit: int = 200) -> list[MesSourceRecord]:
        return [_source_record('stock_records', row) for row in self._query('stock_records', limit=limit)]

    def list_material_records(self, *, limit: int = 200) -> list[MesSourceRecord]:
        return [_source_record('material_records', row) for row in self._query('material_records', limit=limit)]

    def list_yield_records(self, *, limit: int = 200) -> list[MesSourceRecord]:
        return [_source_record('yield_records', row) for row in self._query('yield_records', limit=limit)]

    def list_reference_items(self) -> list[MesSourceRecord]:
        rows = self._query('devices', limit=500)
        return [_source_record('devices', row) for row in rows]

    def list_machine_line_sources(self) -> list[MesMachineLineSource]:
        return [
            MesMachineLineSource(
                line_code=_record_id(row, 'DeviceCode', 'MachineCode'),
                line_name=_text(_value(row, 'DeviceName', 'MachineName', 'Name')) or '',
                workshop_name=_text(_value(row, 'WorkShop', 'WorkShopName', 'WorkshopName')),
                slot_no=_int(_value(row, 'SlotNo', 'SortNo')),
                metadata=_safe_metadata(row),
            )
            for row in self._query('devices', limit=500)
        ]

    def _query(self, query_key: str, *, limit: int = 200, tracking_card_no: str | None = None) -> list[Mapping[str, Any]]:
        bounded_limit = max(1, min(int(limit), 1000))
        if self._query_runner is not None:
            return self._query_runner(query_key, limit=bounded_limit, tracking_card_no=tracking_card_no)
        query_template = _QUERY_BY_KEY[query_key]
        query = query_template.format(limit=bounded_limit)
        params: tuple[Any, ...] = ()
        if query_key == 'card_lookup':
            if not tracking_card_no:
                return []
            params = (tracking_card_no,)
        return _run_pymssql_query(
            host=self._host,
            port=self._port,
            database=self._database,
            username=self._username,
            password=self._password,
            timeout_seconds=self._timeout_seconds,
            encrypt=self._encrypt,
            query=query,
            params=params,
        )


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


def inspect_sqlserver_metadata(
    *,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    timeout_seconds: float,
    encrypt: bool,
    table_limit: int = 30,
    column_limit: int = 40,
) -> dict[str, Any]:
    table_limit = max(1, min(int(table_limit), 100))
    column_limit = max(1, min(int(column_limit), 100))
    database_rows = _run_pymssql_query(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        timeout_seconds=timeout_seconds,
        encrypt=encrypt,
        query='SELECT DB_NAME() AS database_name',
    )
    table_rows = _run_pymssql_query(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        timeout_seconds=timeout_seconds,
        encrypt=encrypt,
        query=(
            f'SELECT TOP ({table_limit}) TABLE_SCHEMA AS [schema], TABLE_NAME AS [name], '
            "TABLE_TYPE AS [type] FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW') ORDER BY TABLE_SCHEMA, TABLE_NAME"
        ),
    )
    tables: list[dict[str, Any]] = []
    for table in table_rows:
        schema = _text(_value(table, 'schema')) or 'dbo'
        name = _text(_value(table, 'name')) or ''
        column_rows = _run_pymssql_query(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            timeout_seconds=timeout_seconds,
            encrypt=encrypt,
            query=(
                f'SELECT TOP ({column_limit}) COLUMN_NAME AS [name], DATA_TYPE AS data_type '
                'FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s '
                'ORDER BY ORDINAL_POSITION'
            ),
            params=(schema, name),
        )
        tables.append({
            'schema': schema,
            'name': name,
            'type': _text(_value(table, 'type')),
            'row_count_estimate': None,
            'columns': [
                {
                    'name': _text(_value(column, 'name')) or '',
                    'data_type': _text(_value(column, 'data_type')) or '',
                }
                for column in column_rows
            ],
        })
    return {
        'database_name': _text(_value(database_rows[0], 'database_name')) if database_rows else database,
        'tables': tables,
    }
