from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
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


def _ensure_factory_command_access(user: User) -> None:
    if not bool(
        getattr(user, 'is_admin', False)
        or getattr(user, 'is_manager', False)
        or getattr(user, 'is_reviewer', False)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Factory command access denied')


@router.get('/overview', response_model=FactoryOverviewOut)
def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FactoryOverviewOut:
    _ensure_factory_command_access(current_user)
    return factory_command_service.build_overview(db)


@router.get('/workshops', response_model=list[FactoryWorkshopOut])
def workshops(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FactoryWorkshopOut]:
    _ensure_factory_command_access(current_user)
    return factory_command_service.list_workshops(db)


@router.get('/machine-lines', response_model=list[FactoryMachineLineOut])
def machine_lines(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FactoryMachineLineOut]:
    _ensure_factory_command_access(current_user)
    return factory_command_service.list_machine_lines(db)


@router.get('/coils', response_model=list[FactoryCoilListItemOut])
def coils(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FactoryCoilListItemOut]:
    _ensure_factory_command_access(current_user)
    return factory_command_service.list_coils(db)


@router.get('/coils/{coil_key}/flow', response_model=FactoryCoilFlowOut)
def coil_flow(
    coil_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FactoryCoilFlowOut:
    _ensure_factory_command_access(current_user)
    return factory_command_service.get_coil_flow(db, coil_key=coil_key)


@router.get('/cost-benefit', response_model=FactoryCostBenefitOut)
def cost_benefit(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FactoryCostBenefitOut:
    _ensure_factory_command_access(current_user)
    return factory_command_service.build_cost_benefit(db)


@router.get('/destinations', response_model=list[FactoryDestinationOut])
def destinations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FactoryDestinationOut]:
    _ensure_factory_command_access(current_user)
    return factory_command_service.list_destinations(db)
