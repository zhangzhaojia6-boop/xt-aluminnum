from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.core.scope import build_scope_summary
from app.models.system import User
from app.services.mapping_reconciliation_service import (
    MappingFieldSpec,
    compare_mapping_rows,
    list_sources,
    propose_rules,
    serialize_result,
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
) -> dict[str, Any]:
    _ensure_mapping_reconciliation_access(current_user)
    result = compare_mapping_rows(
        reference_rows=body.reference_rows,
        system_rows=body.system_rows,
        fields=[MappingFieldSpec(**item.model_dump()) for item in body.fields],
        dimensions=body.dimensions,
        dimension_aliases=body.dimension_aliases,
    )
    payload = serialize_result(result)
    payload['run_mode'] = 'dry_run'
    payload['rule_proposals'] = propose_rules(result.differences)
    return payload
