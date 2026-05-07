from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.imports import ImportBatch, ImportRow
from app.models.master import Equipment, Workshop


@dataclass(frozen=True, slots=True)
class MappingRule:
    workshop_code: str
    equipment_code: str | None = None
    equipment_required: bool = False


@dataclass(frozen=True, slots=True)
class MappingCandidate:
    entity_type: str
    id: int
    code: str
    name: str
    workshop_id: int | None
    workshop_code: str | None
    equipment_type: str | None
    match_reason: str


@dataclass(frozen=True, slots=True)
class DailyProductionMappingRow:
    row_index: int | None
    business_date: str | None
    source_unit: str | None
    workshop_label: str | None
    project_label: str | None
    daily_input_tons: float | None
    month_to_date_input_tons: float | None
    daily_output_tons: float | None
    month_to_date_output_tons: float | None
    daily_scrap_tons: float | None
    month_to_date_scrap_tons: float | None
    status: str
    expected_workshop_code: str | None
    expected_equipment_code: str | None
    workshop_id: int | None
    workshop_code: str | None
    workshop_name: str | None
    equipment_id: int | None
    equipment_code: str | None
    equipment_name: str | None
    issues: list[dict[str, Any]]
    candidate_workshops: list[MappingCandidate] = field(default_factory=list)
    candidate_equipment: list[MappingCandidate] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DailyProductionMappingPreview:
    batch_id: int | None
    batch_no: str | None
    business_date: str | None
    source_unit: str | None
    total_rows: int
    ready_rows: int
    needs_equipment_mapping_rows: int
    unresolved_rows: int
    rows: list[DailyProductionMappingRow]


def serialize_daily_production_mapping_preview(preview: DailyProductionMappingPreview) -> dict[str, Any]:
    return asdict(preview)


DAILY_PRODUCTION_MAPPING_RULES: dict[tuple[str, str], MappingRule] = {
    ('铸锭', ''): MappingRule(workshop_code='ZD'),
    ('铸轧', '铸二'): MappingRule(workshop_code='ZR2'),
    ('铸轧', '铸三'): MappingRule(workshop_code='ZR3'),
    ('热轧', '铣床'): MappingRule(workshop_code='RZ', equipment_code='RZ-XC', equipment_required=True),
    ('热轧', '热轧'): MappingRule(workshop_code='RZ', equipment_code='RZ-ZJ', equipment_required=True),
    ('冷轧', '2050'): MappingRule(workshop_code='LZ2050', equipment_code='LZ2050-1', equipment_required=True),
    ('冷轧', '1850'): MappingRule(workshop_code='LZ1850', equipment_code='LZ1850-1', equipment_required=True),
    ('冷轧', '1650'): MappingRule(workshop_code='LZ1650', equipment_code='LZ1650-1', equipment_required=True),
    ('冷轧', '花纹板'): MappingRule(workshop_code='HWB', equipment_code='HWB-1', equipment_required=True),
    ('精整', '纵剪'): MappingRule(workshop_code='JZ', equipment_code='JZ-ZJ1', equipment_required=True),
    ('精整', '横剪'): MappingRule(workshop_code='JZ', equipment_code='JZ-HJ1', equipment_required=True),
    ('精整', '剪子'): MappingRule(workshop_code='JZ', equipment_code='JZ-HJ1', equipment_required=True),
    ('精整', '剪切'): MappingRule(workshop_code='JZ', equipment_code='JZ-HJ1', equipment_required=True),
    ('精整', '包装'): MappingRule(workshop_code='JZ'),
    ('拉矫', '拉矫'): MappingRule(workshop_code='JZ', equipment_code='JZ-LWJ1', equipment_required=True),
    ('拉矫', '洗拉'): MappingRule(workshop_code='JZ', equipment_code='JZ-LWJ1', equipment_required=True),
    ('拉矫', '分切'): MappingRule(workshop_code='JZ', equipment_code='JZ-FT1', equipment_required=True),
    ('拉矫', '大分切'): MappingRule(workshop_code='JZ', equipment_code='JZ-FT1', equipment_required=True),
    ('拉矫', '横剪'): MappingRule(workshop_code='JZ', equipment_code='JZ-HJ1', equipment_required=True),
    ('拉矫', '产量'): MappingRule(workshop_code='JZ'),
    ('退火炉', '拉矫'): MappingRule(workshop_code='JZ'),
    ('在线退火', '新厂南线'): MappingRule(workshop_code='ZXTF', equipment_code='ZXTF-2', equipment_required=True),
    ('在线退火', '新厂北线'): MappingRule(workshop_code='ZXTF', equipment_code='ZXTF-1', equipment_required=True),
    ('在线退火', '园区北线'): MappingRule(workshop_code='ZXTF', equipment_code='ZXTF-3', equipment_required=True),
    ('在线退火', '南线'): MappingRule(workshop_code='ZXTF'),
    ('园区淬火', ''): MappingRule(workshop_code='JQ'),
    ('园区精整', ''): MappingRule(workshop_code='JQ'),
    ('园区剪切', ''): MappingRule(workshop_code='JQ'),
    ('回收', ''): MappingRule(workshop_code='ZD'),
    ('大修', ''): MappingRule(workshop_code='RZ'),
}


def _normalize_label(value: Any) -> str:
    return str(value or '').strip().replace(' ', '')


def _candidate_tokens(*values: Any) -> list[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = _normalize_label(value)
        if not normalized:
            continue
        tokens.add(normalized)
        if normalized.endswith('炉') and len(normalized) > 1:
            tokens.add(normalized[:-1])
        for marker in ('在线退火', '冷轧', '精整', '拉矫', '分切', '纵剪', '剪子', '剪切', '退火'):
            if marker in normalized:
                tokens.add(marker)
    return sorted(tokens, key=lambda item: (-len(item), item))


def _candidate_workshops(workshop_label: Any, workshops: dict[str, Workshop]) -> list[MappingCandidate]:
    tokens = _candidate_tokens(workshop_label)
    candidates: list[MappingCandidate] = []
    for workshop in workshops.values():
        haystack = _normalize_label(f'{workshop.code}{workshop.name}{workshop.workshop_type or ""}')
        if any(token in haystack for token in tokens):
            candidates.append(
                MappingCandidate(
                    entity_type='workshop',
                    id=workshop.id,
                    code=str(workshop.code or ''),
                    name=str(workshop.name or ''),
                    workshop_id=workshop.id,
                    workshop_code=str(workshop.code or ''),
                    equipment_type=None,
                    match_reason='workshop_label_match',
                )
            )
    return candidates[:6]


def _candidate_equipment(
    project_label: Any,
    equipment: dict[str, Equipment],
    workshops: dict[str, Workshop],
) -> list[MappingCandidate]:
    tokens = _candidate_tokens(project_label)
    workshops_by_id = {item.id: item for item in workshops.values()}
    candidates: list[MappingCandidate] = []
    for machine in equipment.values():
        haystack = _normalize_label(f'{machine.code}{machine.name}{machine.equipment_type or ""}')
        if any(token in haystack for token in tokens):
            workshop = workshops_by_id.get(machine.workshop_id)
            candidates.append(
                MappingCandidate(
                    entity_type='equipment',
                    id=machine.id,
                    code=str(machine.code or ''),
                    name=str(machine.name or ''),
                    workshop_id=machine.workshop_id,
                    workshop_code=str(workshop.code or '') if workshop else None,
                    equipment_type=str(machine.equipment_type or '') if machine.equipment_type else None,
                    match_reason='project_label_match',
                )
            )
    return candidates[:8]


def _latest_daily_production_batch(db: Session) -> ImportBatch | None:
    return (
        db.query(ImportBatch)
        .filter(ImportBatch.import_type == 'daily_production_report')
        .order_by(ImportBatch.id.desc())
        .first()
    )


def _batch_rows(db: Session, batch_id: int) -> list[ImportRow]:
    return db.query(ImportRow).filter(ImportRow.batch_id == batch_id).order_by(ImportRow.row_number.asc()).all()


def _workshops_by_code(db: Session) -> dict[str, Workshop]:
    rows = db.query(Workshop).filter(Workshop.is_active.is_(True)).order_by(Workshop.code.asc()).all()
    return {str(item.code): item for item in rows}


def _equipment_by_code(db: Session) -> dict[str, Equipment]:
    rows = db.query(Equipment).filter(Equipment.is_active.is_(True)).order_by(Equipment.code.asc()).all()
    return {str(item.code): item for item in rows}


def _resolve_row(
    row_payload: dict[str, Any],
    *,
    source_business_date: str | None,
    source_unit: str | None,
    workshops: dict[str, Workshop],
    equipment: dict[str, Equipment],
) -> DailyProductionMappingRow:
    workshop_label = row_payload.get('workshop_label')
    project_label = row_payload.get('project_label')
    rule = DAILY_PRODUCTION_MAPPING_RULES.get(
        (_normalize_label(workshop_label), _normalize_label(project_label))
    )
    issues: list[dict[str, Any]] = []
    workshop = workshops.get(rule.workshop_code) if rule else None
    machine = equipment.get(rule.equipment_code) if rule and rule.equipment_code else None

    status = 'ready'
    if rule is None:
        status = 'unresolved_workshop'
        issues.append(
            {
                'code': 'unresolved_workshop',
                'message': '每日产量行未匹配到高置信车间主数据，请先补充映射规则或主数据。',
            }
        )
    elif workshop is None:
        status = 'unresolved_workshop'
        issues.append(
            {
                'code': 'workshop_code_not_found',
                'message': f'映射规则指向的车间编码不存在或未启用: {rule.workshop_code}',
            }
        )
    elif rule.equipment_required and machine is None:
        status = 'needs_equipment_mapping'
        issues.append(
            {
                'code': 'equipment_code_not_found' if rule.equipment_code else 'equipment_mapping_required',
                'message': '每日产量行需要机列映射确认后才能进入正式产量事实表。',
            }
        )

    candidate_workshops: list[MappingCandidate] = []
    candidate_equipment: list[MappingCandidate] = []
    if status != 'ready':
        candidate_workshops = _candidate_workshops(workshop_label, workshops)
        candidate_equipment = _candidate_equipment(project_label, equipment, workshops)

    return DailyProductionMappingRow(
        row_index=row_payload.get('row_index'),
        business_date=source_business_date,
        source_unit=source_unit,
        workshop_label=workshop_label,
        project_label=project_label,
        daily_input_tons=row_payload.get('daily_input_tons'),
        month_to_date_input_tons=row_payload.get('month_to_date_input_tons'),
        daily_output_tons=row_payload.get('daily_output_tons'),
        month_to_date_output_tons=row_payload.get('month_to_date_output_tons'),
        daily_scrap_tons=row_payload.get('daily_scrap_tons'),
        month_to_date_scrap_tons=row_payload.get('month_to_date_scrap_tons'),
        status=status,
        expected_workshop_code=rule.workshop_code if rule else None,
        expected_equipment_code=rule.equipment_code if rule else None,
        workshop_id=workshop.id if workshop else None,
        workshop_code=workshop.code if workshop else None,
        workshop_name=workshop.name if workshop else None,
        equipment_id=machine.id if machine else None,
        equipment_code=machine.code if machine else None,
        equipment_name=machine.name if machine else None,
        issues=issues,
        candidate_workshops=candidate_workshops,
        candidate_equipment=candidate_equipment,
    )


def build_daily_production_mapping_preview(
    db: Session, *, batch_id: int | None = None
) -> DailyProductionMappingPreview:
    batch = db.get(ImportBatch, batch_id) if batch_id is not None else _latest_daily_production_batch(db)
    if batch is None:
        return DailyProductionMappingPreview(
            batch_id=None,
            batch_no=None,
            business_date=None,
            source_unit=None,
            total_rows=0,
            ready_rows=0,
            needs_equipment_mapping_rows=0,
            unresolved_rows=0,
            rows=[],
        )

    workshops = _workshops_by_code(db)
    equipment = _equipment_by_code(db)
    resolved_rows: list[DailyProductionMappingRow] = []
    business_date = None
    source_unit = None

    for import_row in _batch_rows(db, batch.id):
        mapped_data = import_row.mapped_data if isinstance(import_row.mapped_data, dict) else {}
        business_date = business_date or mapped_data.get('business_date')
        source_unit = source_unit or mapped_data.get('source_unit')
        for row_payload in mapped_data.get('workshop_rows') or []:
            if isinstance(row_payload, dict):
                resolved_rows.append(
                    _resolve_row(
                        row_payload,
                        source_business_date=mapped_data.get('business_date'),
                        source_unit=mapped_data.get('source_unit'),
                        workshops=workshops,
                        equipment=equipment,
                    )
                )

    return DailyProductionMappingPreview(
        batch_id=batch.id,
        batch_no=batch.batch_no,
        business_date=business_date,
        source_unit=source_unit,
        total_rows=len(resolved_rows),
        ready_rows=len([item for item in resolved_rows if item.status == 'ready']),
        needs_equipment_mapping_rows=len(
            [item for item in resolved_rows if item.status == 'needs_equipment_mapping']
        ),
        unresolved_rows=len([item for item in resolved_rows if item.status == 'unresolved_workshop']),
        rows=resolved_rows,
    )
