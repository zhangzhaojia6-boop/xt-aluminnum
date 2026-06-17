from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary
from app.models.reconciliation import MappingReconciliationRun
from app.models.system import User
from app.services.mapping_reconciliation_service import (
    MappingFieldSpec,
    build_system_mapping_rows,
    compare_mapping_rows,
    list_sources,
    parse_output_skill_reference_file,
    propose_rules,
    resolve_reference_file,
    serialize_result,
    summarize_differences,
    summarize_match_result,
)

router = APIRouter(tags=['mapping-reconciliation'])


class MappingFieldSpecIn(BaseModel):
    metric: str
    reference_field: str
    system_field: str
    reference_unit: str | None = None
    system_unit: str | None = None
    tolerance: float = 0
    weight: float = 1


class MappingRunRequest(BaseModel):
    reference_file: str | None = None
    business_date: date | None = None
    reference_rows: list[dict[str, Any]] = Field(default_factory=list)
    system_rows: list[dict[str, Any]] = Field(default_factory=list)
    fields: list[MappingFieldSpecIn] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=lambda: ['business_date', 'workshop', 'shift'])
    dimension_aliases: dict[str, dict[str, str]] = Field(default_factory=dict)


class MappingDifferenceIn(BaseModel):
    reason_code: str
    metric: str
    dimension: dict[str, Any] = Field(default_factory=dict)
    reference_value: float | str | None = None
    system_value: float | str | None = None
    diff_value: float | None = None
    suggested_rule: str = ''


class RuleProposeRequest(BaseModel):
    differences: list[MappingDifferenceIn] = Field(default_factory=list)


class RuleApplyDryRunRequest(MappingRunRequest):
    proposals: list[dict[str, Any]] = Field(default_factory=list)


def _ensure_mapping_reconciliation_access(user: User) -> None:
    if not build_scope_summary(user).is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Mapping reconciliation access denied',
        )


def _serialize_run(entity: MappingReconciliationRun) -> dict[str, Any]:
    return {
        'id': entity.id,
        'run_mode': entity.run_mode,
        'status': entity.status,
        'business_date': entity.business_date.isoformat() if entity.business_date else None,
        'reference_file': entity.reference_file,
        'reference_source': entity.reference_source,
        'created_by_id': entity.created_by_id,
        'reference_rows_count': entity.reference_rows_count,
        'system_rows_count': entity.system_rows_count,
        'overall_match_rate': float(entity.overall_match_rate or 0),
        'result': entity.result_payload or {},
        'created_at': entity.created_at.isoformat() if entity.created_at else None,
    }


def _persist_run(
    *,
    db: Session,
    body: MappingRunRequest,
    payload: dict[str, Any],
    current_user: User,
) -> MappingReconciliationRun | None:
    if not isinstance(db, Session):
        return None
    entity = MappingReconciliationRun(
        run_mode='dry_run',
        status='completed',
        business_date=body.business_date,
        reference_file=body.reference_file,
        reference_source=payload.get('reference_parse', {}).get('source_path') if payload.get('reference_parse') else None,
        created_by_id=current_user.id,
        reference_rows_count=payload['reference_rows_count'],
        system_rows_count=payload['system_rows_count'],
        overall_match_rate=payload['overall_match_rate'],
        request_payload=body.model_dump(mode='json'),
        result_payload=payload,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def _get_run_or_404(db: Session, run_id: int) -> MappingReconciliationRun:
    entity = db.get(MappingReconciliationRun, run_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mapping reconciliation run not found')
    return entity


def _differences_from_request(items: list[MappingDifferenceIn]):
    from app.services.mapping_reconciliation_service import MappingDifference

    return [MappingDifference(**item.model_dump()) for item in items]


def _filter_rows_by_business_date(rows: list[dict[str, Any]], business_date: date | None) -> list[dict[str, Any]]:
    if business_date is None:
        return rows
    target = business_date.isoformat()
    return [row for row in rows if str(row.get('business_date') or '') == target]


def _dimension_aliases_with_proposals(
    base_aliases: dict[str, dict[str, str]],
    proposals: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    aliases = {field: dict(values) for field, values in base_aliases.items()}
    for item in proposals:
        if item.get('rule_type') != 'alias_candidate':
            continue
        field = item.get('field')
        reference_value = item.get('reference_value')
        system_value = item.get('system_value')
        if not field or not reference_value or not system_value:
            continue
        aliases.setdefault(str(field), {})[str(system_value)] = str(reference_value)
    return aliases


def _resolve_rows(
    *,
    body: MappingRunRequest,
    db: Session,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    reference_rows = body.reference_rows
    system_rows = body.system_rows
    reference_parse: dict[str, Any] | None = None

    if body.reference_file:
        try:
            reference_path = resolve_reference_file(body.reference_file)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        reference_parse = parse_output_skill_reference_file(reference_path)
        if reference_parse['status'] != 'parsed':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reference_parse)
        reference_rows = reference_parse['rows']
        reference_rows = _filter_rows_by_business_date(reference_rows, body.business_date)
        reference_parse['rows'] = reference_rows

    if body.business_date and not system_rows:
        system_rows = build_system_mapping_rows(db, business_date=body.business_date)

    return reference_rows, system_rows, reference_parse


@router.get('/sources')
def get_sources(
    limit: int = Query(default=5000, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _ensure_mapping_reconciliation_access(current_user)
    return list_sources(limit=limit)


@router.post('/run')
def run_mapping_reconciliation(
    body: MappingRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_mapping_reconciliation_access(current_user)
    reference_rows, system_rows, reference_parse = _resolve_rows(body=body, db=db)

    result = compare_mapping_rows(
        reference_rows=reference_rows,
        system_rows=system_rows,
        fields=[MappingFieldSpec(**item.model_dump()) for item in body.fields],
        dimensions=body.dimensions,
        dimension_aliases=body.dimension_aliases,
    )
    payload = serialize_result(result)
    payload['run_mode'] = 'dry_run'
    payload['reference_rows_count'] = len(reference_rows)
    payload['system_rows_count'] = len(system_rows)
    payload['match_summary'] = summarize_match_result(result)
    payload['difference_summary'] = summarize_differences(result.differences)
    if reference_parse is not None:
        payload['reference_parse'] = reference_parse
    payload['rule_proposals'] = propose_rules(result.differences)
    persisted = _persist_run(db=db, body=body, payload=payload, current_user=current_user)
    if persisted is not None:
        payload['run_id'] = persisted.id
    return payload


@router.post('/rules/propose')
def propose_mapping_reconciliation_rules(
    body: RuleProposeRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _ensure_mapping_reconciliation_access(current_user)
    return {
        'run_mode': 'dry_run',
        'applied': False,
        'rule_proposals': propose_rules(_differences_from_request(body.differences)),
    }


@router.post('/rules/apply-dry-run')
def apply_mapping_reconciliation_rules_dry_run(
    body: RuleApplyDryRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_mapping_reconciliation_access(current_user)
    reference_rows, system_rows, reference_parse = _resolve_rows(body=body, db=db)
    dimension_aliases = _dimension_aliases_with_proposals(body.dimension_aliases, body.proposals)
    result = compare_mapping_rows(
        reference_rows=reference_rows,
        system_rows=system_rows,
        fields=[MappingFieldSpec(**item.model_dump()) for item in body.fields],
        dimensions=body.dimensions,
        dimension_aliases=dimension_aliases,
    )
    result_payload = serialize_result(result)
    result_payload['match_summary'] = summarize_match_result(result)
    result_payload['difference_summary'] = summarize_differences(result.differences)
    if reference_parse is not None:
        result_payload['reference_parse'] = reference_parse
    return {
        'run_mode': 'dry_run',
        'applied': False,
        'persisted': False,
        'dimension_aliases': dimension_aliases,
        'result': result_payload,
    }


@router.get('/runs/{run_id}')
def get_mapping_reconciliation_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_mapping_reconciliation_access(current_user)
    return _serialize_run(_get_run_or_404(db, run_id))


@router.get('/runs/{run_id}/differences')
def get_mapping_reconciliation_run_differences(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_mapping_reconciliation_access(current_user)
    entity = _get_run_or_404(db, run_id)
    result_payload = entity.result_payload or {}
    return {
        'run_id': entity.id,
        'differences': result_payload.get('differences', []),
        'difference_summary': result_payload.get('difference_summary', {}),
    }
