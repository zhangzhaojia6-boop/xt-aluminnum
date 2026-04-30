from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import importlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.imports import ImportBatch, ImportRow


YIELD_MATRIX_FIELD_ORDER = [
    'business_date',
    'source_batch_id',
    'sheet_name',
    'delivery_scope',
    'workshop_yields',
    'mp_targets',
    'company_total_yield',
    'lineage_hash',
    'quality_status',
]

WORKSHOP_ALIASES: dict[str, tuple[str, ...]] = {
    'cold_roll_1450': ('1450', '1450冷轧', '1450车间'),
    'cold_roll_1650_2050': ('1650+2050', '1650 / 2050', '2050', '2050冷轧', '2050车间'),
    'cold_roll_1850': ('1850', '1850冷轧', '1850车间'),
    'stretch': ('拉矫',),
    'finishing': ('精整',),
    'park_cutting': ('园区飞剪', '飞剪', '园区剪切', '剪切'),
}

YIELD_METRIC_ALIASES = ('成品率', '成材率')
COMPANY_ALIASES = ('公司', '公司总成品率', '总成品率', '公司总率')
M_ALIASES = ('m', 'm值', 'm指标', 'm率')
P_ALIASES = ('p', 'p值', 'p指标', 'p率')


@dataclass(slots=True)
class YieldMatrixSnapshot:
    business_date: date | None
    source_batch_id: int | None
    sheet_name: str
    delivery_scope: str
    workshop_yields: dict[str, float]
    mp_targets: dict[str, float]
    company_total_yield: float | None
    lineage_hash: str
    quality_status: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['business_date'] = self.business_date.isoformat() if self.business_date else None
        return payload


@dataclass(slots=True)
class ParsedYieldMatrixSheet:
    sheet_name: str
    business_date: date | None
    delivery_scope: str
    mapped_data: dict[str, Any]
    raw_data: dict[str, Any]
    status: str
    error_msg: str | None


def yield_matrix_row_summary_fields() -> list[str]:
    return list(YIELD_MATRIX_FIELD_ORDER)


def _normalize_text(value: Any) -> str:
    text = str(value or '').strip()
    return text.replace('\n', ' ').replace('\r', ' ')


def _normalize_token(value: Any) -> str:
    return _normalize_text(value).replace(' ', '').lower()


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


def _coerce_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_lineage_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _detect_business_date(sheet_name: str, frame: pd.DataFrame, *, year_hint: int | None) -> date | None:
    candidates = [_normalize_text(sheet_name)]
    for value in frame.head(4).fillna('').astype(str).values.flatten().tolist():
        text = _normalize_text(value)
        if text:
            candidates.append(text)

    year = year_hint or datetime.now(timezone.utc).year
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


def normalize_yield_matrix_delivery_scope(sheet_name: str, frame: pd.DataFrame | None = None) -> str:
    tokens = [_normalize_text(sheet_name)]
    if frame is not None:
        tokens.extend(_normalize_text(value) for value in frame.head(3).fillna('').astype(str).values.flatten().tolist())
    text = ' '.join(token for token in tokens if token)
    matched_workshops = [
        workshop_key
        for workshop_key, aliases in WORKSHOP_ALIASES.items()
        if any(alias in text for alias in aliases)
    ]
    matched_company = any(alias in text for alias in COMPANY_ALIASES)
    if matched_company or len(matched_workshops) > 1:
        return 'factory'
    if len(matched_workshops) == 1:
        return f'workshop:{matched_workshops[0]}'
    return 'factory'


def _build_column_labels(frame: pd.DataFrame, *, header_rows: int = 3) -> list[str]:
    labels: list[str] = []
    max_rows = min(header_rows, len(frame.index))
    for column_index in range(len(frame.columns)):
        parts: list[str] = []
        for row_index in range(max_rows):
            text = _normalize_text(frame.iat[row_index, column_index])
            if text and text not in parts:
                parts.append(text)
        labels.append(' '.join(parts))
    return labels


def _build_row_labels(frame: pd.DataFrame) -> list[str]:
    labels: list[str] = []
    for row in frame.fillna('').values.tolist():
        label = ''
        for item in row:
            text = _normalize_text(item)
            if text:
                label = text
                break
        labels.append(label)
    return labels


def _label_matches(label: str, aliases: Iterable[str]) -> bool:
    normalized_label = _normalize_token(label)
    for alias in aliases:
        normalized_alias = _normalize_token(alias)
        if normalized_alias and normalized_alias in normalized_label:
            return True
    return False


def _label_equals_alias(label: str, aliases: Iterable[str]) -> bool:
    normalized_label = _normalize_token(label)
    for alias in aliases:
        normalized_alias = _normalize_token(alias)
        if normalized_alias and normalized_label == normalized_alias:
            return True
    return False


def _row_numeric_value(row: list[Any]) -> float | None:
    numeric_candidates: list[float] = []
    for cell in row:
        value = _parse_float(cell)
        if value is not None:
            numeric_candidates.append(value)
    if numeric_candidates:
        return numeric_candidates[-1]
    return None


def _extract_row_metric(frame: pd.DataFrame, row_labels: list[str], *, row_aliases: Iterable[str]) -> float | None:
    for index, label in enumerate(row_labels):
        if not _label_matches(label, row_aliases):
            continue
        value = _row_numeric_value(frame.iloc[index].tolist())
        if value is not None:
            return value
    return None


def _extract_column_metric(
    frame: pd.DataFrame,
    row_labels: list[str],
    column_labels: list[str],
    *,
    column_aliases: Iterable[str],
    metric_aliases: Iterable[str],
) -> float | None:
    for row_index, label in enumerate(row_labels):
        if not _label_equals_alias(label, metric_aliases):
            continue
        for column_index, column_label in enumerate(column_labels):
            if not _label_matches(column_label, column_aliases):
                continue
            value = _parse_float(frame.iat[row_index, column_index])
            if value is not None:
                return value
    return None


def _extract_workshop_yields(frame: pd.DataFrame, row_labels: list[str], column_labels: list[str]) -> dict[str, float]:
    workshop_yields: dict[str, float] = {}
    for workshop_key, aliases in WORKSHOP_ALIASES.items():
        value = _extract_column_metric(
            frame,
            row_labels,
            column_labels,
            column_aliases=aliases,
            metric_aliases=YIELD_METRIC_ALIASES,
        )
        if value is None:
            row_aliases = tuple([f'{alias}{metric}' for alias in aliases for metric in YIELD_METRIC_ALIASES])
            value = _extract_row_metric(frame, row_labels, row_aliases=row_aliases)
        if value is not None:
            workshop_yields[workshop_key] = value
    return workshop_yields


def _extract_company_total_yield(frame: pd.DataFrame, row_labels: list[str], column_labels: list[str]) -> float | None:
    value = _extract_column_metric(
        frame,
        row_labels,
        column_labels,
        column_aliases=COMPANY_ALIASES,
        metric_aliases=YIELD_METRIC_ALIASES,
    )
    if value is not None:
        return value
    row_aliases = tuple([f'{alias}{metric}' for alias in COMPANY_ALIASES for metric in YIELD_METRIC_ALIASES])
    value = _extract_row_metric(frame, row_labels, row_aliases=row_aliases)
    if value is not None:
        return value
    return None


def _extract_mp_targets(frame: pd.DataFrame, row_labels: list[str], column_labels: list[str]) -> dict[str, float]:
    mp_targets: dict[str, float] = {}
    for key, aliases in (('M', M_ALIASES), ('P', P_ALIASES)):
        value = _extract_row_metric(frame, row_labels, row_aliases=aliases)
        if value is None:
            value = _extract_column_metric(
                frame,
                row_labels,
                column_labels,
                column_aliases=aliases,
                metric_aliases=YIELD_METRIC_ALIASES,
            )
        if value is not None:
            mp_targets[key] = value
    return mp_targets


def _quality_status(*, workshop_yields: dict[str, float], mp_targets: dict[str, float], company_total_yield: float | None) -> str:
    if workshop_yields and len(mp_targets) == 2 and company_total_yield is not None:
        return 'ready'
    if workshop_yields or mp_targets or company_total_yield is not None:
        return 'warning'
    return 'blocked'


def parse_yield_matrix_sheet(
    sheet_name: str,
    frame: pd.DataFrame,
    *,
    source_batch_id: int | None = None,
    year_hint: int | None = None,
) -> ParsedYieldMatrixSheet:
    business_date = _detect_business_date(sheet_name, frame, year_hint=year_hint)
    delivery_scope = normalize_yield_matrix_delivery_scope(sheet_name, frame)
    row_labels = _build_row_labels(frame)
    column_labels = _build_column_labels(frame)
    workshop_yields = _extract_workshop_yields(frame, row_labels, column_labels)
    mp_targets = _extract_mp_targets(frame, row_labels, column_labels)
    company_total_yield = _extract_company_total_yield(frame, row_labels, column_labels)
    quality_status = _quality_status(
        workshop_yields=workshop_yields,
        mp_targets=mp_targets,
        company_total_yield=company_total_yield,
    )

    draft_payload = {
        'business_date': business_date.isoformat() if business_date else None,
        'source_batch_id': source_batch_id,
        'sheet_name': str(sheet_name),
        'delivery_scope': delivery_scope,
        'workshop_yields': workshop_yields,
        'mp_targets': mp_targets,
        'company_total_yield': company_total_yield,
    }
    mapped_data = {
        **draft_payload,
        'lineage_hash': _build_lineage_hash(draft_payload),
        'quality_status': quality_status,
    }
    raw_data = {
        'sheet_name': str(sheet_name),
        'preview_rows': frame.head(8).fillna('').astype(str).values.tolist(),
        'column_preview': column_labels,
    }
    status = 'success' if quality_status != 'blocked' else 'failed'
    error_msg = None if status == 'success' else '成品率矩阵未识别出足够字段，请检查表头、样本或多级列结构。'
    return ParsedYieldMatrixSheet(
        sheet_name=str(sheet_name),
        business_date=business_date,
        delivery_scope=delivery_scope,
        mapped_data=mapped_data,
        raw_data=raw_data,
        status=status,
        error_msg=error_msg,
    )


def parse_yield_matrix_workbook(
    path: str | Path,
    *,
    source_batch_id: int | None = None,
    year_hint: int | None = None,
) -> list[ParsedYieldMatrixSheet]:
    workbook_path = Path(path)
    if workbook_path.suffix.lower() == '.xlsx':
        engine = 'openpyxl'
    elif workbook_path.suffix.lower() == '.xls':
        try:
            importlib.import_module('xlrd')
        except ModuleNotFoundError as exc:
            raise HTTPException(
                status_code=400,
                detail='当前运行环境不支持直接读取历史 .xls，请先转换为 .xlsx 后上传。',
            ) from exc
        engine = 'xlrd'
    else:
        raise HTTPException(status_code=400, detail='Only xlsx/xls yield matrix workbooks are supported')
    excel = pd.ExcelFile(workbook_path, engine=engine)
    parsed_rows: list[ParsedYieldMatrixSheet] = []
    for sheet_name in excel.sheet_names:
        frame = pd.read_excel(workbook_path, sheet_name=sheet_name, header=None, engine=engine)
        parsed_rows.append(
            parse_yield_matrix_sheet(
                str(sheet_name),
                frame,
                source_batch_id=source_batch_id,
                year_hint=year_hint,
            )
        )
    return parsed_rows


def build_yield_matrix_snapshot(mapped_data: dict[str, Any]) -> YieldMatrixSnapshot | None:
    if not isinstance(mapped_data, dict):
        return None
    sheet_name = mapped_data.get('sheet_name')
    if not sheet_name:
        return None
    business_date_value = mapped_data.get('business_date')
    snapshot_date = None
    if business_date_value:
        try:
            snapshot_date = date.fromisoformat(str(business_date_value))
        except ValueError:
            snapshot_date = None
    workshop_yields = mapped_data.get('workshop_yields') if isinstance(mapped_data.get('workshop_yields'), dict) else {}
    mp_targets = mapped_data.get('mp_targets') if isinstance(mapped_data.get('mp_targets'), dict) else {}
    payload = {
        'business_date': mapped_data.get('business_date'),
        'source_batch_id': mapped_data.get('source_batch_id'),
        'sheet_name': sheet_name,
        'delivery_scope': mapped_data.get('delivery_scope') or 'factory',
        'workshop_yields': {str(key): _parse_float(value) for key, value in workshop_yields.items()},
        'mp_targets': {str(key): _parse_float(value) for key, value in mp_targets.items()},
        'company_total_yield': _parse_float(mapped_data.get('company_total_yield')),
    }
    return YieldMatrixSnapshot(
        business_date=snapshot_date,
        source_batch_id=_coerce_int(mapped_data.get('source_batch_id')),
        sheet_name=str(sheet_name),
        delivery_scope=str(payload['delivery_scope']),
        workshop_yields={key: value for key, value in payload['workshop_yields'].items() if value is not None},
        mp_targets={key: value for key, value in payload['mp_targets'].items() if value is not None},
        company_total_yield=payload['company_total_yield'],
        lineage_hash=str(mapped_data.get('lineage_hash') or _build_lineage_hash(payload)),
        quality_status=str(mapped_data.get('quality_status') or 'warning'),
    )


def load_yield_matrix_snapshots(db: Session, *, target_date: date | None = None) -> list[YieldMatrixSnapshot]:
    batches = db.query(ImportBatch).filter(ImportBatch.import_type == 'yield_rate_matrix').order_by(ImportBatch.id.desc()).all()
    snapshots: list[YieldMatrixSnapshot] = []
    seen_keys: set[tuple[str | None, str, str]] = set()
    for batch in batches:
        rows = db.query(ImportRow).filter(ImportRow.batch_id == batch.id).order_by(ImportRow.row_number.asc()).all()
        for row in rows:
            snapshot = build_yield_matrix_snapshot(row.mapped_data or {})
            if snapshot is None:
                continue
            if target_date is not None and snapshot.business_date != target_date:
                continue
            key = (
                snapshot.business_date.isoformat() if snapshot.business_date else None,
                snapshot.delivery_scope,
                snapshot.sheet_name,
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            snapshots.append(snapshot)
    snapshots.sort(key=lambda item: ((item.business_date or date.min).isoformat(), item.delivery_scope, item.sheet_name))
    return snapshots


def _resolve_authoritative_scope(ready_snapshots: list[YieldMatrixSnapshot]) -> tuple[str | None, str]:
    ready_scopes = sorted({item.delivery_scope for item in ready_snapshots if item.delivery_scope})
    if not ready_scopes:
        return None, 'no_ready_snapshot'
    if 'factory' in ready_scopes:
        return 'factory', 'prefer_factory_scope'
    if len(ready_scopes) == 1:
        return ready_scopes[0], 'single_ready_scope'
    return None, 'ambiguous_ready_scopes'


def _has_conflicting_metrics(snapshots: list[YieldMatrixSnapshot]) -> bool:
    workshop_values: dict[str, set[float]] = {}
    mp_values: dict[str, set[float]] = {}
    company_values: set[float] = set()

    for item in snapshots:
        for key, value in item.workshop_yields.items():
            workshop_values.setdefault(key, set()).add(round(value, 6))
        for key, value in item.mp_targets.items():
            mp_values.setdefault(key, set()).add(round(value, 6))
        if item.company_total_yield is not None:
            company_values.add(round(item.company_total_yield, 6))

    if any(len(values) > 1 for values in workshop_values.values()):
        return True
    if any(len(values) > 1 for values in mp_values.values()):
        return True
    return len(company_values) > 1


def build_yield_matrix_projection(db: Session, *, target_date: date) -> dict[str, Any]:
    candidate_snapshots = load_yield_matrix_snapshots(db, target_date=target_date)
    ready_snapshots = [item for item in candidate_snapshots if item.quality_status == 'ready']
    authoritative_scope, selection_status = _resolve_authoritative_scope(ready_snapshots)
    snapshots = [item for item in ready_snapshots if authoritative_scope and item.delivery_scope == authoritative_scope]
    delivery_scopes = sorted({item.delivery_scope for item in snapshots if item.delivery_scope})
    has_conflicts = _has_conflicting_metrics(snapshots)
    workshop_yields: dict[str, float] = {}
    mp_targets: dict[str, float] = {}
    company_total_yield: float | None = None
    if not has_conflicts:
        for item in snapshots:
            workshop_yields.update(item.workshop_yields)
            mp_targets.update(item.mp_targets)
            if item.company_total_yield is not None:
                company_total_yield = item.company_total_yield

    projection = {
        'business_date': target_date.isoformat(),
        'snapshot_count': len(snapshots),
        'candidate_snapshot_count': len(candidate_snapshots),
        'delivery_scopes': delivery_scopes,
        'primary_delivery_scope': authoritative_scope,
        'selection_status': selection_status if not has_conflicts else 'conflicting_ready_snapshots',
        'selection_rule': 'prefer_factory_scope_else_single_ready_scope_else_ambiguous; conflicting_ready_metrics_do_not_promote_formal_truth',
        'workshop_yields': workshop_yields,
        'mp_targets': mp_targets,
        'company_total_yield': company_total_yield,
        'quality_status': 'ready',
        'items': [item.to_dict() for item in snapshots],
    }
    if snapshots and not has_conflicts:
        projection['quality_status'] = 'ready'
    elif has_conflicts:
        projection['quality_status'] = 'warning'
        projection['workshop_yields'] = {}
        projection['mp_targets'] = {}
        projection['company_total_yield'] = None
    elif any(item.quality_status == 'warning' for item in candidate_snapshots):
        projection['quality_status'] = 'warning'
    elif any(item.quality_status == 'blocked' for item in candidate_snapshots):
        projection['quality_status'] = 'blocked'
    else:
        projection['quality_status'] = 'missing'
    return projection
