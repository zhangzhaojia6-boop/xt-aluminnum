from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import and_, inspect, or_
from sqlalchemy.orm import Session

from app.core.business_time import local_now, production_business_window
from app.domain.metric_contracts import DAILY_REPORT_METRIC_CONTRACT_VERSION
from app.models.mes import (
    MesCoilSnapshot,
    MesDailyWipSnapshot,
    MesMaterialRecord,
    MesStockRecord,
    MesSyncCursor,
    MesSyncRunLog,
    MesWipTotalSnapshot,
    MesWorkshopProcessRecord,
)
from app.services.report.mes_factory_production_fact import (
    FINISHED_INBOUND_DETAIL_SOURCE_PATH,
    FINISHED_INBOUND_HEADER_SOURCE_PATH,
)
from app.services.report.mes_workshop_mapping import resolve_mes_process_workshop_bucket


MATERIAL_INCLUDED_STATUSES = ("已使用", "未使用")
PROJECTION_METRIC_CONTRACT_VERSION = DAILY_REPORT_METRIC_CONTRACT_VERSION
PROJECTION_VALUE_TOLERANCE = Decimal("0.001")


@dataclass(frozen=True)
class ProjectionFactContract:
    source_ref: str
    source_types: frozenset[str]
    period: str
    query_kind: str
    workshop_tokens: tuple[str, ...] = ()
    buckets: tuple[str, ...] = ()
    expected_unit: str = "吨"
    metric_contract_version: str = PROJECTION_METRIC_CONTRACT_VERSION


@dataclass(frozen=True)
class ProjectionEvidence:
    value: float
    row_count: int
    latest_row_id: int
    business_window: str


PROJECTION_FACT_CONTRACTS: dict[str, ProjectionFactContract] = {}
for _daily_field, _monthly_field, _tokens in (
    ("hot_roll_daily", "hot_roll_month", ("热轧车间", "热轧")),
    ("cast_2_daily", "cast_2_month", ("铸二车间", "铸二", "铸轧二", "铸轧二车间", "铸轧2")),
    ("cast_3_daily", "cast_3_month", ("铸三车间", "铸三", "铸轧三", "铸轧三车间", "铸轧3")),
):
    PROJECTION_FACT_CONTRACTS[_daily_field] = ProjectionFactContract(
        source_ref=MesMaterialRecord.__tablename__,
        source_types=frozenset({"mes_material_records"}),
        period="daily",
        query_kind="material",
        workshop_tokens=_tokens,
    )
    PROJECTION_FACT_CONTRACTS[_monthly_field] = ProjectionFactContract(
        source_ref=MesMaterialRecord.__tablename__,
        source_types=frozenset({"mes_material_records"}),
        period="month",
        query_kind="material",
        workshop_tokens=_tokens,
    )

for _field, _period in (
    ("total_output_daily", "daily"),
    ("total_output_month", "month"),
):
    PROJECTION_FACT_CONTRACTS[_field] = ProjectionFactContract(
        source_ref=MesWorkshopProcessRecord.__tablename__,
        source_types=frozenset({"mes_packaging_output"}),
        period=_period,
        query_kind="packaging",
    )

for _daily_field, _monthly_field, _buckets in (
    ("foundry_daily", "foundry_month", ("铸锭",)),
    ("cold_1650_daily", "cold_1650_month", ("冷轧1650",)),
    ("cold_1850_daily", "cold_1850_month", ("冷轧1850",)),
    ("cold_2050_daily", "cold_2050_month", ("冷轧2050",)),
    ("online_anneal_daily", "online_anneal_month", ("新厂在线", "园区在线")),
    ("straightening_daily", "straightening_month", ("拉矫",)),
    ("finishing_daily", "finishing_month", ("精整",)),
    ("shearing_daily", "shearing_month", ("园区剪切",)),
    ("coating_daily", "coating_month", ("彩涂",)),
):
    PROJECTION_FACT_CONTRACTS[_daily_field] = ProjectionFactContract(
        source_ref=MesWorkshopProcessRecord.__tablename__,
        source_types=frozenset({"mes_workshop_process_records"}),
        period="daily",
        query_kind="workshop",
        buckets=_buckets,
    )
    PROJECTION_FACT_CONTRACTS[_monthly_field] = ProjectionFactContract(
        source_ref=MesWorkshopProcessRecord.__tablename__,
        source_types=frozenset({"mes_workshop_process_records"}),
        period="month",
        query_kind="workshop",
        buckets=_buckets,
    )

for _field, _period in (
    ("finished_inbound_daily", "daily"),
    ("finished_inbound_month", "month"),
):
    PROJECTION_FACT_CONTRACTS[_field] = ProjectionFactContract(
        source_ref=MesStockRecord.__tablename__,
        source_types=frozenset({"mes_stock_header_records", "mes_stock_records"}),
        period=_period,
        query_kind="finished_inbound",
    )

WIP_FIELDS = (
    "wip_1650_2050_cold",
    "wip_1850_cold",
    "wip_milling",
    "wip_new_north",
    "wip_new_south",
    "wip_park_anneal",
    "wip_straightening",
    "wip_finishing",
    "wip_park_finishing",
    "wip_hot_plate_shearing",
    "wip_coating",
    "wip_anneal_total",
    "wip_finishing_total",
    "wip_total",
)
WIP_SOURCE_CONTRACTS = {
    "mes_coil_snapshot_business_date": MesCoilSnapshot.__tablename__,
    "mes_daily_wip_snapshot": MesDailyWipSnapshot.__tablename__,
    "mes_wip_total_snapshot": MesWipTotalSnapshot.__tablename__,
}
WIP_PROJECTION_FACT_CONTRACTS: dict[tuple[str, str], ProjectionFactContract] = {}
for _field in WIP_FIELDS:
    for _source_type, _source_ref in WIP_SOURCE_CONTRACTS.items():
        WIP_PROJECTION_FACT_CONTRACTS[(_field, _source_ref)] = ProjectionFactContract(
            source_ref=_source_ref,
            source_types=frozenset({_source_type}),
            period="daily",
            query_kind="wip",
        )


SOURCE_TABLE_BY_TYPE = {
    "mes_material_records": "MES_Material",
    "mes_packaging_output": "MES_ProductProcessRecord",
    "mes_workshop_process_records": "MES_ProductProcessRecord",
    "mes_stock_header_records": "WMS_InStock",
    "mes_stock_records": "WMS_InStockDetail",
}


SYNC_FACT_CONTRACTS = {
    ("total_output_daily", "MES_ProductProcessRecord"): frozenset({
        "mes_workshop_process_records",
        "mes_workshop_process_records_between",
    }),
    ("total_output_daily", "mes_workshop_process_records"): frozenset({
        "mes_workshop_process_records",
        "mes_workshop_process_records_between",
    }),
}


class DailyFactEvidenceVerifier:
    def __init__(self, db: Session, *, business_date: date) -> None:
        self.db = db
        self.business_date = business_date
        self._table_cache: dict[str, bool] = {}
        self._dataset_cache: dict[str, list[Any]] = {}
        self._projection_cache: dict[tuple[Any, ...], bool] = {}
        self._run_cache: dict[int, MesSyncRunLog | None] = {}
        self._cursor_cache: dict[str, MesSyncCursor | None] = {}
        self._sync_cache: dict[tuple[Any, ...], bool] = {}

    def verify_projection(
        self,
        *,
        field_name: str,
        source_type: str,
        fact_value: Any,
        source_detail: Mapping[str, Any],
    ) -> bool:
        source_ref = str(source_detail.get("source_ref") or "").strip()
        contract = PROJECTION_FACT_CONTRACTS.get(field_name) or WIP_PROJECTION_FACT_CONTRACTS.get(
            (field_name, source_ref)
        )
        claimed_anchor = source_detail.get("latest_row_id")
        cache_key = (
            field_name,
            source_ref,
            source_type,
            self.business_date,
            claimed_anchor,
            source_detail.get("row_count"),
            source_detail.get("business_window"),
            source_detail.get("source_table"),
            source_detail.get("unit"),
            source_detail.get("metric_contract_version"),
            source_detail.get("trace_id"),
            fact_value,
        )
        if cache_key in self._projection_cache:
            return self._projection_cache[cache_key]
        verified = self._verify_projection_uncached(
            contract=contract,
            source_ref=source_ref,
            source_type=source_type,
            field_name=field_name,
            fact_value=fact_value,
            source_detail=source_detail,
        )
        self._projection_cache[cache_key] = verified
        return verified

    def verify_sync(
        self,
        *,
        field_name: str,
        source_type: str,
        source_ref: str,
        sync_run_id: Any,
        cursor_key: Any,
        trace_id: Any,
        window_start: datetime | None,
        window_end: datetime | None,
    ) -> bool:
        try:
            normalized_id = int(sync_run_id)
        except (TypeError, ValueError):
            return False
        normalized_cursor_key = str(cursor_key or "").strip()
        cache_key = (
            field_name,
            source_ref,
            source_type,
            normalized_cursor_key,
            normalized_id,
            trace_id,
            window_start,
            window_end,
        )
        if cache_key in self._sync_cache:
            return self._sync_cache[cache_key]
        verified = self._verify_sync_uncached(
            field_name=field_name,
            source_type=source_type,
            source_ref=source_ref,
            normalized_id=normalized_id,
            cursor_key=normalized_cursor_key,
            trace_id=trace_id,
            window_start=window_start,
            window_end=window_end,
        )
        self._sync_cache[cache_key] = verified
        return verified

    def _verify_projection_uncached(
        self,
        *,
        contract: ProjectionFactContract | None,
        source_ref: str,
        source_type: str,
        field_name: str,
        fact_value: Any,
        source_detail: Mapping[str, Any],
    ) -> bool:
        if (
            contract is None
            or source_ref != contract.source_ref
            or source_type not in contract.source_types
            or source_detail.get("unit") != contract.expected_unit
            or source_detail.get("metric_contract_version") != contract.metric_contract_version
            or not self._has_table(source_ref)
        ):
            return False
        expected_source_table = SOURCE_TABLE_BY_TYPE.get(source_type)
        if expected_source_table and source_detail.get("source_table") != expected_source_table:
            return False
        trace = _parse_projection_trace(source_detail.get("trace_id"))
        if trace is None:
            return False
        trace_source_ref, trace_anchor, trace_count = trace
        try:
            claimed_count = int(source_detail.get("row_count"))
            claimed_anchor = int(source_detail.get("latest_row_id"))
            claimed_value = Decimal(str(fact_value))
        except (InvalidOperation, TypeError, ValueError):
            return False
        if not claimed_value.is_finite():
            return False
        actual = self._projection_evidence(
            contract=contract,
            field_name=field_name,
            source_type=source_type,
        )
        if actual is None:
            return False
        if contract.query_kind == "wip":
            expected_wip_date = self.business_date + timedelta(days=1)
            if source_detail.get("business_date") != expected_wip_date.isoformat():
                return False
        actual_value = Decimal(str(actual.value))
        return bool(
            trace_source_ref == source_ref
            and trace_count == claimed_count == actual.row_count
            and trace_anchor == str(claimed_anchor) == str(actual.latest_row_id)
            and str(source_detail.get("business_window") or "") == actual.business_window
            and abs(claimed_value - actual_value) <= PROJECTION_VALUE_TOLERANCE
        )

    def _projection_evidence(
        self,
        *,
        contract: ProjectionFactContract,
        field_name: str,
        source_type: str,
    ) -> ProjectionEvidence | None:
        if contract.query_kind == "material":
            return self._material_evidence(contract)
        if contract.query_kind in {"packaging", "workshop"}:
            return self._process_evidence(contract)
        if contract.query_kind == "finished_inbound":
            return self._finished_inbound_evidence(contract, source_type=source_type)
        if contract.query_kind == "wip":
            return self._wip_evidence(contract, field_name=field_name)
        return None

    def _material_evidence(self, contract: ProjectionFactContract) -> ProjectionEvidence | None:
        rows = self._material_rows()
        if contract.period == "month":
            start = self.business_date.replace(day=1)
        else:
            start = self.business_date
        end = self.business_date
        business_rows = [
            row
            for row in rows
            if row.business_date is not None and start <= row.business_date <= end
        ]
        if business_rows:
            candidates = business_rows
            prefer_explicit_status = False
        else:
            window_start = datetime.combine(start, time(10, 0))
            window_end = datetime.combine(end + timedelta(days=1), time(10, 0))
            candidates = [
                row
                for row in rows
                if row.production_date is not None and window_start <= row.production_date < window_end
            ]
            prefer_explicit_status = True
        matched = [
            row
            for row in candidates
            if any(token in str(row.workshop_name or "") for token in contract.workshop_tokens)
            and _material_weight_tons(row) > 0
        ]
        require_explicit_status = prefer_explicit_status and any(_material_status(row) for row in matched)
        selected = [
            row
            for row in matched
            if (not require_explicit_status or _material_status(row))
            and _material_status_counts(row)
        ]
        if not selected:
            return None
        total = round(sum(_material_weight_tons(row) for row in selected), 3)
        latest_row_id = max(int(row.id) for row in selected if row.id is not None)
        start_at, _ = production_business_window(start, workshop_name=contract.workshop_tokens[0])
        _, end_at = production_business_window(end, workshop_name=contract.workshop_tokens[0])
        return ProjectionEvidence(
            value=total,
            row_count=len(selected),
            latest_row_id=latest_row_id,
            business_window=f"{start_at.isoformat()}/{end_at.isoformat()}",
        )

    def _material_rows(self) -> list[MesMaterialRecord]:
        cache_key = MesMaterialRecord.__tablename__
        if cache_key not in self._dataset_cache:
            month_start = self.business_date.replace(day=1)
            time_start = datetime.combine(month_start, time(10, 0))
            time_end = datetime.combine(self.business_date + timedelta(days=1), time(10, 0))
            self._dataset_cache[cache_key] = (
                self.db.query(MesMaterialRecord)
                .filter(
                    or_(
                        MesMaterialRecord.business_date.between(month_start, self.business_date),
                        and_(
                            MesMaterialRecord.production_date >= time_start,
                            MesMaterialRecord.production_date < time_end,
                        ),
                    )
                )
                .order_by(MesMaterialRecord.id.asc())
                .all()
            )
        return self._dataset_cache[cache_key]

    def _process_evidence(self, contract: ProjectionFactContract) -> ProjectionEvidence | None:
        rows = self._workshop_process_rows()
        start = self.business_date.replace(day=1) if contract.period == "month" else self.business_date
        candidates = [
            row
            for row in rows
            if row.business_date is not None and start <= row.business_date <= self.business_date
        ]
        if contract.query_kind == "packaging":
            selected = [
                row
                for row in candidates
                if "包装" in str(row.process_name or "") and _process_weight_tons(row) > 0
            ]
        else:
            selected = [
                row
                for row in candidates
                if resolve_mes_process_workshop_bucket(
                    row.workshop_name,
                    row.process_name,
                    row.device_name,
                ) in contract.buckets
                and _process_weight_tons(row) > 0
            ]
        return _rows_evidence(
            selected,
            value=sum(_process_weight_tons(row) for row in selected),
            window=_business_window(start, self.business_date),
        )

    def _workshop_process_rows(self) -> list[MesWorkshopProcessRecord]:
        cache_key = MesWorkshopProcessRecord.__tablename__
        if cache_key not in self._dataset_cache:
            month_start = self.business_date.replace(day=1)
            self._dataset_cache[cache_key] = (
                self.db.query(MesWorkshopProcessRecord)
                .filter(
                    MesWorkshopProcessRecord.business_date >= month_start,
                    MesWorkshopProcessRecord.business_date <= self.business_date,
                )
                .order_by(MesWorkshopProcessRecord.id.asc())
                .all()
            )
        return self._dataset_cache[cache_key]

    def _finished_inbound_evidence(
        self,
        contract: ProjectionFactContract,
        *,
        source_type: str,
    ) -> ProjectionEvidence | None:
        start = self.business_date.replace(day=1) if contract.period == "month" else self.business_date
        candidates = [
            row
            for row in self._stock_rows()
            if row.business_date is not None and start <= row.business_date <= self.business_date
        ]
        by_date: dict[date, list[MesStockRecord]] = {}
        for row in candidates:
            by_date.setdefault(row.business_date, []).append(row)
        selected: list[MesStockRecord] = []
        for rows in by_date.values():
            headers = [row for row in rows if row.source_path == "sqlserver:stock_header_records"]
            selected.extend(headers or rows)
        selected = [row for row in selected if _stock_weight_tons(row) > 0]
        if contract.period == "daily" and selected:
            expected_type = (
                "mes_stock_header_records"
                if all(row.source_path == "sqlserver:stock_header_records" for row in selected)
                else "mes_stock_records"
            )
            if source_type != expected_type:
                return None
        return _rows_evidence(
            selected,
            value=sum(_stock_weight_tons(row) for row in selected),
            window=_business_window(start, self.business_date),
        )

    def _stock_rows(self) -> list[MesStockRecord]:
        cache_key = MesStockRecord.__tablename__
        if cache_key not in self._dataset_cache:
            month_start = self.business_date.replace(day=1)
            self._dataset_cache[cache_key] = (
                self.db.query(MesStockRecord)
                .filter(
                    MesStockRecord.business_date >= month_start,
                    MesStockRecord.business_date <= self.business_date,
                    MesStockRecord.source_path.in_(
                        (
                            FINISHED_INBOUND_HEADER_SOURCE_PATH,
                            FINISHED_INBOUND_DETAIL_SOURCE_PATH,
                        )
                    ),
                )
                .order_by(MesStockRecord.id.asc())
                .all()
            )
        return self._dataset_cache[cache_key]

    def _wip_evidence(
        self,
        contract: ProjectionFactContract,
        *,
        field_name: str,
    ) -> ProjectionEvidence | None:
        rows = self._wip_rows(contract.source_ref)
        buckets = _wip_field_buckets(field_name)
        selected = [
            row
            for row in rows
            if _wip_bucket_for_row(row) in buckets and _wip_weight_tons(row) > 0
        ]
        if not selected:
            return None
        snapshot_at = max(_wip_snapshot_at(row) for row in selected)
        snapshot_text = local_now(snapshot_at).isoformat()
        return _rows_evidence(
            selected,
            value=sum(_wip_weight_tons(row) for row in selected),
            window=f"{snapshot_text}/{snapshot_text}",
        )

    def _wip_rows(self, source_ref: str) -> list[Any]:
        if source_ref in self._dataset_cache:
            return self._dataset_cache[source_ref]
        wip_date = self.business_date + timedelta(days=1)
        if source_ref == MesCoilSnapshot.__tablename__:
            query = self.db.query(MesCoilSnapshot).filter(
                MesCoilSnapshot.business_date == wip_date,
                MesCoilSnapshot.delivery_date.is_(None),
                MesCoilSnapshot.allocation_date.is_(None),
                MesCoilSnapshot.in_stock_date.is_(None),
                or_(MesCoilSnapshot.status_name.is_(None), MesCoilSnapshot.status_name != "已入库"),
                or_(
                    and_(MesCoilSnapshot.current_process.isnot(None), MesCoilSnapshot.current_process != ""),
                    and_(MesCoilSnapshot.next_process.isnot(None), MesCoilSnapshot.next_process != ""),
                ),
            )
            model = MesCoilSnapshot
        elif source_ref == MesDailyWipSnapshot.__tablename__:
            query = self.db.query(MesDailyWipSnapshot).filter(
                MesDailyWipSnapshot.business_date == wip_date,
                or_(
                    MesDailyWipSnapshot.source.is_(None),
                    MesDailyWipSnapshot.source != "output_skill_daily_report",
                ),
            )
            model = MesDailyWipSnapshot
        elif source_ref == MesWipTotalSnapshot.__tablename__:
            window_start, window_end = production_business_window(wip_date)
            query = self.db.query(MesWipTotalSnapshot).filter(
                MesWipTotalSnapshot.snapshot_at >= window_start,
                MesWipTotalSnapshot.snapshot_at < window_end,
            )
            model = MesWipTotalSnapshot
        else:
            return []
        self._dataset_cache[source_ref] = query.order_by(model.id.asc()).all()
        return self._dataset_cache[source_ref]

    def _verify_sync_uncached(
        self,
        *,
        field_name: str,
        source_type: str,
        source_ref: str,
        normalized_id: int,
        cursor_key: str,
        trace_id: Any,
        window_start: datetime | None,
        window_end: datetime | None,
    ) -> bool:
        allowed_cursors = SYNC_FACT_CONTRACTS.get((field_name, source_ref), frozenset())
        if (
            not (source_type == "mes_verified" or source_type.startswith("mes_"))
            or cursor_key not in allowed_cursors
            or str(trace_id or "").strip() != f"mes-sync-run:{normalized_id}"
            or window_start is None
            or window_end is None
            or not self._has_table(MesSyncRunLog.__tablename__)
            or not self._has_table(MesSyncCursor.__tablename__)
        ):
            return False
        run = self._sync_run(normalized_id)
        cursor = self._sync_cursor(cursor_key)
        if (
            run is None
            or cursor is None
            or run.cursor_key != cursor_key
            or run.status != "success"
            or run.finished_at is None
            or int(run.fetched_count or 0) <= 0
            or cursor.last_synced_at is None
        ):
            return False
        metadata = run.metadata_json if isinstance(run.metadata_json, dict) else {}
        coverage_start = _parse_datetime(metadata.get("window_started_at"))
        if coverage_start is None:
            return False
        finished_at = local_now(run.finished_at)
        cursor_synced_at = local_now(cursor.last_synced_at)
        normalized_window_start = window_start.astimezone(coverage_start.tzinfo)
        return bool(
            coverage_start <= normalized_window_start
            and finished_at >= window_end.astimezone(finished_at.tzinfo)
            and cursor_synced_at >= window_end.astimezone(cursor_synced_at.tzinfo)
            and cursor_synced_at <= finished_at.astimezone(cursor_synced_at.tzinfo)
        )

    def _has_table(self, table_name: str) -> bool:
        if table_name not in self._table_cache:
            self._table_cache[table_name] = inspect(self.db.connection()).has_table(table_name)
        return self._table_cache[table_name]

    def _sync_run(self, run_id: int) -> MesSyncRunLog | None:
        if run_id not in self._run_cache:
            self._run_cache[run_id] = (
                self.db.query(MesSyncRunLog)
                .filter(MesSyncRunLog.id == run_id)
                .one_or_none()
            )
        return self._run_cache[run_id]

    def _sync_cursor(self, cursor_key: str) -> MesSyncCursor | None:
        if cursor_key not in self._cursor_cache:
            self._cursor_cache[cursor_key] = (
                self.db.query(MesSyncCursor)
                .filter(MesSyncCursor.cursor_key == cursor_key)
                .one_or_none()
            )
        return self._cursor_cache[cursor_key]


def _parse_projection_trace(value: Any) -> tuple[str, str, int] | None:
    trace_id = str(value or "").strip()
    prefix = "projection-read:"
    if not trace_id.startswith(prefix):
        return None
    try:
        source_ref, tail = trace_id[len(prefix):].split(":", 1)
        anchor, row_count = tail.rsplit(":", 1)
        return source_ref, anchor, int(row_count)
    except (TypeError, ValueError):
        return None


def _material_weight_tons(row: MesMaterialRecord) -> float:
    direct = float(row.weight_tons or 0)
    if direct > 0:
        return direct
    return float(row.weight_kg or 0) / 1000


def _material_status(row: MesMaterialRecord) -> str:
    payload = row.source_payload if isinstance(row.source_payload, dict) else {}
    return str(row.status_name or payload.get("StatusName") or payload.get("Status") or "").strip()


def _material_status_counts(row: MesMaterialRecord) -> bool:
    status = _material_status(row)
    return not status or any(token in status for token in MATERIAL_INCLUDED_STATUSES)


def _process_weight_tons(row: MesWorkshopProcessRecord) -> float:
    direct = float(row.output_weight_tons or 0)
    if direct > 0:
        return direct
    return float(row.output_weight_kg or 0) / 1000


def _stock_weight_tons(row: MesStockRecord) -> float:
    direct = float(row.net_weight_tons or 0)
    if direct > 0:
        return direct
    return float(row.net_weight_kg or 0) / 1000


def _business_window(start: date, end: date) -> str:
    start_at, _unused = production_business_window(start)
    _unused, end_at = production_business_window(end)
    return f"{start_at.isoformat()}/{end_at.isoformat()}"


def _rows_evidence(
    rows: list[Any],
    *,
    value: float,
    window: str,
) -> ProjectionEvidence | None:
    if not rows:
        return None
    return ProjectionEvidence(
        value=round(value, 3),
        row_count=len(rows),
        latest_row_id=max(int(row.id) for row in rows if row.id is not None),
        business_window=window,
    )


def _wip_field_buckets(field_name: str) -> set[str]:
    base = set(WIP_FIELDS) - {"wip_anneal_total", "wip_finishing_total", "wip_total"}
    if field_name == "wip_total":
        return base
    if field_name == "wip_anneal_total":
        return {"wip_new_north", "wip_new_south", "wip_park_anneal"}
    if field_name == "wip_finishing_total":
        return {"wip_straightening", "wip_finishing", "wip_park_finishing"}
    return {field_name} if field_name in base else set()


def _wip_bucket(workshop_name: Any, process_name: Any) -> str | None:
    workshop = str(workshop_name or "")
    process = str(process_name or "")
    text = f"{workshop} {process}"
    if "园区在线" in workshop:
        return "wip_park_anneal"
    if "北线" in process and "园区" not in workshop:
        return "wip_new_north"
    if "南线" in process and "园区" not in workshop:
        return "wip_new_south"
    if ("1650" in workshop or "2050" in workshop) and "冷轧" in process:
        return "wip_1650_2050_cold"
    if "1850" in workshop and "冷轧" in process:
        return "wip_1850_cold"
    if "铣床" in text:
        return "wip_milling"
    if "拉矫" in workshop:
        return "wip_straightening"
    if workshop.strip() == "精整":
        return "wip_finishing"
    if "园区精整" in workshop:
        return "wip_park_finishing"
    if "热轧" in workshop and "中厚板剪切" in process:
        return "wip_hot_plate_shearing"
    if "彩涂" in workshop:
        return "wip_coating"
    return None


def _wip_bucket_for_row(row: Any) -> str | None:
    if isinstance(row, MesCoilSnapshot):
        workshop = row.current_workshop or row.workshop_code or row.next_process
        process = row.current_process or row.next_process
    else:
        workshop = row.workshop_name
        process = row.process_name
    return _wip_bucket(workshop, process)


def _wip_weight_tons(row: Any) -> float:
    if isinstance(row, MesCoilSnapshot):
        return float(row.material_weight or 0) / 1000
    value = (
        row.material_weight_tons
        if isinstance(row, MesDailyWipSnapshot)
        else row.doing_weight_tons
    )
    parsed = float(value or 0)
    return parsed / 1000 if parsed > 1000 else parsed


def _wip_snapshot_at(row: Any) -> datetime:
    return row.last_synced_at if isinstance(row, MesCoilSnapshot) else row.snapshot_at


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value or ""))
        except ValueError:
            return None
    return local_now(parsed)
