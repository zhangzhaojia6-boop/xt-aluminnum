from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.system import User
from app.schemas.command import CommandModuleOut, CommandSurfaceResponseOut
from app.services.command_service import build_admin_module_overview, build_command_surface

router = APIRouter(tags=['command'])
admin_router = APIRouter(tags=['admin-command'])


def _has_entry_access(user: User) -> bool:
    return bool(getattr(user, 'is_admin', False) or getattr(user, 'is_mobile_user', False))


def _has_review_access(user: User) -> bool:
    return bool(getattr(user, 'is_admin', False) or getattr(user, 'is_manager', False) or getattr(user, 'is_reviewer', False))


def _has_admin_access(user: User) -> bool:
    return bool(getattr(user, 'is_admin', False) or getattr(user, 'is_manager', False))


def _ensure_surface_access(surface: str, user: User) -> None:
    allowed = {
        'entry': _has_entry_access,
        'review': _has_review_access,
        'admin': _has_admin_access,
    }[surface](user)
    if not allowed:
        raise HTTPException(status_code=403, detail='Command surface access denied')


@router.get('/surface/{surface}', response_model=CommandSurfaceResponseOut)
def command_surface(
    surface: Literal['entry', 'review', 'admin'],
    target_date: date | None = None,
    current_user: User = Depends(get_current_user),
) -> CommandSurfaceResponseOut:
    _ensure_surface_access(surface, current_user)
    return build_command_surface(surface=surface, target_date=target_date)


@admin_router.get('/command-overview', response_model=CommandSurfaceResponseOut)
def admin_command_overview(
    target_date: date | None = None,
    current_user: User = Depends(get_current_user),
) -> CommandSurfaceResponseOut:
    _ensure_surface_access('admin', current_user)
    return build_command_surface(surface='admin', target_date=target_date)


@admin_router.get('/ops-overview', response_model=CommandModuleOut)
def admin_ops_overview(
    target_date: date | None = None,
    current_user: User = Depends(get_current_user),
) -> CommandModuleOut:
    _ensure_surface_access('admin', current_user)
    return build_admin_module_overview(module_id='12', target_date=target_date)


@admin_router.get('/governance-overview', response_model=CommandModuleOut)
def admin_governance_overview(
    target_date: date | None = None,
    current_user: User = Depends(get_current_user),
) -> CommandModuleOut:
    _ensure_surface_access('admin', current_user)
    return build_admin_module_overview(module_id='13', target_date=target_date)


@admin_router.get('/master-overview', response_model=CommandModuleOut)
def admin_master_overview(
    target_date: date | None = None,
    current_user: User = Depends(get_current_user),
) -> CommandModuleOut:
    _ensure_surface_access('admin', current_user)
    return build_admin_module_overview(module_id='14', target_date=target_date)
