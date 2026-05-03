from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.rule_config import RuleConfig
from app.models.system import User
from app.schemas.rule_config import RuleConfigOut, RuleConfigUpdate, RuleConfigUpsert
from app.services import rule_config_service


router = APIRouter(tags=['rule-configs'])


def _require_admin(current_user: User) -> None:
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='仅管理员可操作')


@router.get('', response_model=list[RuleConfigOut])
def list_rule_configs(
    scope_type: str = Query(..., pattern='^(factory|workshop)$'),
    scope_key: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    _require_admin(current_user)
    try:
        return rule_config_service.list_for_scope(db, scope_type=scope_type, scope_key=scope_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post('', response_model=RuleConfigOut, status_code=status.HTTP_201_CREATED)
def upsert_rule_config(
    payload: RuleConfigUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    try:
        item = rule_config_service.set_threshold(
            db,
            scope_type=payload.scope_type,
            scope_key=payload.scope_key,
            key=payload.key,
            value=payload.value,
            updated_by=current_user.id,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    db.commit()
    db.refresh(item)
    return rule_config_service.payload_for(item)

@router.put('/{config_id}', response_model=RuleConfigOut)
def update_rule_config(
    config_id: int,
    payload: RuleConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    item = db.get(RuleConfig, config_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='规则配置不存在')
    item = rule_config_service.set_threshold(
        db,
        scope_type=item.scope_type,
        scope_key=item.scope_key,
        key=item.key,
        value=payload.value,
        updated_by=current_user.id,
        value_type=item.value_type,
    )
    db.commit()
    db.refresh(item)
    return rule_config_service.payload_for(item)
