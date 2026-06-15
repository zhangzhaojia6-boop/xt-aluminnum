from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary
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


def _ensure_mapping_reconciliation_access(user: User) -> None:
    if not build_scope_summary(user).is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Mapping reconciliation access denied',
        )


@router.get('/sources')
def get_sources(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    _ensure_mapping_reconciliation_access(current_user)
    return list_sources()


@router.post('/run')
def run_mapping_reconciliation(
    body: MappingRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_mapping_reconciliation_access(current_user)
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

    if body.business_date and not system_rows:
        system_rows = build_system_mapping_rows(db, business_date=body.business_date)

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
    payload['difference_summary'] = summarize_differences(result.differences)
    if reference_parse is not None:
        payload['reference_parse'] = reference_parse
    payload['rule_proposals'] = propose_rules(result.differences)
    return payload
