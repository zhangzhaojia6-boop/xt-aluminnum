from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from sqlalchemy.orm import Session

from app.models.master import Workshop
from app.models.imports import ImportBatch, ImportRow
from app.models.production import WorkOrderEntry


CONTRACT_FIELD_ORDER = [
    'business_date',
    'source_batch_id',
    'sheet_name',
    'delivery_scope',
    'daily_contract_weight',
    'month_to_date_contract_weight',
    'daily_input_weight',
    'month_to_date_input_weight',
    'lineage_hash',
    'quality_status',
]

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    'daily_contract_weight': ('当日合同', '今日合同', '日合同', '合同量', '当天合同'),
    'month_to_date_contract_weight': ('月累计合同', '本月累计合同', '累计合同', '合同累计'),
    'daily_input_weight': ('当日投料', '今日投料', '日投料', '投料量', '投料'),
    'month_to_date_input_weight': ('月累计投料', '本月累计投料', '累计投料', '坯总量', '月坯总量'),
}

WORKSHOP_SCOPE_HINTS: dict[str, tuple[str, ...]] = {
    'foundry': ('铸锭', '熔铸'),
    'cold_roll': ('冷轧',),
    'finishing': ('精整',),
    'stretch': ('拉矫',),
    'park_cutting': ('园区剪切', '飞剪', '剪切'),
}


@dataclass(slots=True)
class ContractDailySnapshot:
    business_date: date | None
    source_batch_id: int | None
    sheet_name: str
    delivery_scope: str
    daily_contract_weight: float | None
    month_to_date_contract_weight: float | None
    daily_input_weight: float | None
    month_to_date_input_weight: float | None
    lineage_hash: str
    quality_status: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['business_date'] = self.business_date.isoformat() if self.business_date else None
        return payload


@dataclass(slots=True)
class ParsedContractSheet:
    sheet_name: str
    business_date: date | None
    delivery_scope: str
    mapped_data: dict[str, Any]
    raw_data: dict[str, Any]
    status: str
    error_msg: str | None


def contract_row_summary_fields() -> list[str]:
    return list(CONTRACT_FIELD_ORDER)


def _normalize_text(value: Any) -> str:
    text = str(value or '').strip()
    return text.replace('\n', ' ').replace('\r', ' ')


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return None if pd.isna(number) else number
    text = _normalize_text(value).replace(',', '')
    if not text:
        return None
    if text.endswith('%'):
        text = text[:-1]
    match = re.search(r'-?\d+(?:\.\d+)?', text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _extract_row_value(cells: Iterable[Any], aliases: tuple[str, ...]) -> float | None:
    values = list(cells)
    normalized_row = ' '.join(_normalize_text(item) for item in values)
    if not normalized_row:
        return None
    if not any(alias in normalized_row for alias in aliases):
        return None

    numeric_candidates: list[float] = []
    for cell in values:
        value = _parse_float(cell)
        if value is not None:
            numeric_candidates.append(value)
    if numeric_candidates:
        return numeric_candidates[-1]
    return None


def _detect_business_date(sheet_name: str, frame: pd.DataFrame, *, year_hint: int | None) -> date | None:
    candidates = [_normalize_text(sheet_name)]
    for value in frame.head(4).fillna('').astype(str).values.flatten().tolist():
        text = _normalize_text(value)
        if text:
            candidates.append(text)

    year = year_hint or datetime.now(UTC).year
    for text in candidates:
        match = re.search(r'(?:(\d{4})[-/.年])?(\d{1,2})[-/.月](\d{1,2})', text)
        if not match:
            continue
        parsed_year = int(match.group(1) or year)
        month = int(match.group(2))
        day = int(match.group(3))
        try:
            return date(parsed_year, month, day)
        except ValueError:
            continue
    return None


def normalize_delivery_scope(sheet_name: str, frame: pd.DataFrame | None = None) -> str:
    tokens = [_normalize_text(sheet_name)]
    if frame is not None:
        tokens.extend(_normalize_text(value) for value in frame.head(3).fillna('').astype(str).values.flatten().tolist())
    text = ' '.join(token for token in tokens if token)
    for code, aliases in WORKSHOP_SCOPE_HINTS.items():
        if any(alias in text for alias in aliases):
            return f'workshop:{code}'
    return 'factory'


def _quality_status(values: dict[str, float | None]) -> str:
    filled = sum(1 for item in values.values() if item is not None)
    if filled == len(values):
        return 'ready'
    if filled >= 2:
        return 'warning'
    return 'blocked'


def _build_lineage_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def parse_contract_sheet(
    sheet_name: str,
    frame: pd.DataFrame,
    *,
    source_batch_id: int | None = None,
    year_hint: int | None = None,
) -> ParsedContractSheet:
    metric_values = {
        field_name: None
        for field_name in (
            'daily_contract_weight',
            'month_to_date_contract_weight',
            'daily_input_weight',
            'month_to_date_input_weight',
        )
    }

    for row in frame.fillna('').values.tolist():
        for field_name, aliases in FIELD_ALIASES.items():
            if metric_values[field_name] is not None:
                continue
            metric_values[field_name] = _extract_row_value(row, aliases)

    business_date = _detect_business_date(sheet_name, frame, year_hint=year_hint)
    delivery_scope = normalize_delivery_scope(sheet_name, frame)
    draft_payload = {
        'business_date': business_date.isoformat() if business_date else None,
        'source_batch_id': source_batch_id,
        'sheet_name': str(sheet_name),
        'delivery_scope': delivery_scope,
        **metric_values,
    }
    mapped_data = {
        **draft_payload,
        'lineage_hash': _build_lineage_hash(draft_payload),
        'quality_status': _quality_status(metric_values),
    }
    raw_data = {
        'sheet_name': str(sheet_name),
        'preview_rows': frame.head(6).fillna('').astype(str).values.tolist(),
    }
    status = 'success' if mapped_data['quality_status'] != 'blocked' else 'failed'
    error_msg = None if status == 'success' else '合同表未识别出足够字段，请检查表头或样本格式。'
    return ParsedContractSheet(
        sheet_name=str(sheet_name),
        business_date=business_date,
        delivery_scope=delivery_scope,
        mapped_data=mapped_data,
        raw_data=raw_data,
        status=status,
        error_msg=error_msg,
    )


def parse_contract_workbook(
    path: str | Path,
    *,
    source_batch_id: int | None = None,
    year_hint: int | None = None,
) -> list[ParsedContractSheet]:
    workbook_path = Path(path)
    engine = 'openpyxl' if workbook_path.suffix.lower() == '.xlsx' else 'xlrd'
    excel = pd.ExcelFile(workbook_path, engine=engine)
    parsed_rows: list[ParsedContractSheet] = []
    for sheet_name in excel.sheet_names:
        frame = pd.read_excel(workbook_path, sheet_name=sheet_name, header=None, engine=engine)
        parsed_rows.append(
            parse_contract_sheet(
                str(sheet_name),
                frame,
                source_batch_id=source_batch_id,
                year_hint=year_hint,
            )
        )
    return parsed_rows


def build_contract_daily_snapshot(mapped_data: dict[str, Any]) -> ContractDailySnapshot | None:
    if not isinstance(mapped_data, dict):
        return None
    business_date_value = mapped_data.get('business_date')
    snapshot_date = None
    if business_date_value:
        try:
            snapshot_date = date.fromisoformat(str(business_date_value))
        except ValueError:
            snapshot_date = None
    payload = {
        'business_date': mapped_data.get('business_date'),
        'source_batch_id': mapped_data.get('source_batch_id'),
        'sheet_name': mapped_data.get('sheet_name'),
        'delivery_scope': mapped_data.get('delivery_scope') or 'factory',
        'daily_contract_weight': mapped_data.get('daily_contract_weight'),
        'month_to_date_contract_weight': mapped_data.get('month_to_date_contract_weight'),
        'daily_input_weight': mapped_data.get('daily_input_weight'),
        'month_to_date_input_weight': mapped_data.get('month_to_date_input_weight'),
    }
    if not payload['sheet_name']:
        return None
    return ContractDailySnapshot(
        business_date=snapshot_date,
        source_batch_id=_coerce_int(mapped_data.get('source_batch_id')),
        sheet_name=str(payload['sheet_name']),
        delivery_scope=str(payload['delivery_scope']),
        daily_contract_weight=_parse_float(payload['daily_contract_weight']),
        month_to_date_contract_weight=_parse_float(payload['month_to_date_contract_weight']),
        daily_input_weight=_parse_float(payload['daily_input_weight']),
        month_to_date_input_weight=_parse_float(payload['month_to_date_input_weight']),
        lineage_hash=str(mapped_data.get('lineage_hash') or _build_lineage_hash(payload)),
        quality_status=str(mapped_data.get('quality_status') or 'warning'),
    )


def _coerce_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_contract_snapshots(db: Session, *, target_date: date | None = None) -> list[ContractDailySnapshot]:
    batches = db.query(ImportBatch).filter(ImportBatch.import_type == 'contract_report').order_by(ImportBatch.id.desc()).all()
    snapshots: list[ContractDailySnapshot] = []
    seen_keys: set[tuple[str | None, str]] = set()
    for batch in batches:
        rows = db.query(ImportRow).filter(ImportRow.batch_id == batch.id).order_by(ImportRow.row_number.asc()).all()
        for row in rows:
            snapshot = build_contract_daily_snapshot(row.mapped_data or {})
            if snapshot is None:
                continue
            if target_date is not None and snapshot.business_date != target_date:
                continue
            key = (
                snapshot.business_date.isoformat() if snapshot.business_date else None,
                snapshot.sheet_name,
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            snapshots.append(snapshot)
    snapshots.sort(key=lambda item: ((item.business_date or date.min).isoformat(), item.sheet_name))
    return snapshots


def _load_owner_entry_contract_snapshots(db: Session, *, target_date: date) -> list[ContractDailySnapshot]:
    rows = (
        db.query(WorkOrderEntry, Workshop)
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .filter(
            WorkOrderEntry.business_date == target_date,
            WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
            Workshop.workshop_type == 'inventory',
        )
        .all()
    )
    snapshots: list[ContractDailySnapshot] = []
    for entry, workshop in rows:
        payload = dict(entry.extra_payload or {})
        if not any(
            payload.get(field_name) is not None
            for field_name in (
                'daily_contract_weight',
                'month_to_date_contract_weight',
                'daily_input_weight',
                'month_to_date_input_weight',
            )
        ):
            continue
        snapshot_payload = {
            'business_date': target_date.isoformat(),
            'source_batch_id': None,
            'sheet_name': f'{workshop.name}岗位补录',
            'delivery_scope': 'factory',
            'daily_contract_weight': payload.get('daily_contract_weight'),
            'month_to_date_contract_weight': payload.get('month_to_date_contract_weight'),
            'daily_input_weight': payload.get('daily_input_weight'),
            'month_to_date_input_weight': payload.get('month_to_date_input_weight'),
        }
        snapshots.append(
            ContractDailySnapshot(
                business_date=target_date,
                source_batch_id=None,
                sheet_name=str(snapshot_payload['sheet_name']),
                delivery_scope='factory',
                daily_contract_weight=_parse_float(snapshot_payload['daily_contract_weight']),
                month_to_date_contract_weight=_parse_float(snapshot_payload['month_to_date_contract_weight']),
                daily_input_weight=_parse_float(snapshot_payload['daily_input_weight']),
                month_to_date_input_weight=_parse_float(snapshot_payload['month_to_date_input_weight']),
                lineage_hash=_build_lineage_hash(snapshot_payload),
                quality_status='owner_only',
            )
        )
    return snapshots


def build_contract_projection(db: Session, *, target_date: date) -> dict[str, Any]:
    snapshots = load_contract_snapshots(db, target_date=target_date)
    owner_entry_snapshots = _load_owner_entry_contract_snapshots(db, target_date=target_date)
    if owner_entry_snapshots:
        snapshots = owner_entry_snapshots
    delivery_scopes = sorted({item.delivery_scope for item in snapshots if item.delivery_scope})
    projection = {
        'business_date': target_date.isoformat(),
        'snapshot_count': 0 if owner_entry_snapshots else len(snapshots),
        'owner_entry_count': len(owner_entry_snapshots),
        'delivery_scopes': delivery_scopes,
        'daily_contract_weight': round(sum(item.daily_contract_weight or 0.0 for item in snapshots), 3),
        'month_to_date_contract_weight': round(sum(item.month_to_date_contract_weight or 0.0 for item in snapshots), 3),
        'daily_input_weight': round(sum(item.daily_input_weight or 0.0 for item in snapshots), 3),
        'month_to_date_input_weight': round(sum(item.month_to_date_input_weight or 0.0 for item in snapshots), 3),
        'quality_status': 'owner_only' if owner_entry_snapshots else 'ready',
        'items': [item.to_dict() for item in snapshots],
    }
    if any(item.quality_status == 'blocked' for item in snapshots):
        projection['quality_status'] = 'blocked'
    elif any(item.quality_status == 'warning' for item in snapshots):
        projection['quality_status'] = 'warning'
    if not snapshots:
        projection['quality_status'] = 'missing'
    return projection
