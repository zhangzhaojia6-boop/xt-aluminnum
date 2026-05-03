from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.scope import ScopeSummary, build_scope_summary
from app.models.system import User
from app.schemas.factory_command import (
    FactoryCoilFlowOut,
    FactoryCoilListItemOut,
    FactoryCostBenefitOut,
    FactoryDestinationOut,
    FactoryMachineLineOut,
    FactoryOverviewOut,
    FactoryWorkshopOut,
)
from app.services import factory_command_service

router = APIRouter(tags=['factory-command'])


def _ensure_factory_command_access(user: User) -> ScopeSummary:
    summary = build_scope_summary(user)
    if not bool(summary.is_admin or summary.is_manager or summary.is_reviewer):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Factory command access denied')
    return summary


@router.get('/overview', response_model=FactoryOverviewOut)
def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FactoryOverviewOut:
    scope = _ensure_factory_command_access(current_user)
    return factory_command_service.build_overview(db, scope=scope)


@router.get('/workshops', response_model=list[FactoryWorkshopOut])
def workshops(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FactoryWorkshopOut]:
    scope = _ensure_factory_command_access(current_user)
    return factory_command_service.list_workshops(db, scope=scope)


@router.get('/machine-lines', response_model=list[FactoryMachineLineOut])
def machine_lines(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FactoryMachineLineOut]:
    scope = _ensure_factory_command_access(current_user)
    return factory_command_service.list_machine_lines(db, scope=scope)


@router.get('/coils', response_model=list[FactoryCoilListItemOut])
def coils(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FactoryCoilListItemOut]:
    scope = _ensure_factory_command_access(current_user)
    return factory_command_service.list_coils(db, scope=scope)


@router.get('/coils/{coil_key}/flow', response_model=FactoryCoilFlowOut)
def coil_flow(
    coil_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FactoryCoilFlowOut:
    scope = _ensure_factory_command_access(current_user)
    return factory_command_service.get_coil_flow(db, coil_key=coil_key, scope=scope)


@router.get('/cost-benefit', response_model=FactoryCostBenefitOut)
def cost_benefit(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FactoryCostBenefitOut:
    scope = _ensure_factory_command_access(current_user)
    return factory_command_service.build_cost_benefit(db, scope=scope)


@router.get('/destinations', response_model=list[FactoryDestinationOut])
def destinations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FactoryDestinationOut]:
    scope = _ensure_factory_command_access(current_user)
    return factory_command_service.list_destinations(db, scope=scope)
