from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_password_hash
from app.core.deps import get_current_user, get_db
from app.models.master import Equipment, Team, Workshop
from app.models.system import User
from app.schemas.common import PaginatedResponse
from app.schemas.users import (
    UserCreateRequest,
    UserDingtalkSyncRequest,
    UserListItem,
    UserResetPasswordRequest,
    UserResetPasswordResponse,
    UserUpdateRequest,
)
from app.services.audit_service import record_entity_change
from app.services import dingtalk_service


router = APIRouter(tags=['users'])


def _require_admin(current_user: User) -> None:
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='仅管理员可操作')


def _resolve_scope_type(*, role: str, workshop_id: int | None, team_id: int | None, is_reviewer: bool, is_manager: bool) -> str:
    if role == 'admin':
        return 'all'
    if team_id is not None:
        return 'self_team'
    if workshop_id is not None:
        return 'self_workshop'
    if is_reviewer or is_manager:
        return 'all'
    return 'assigned'


def _serialize_user_row(
    user: User,
    workshop_name: str | None,
    team_name: str | None,
    *,
    bound_machine_id: int | None = None,
    bound_machine_name: str | None = None,
) -> dict:
    return {
        'id': user.id,
        'username': user.username,
        'name': user.name,
        'role': user.role,
        'workshop_id': user.workshop_id,
        'workshop_name': workshop_name,
        'team_id': user.team_id,
        'team_name': team_name,
        'is_mobile_user': user.is_mobile_user,
        'is_reviewer': user.is_reviewer,
        'is_manager': user.is_manager,
        'is_active': user.is_active,
        'last_login': user.last_login,
        'bound_machine_id': bound_machine_id,
        'bound_machine_name': bound_machine_name,
    }


def _ensure_workshop_and_team(db: Session, *, workshop_id: int | None, team_id: int | None) -> tuple[Workshop | None, Team | None]:
    workshop = db.get(Workshop, workshop_id) if workshop_id is not None else None
    if workshop_id is not None and (workshop is None or not workshop.is_active):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='所属车间不存在')

    team = db.get(Team, team_id) if team_id is not None else None
    if team_id is not None and (team is None or not team.is_active):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='所属班组不存在')
    if workshop is not None and team is not None and team.workshop_id != workshop.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='班组不属于所选车间')
    return workshop, team


def _ensure_unique_username(db: Session, username: str, *, exclude_user_id: int | None = None) -> None:
    query = db.query(User).filter(User.username == username)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    if query.first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='用户名已存在')


def _load_bound_machine_map(db: Session, user_ids: list[int]) -> dict[int, tuple[int, str]]:
    if not user_ids:
        return {}

    rows = (
        db.query(Equipment)
        .filter(Equipment.bound_user_id.in_(user_ids))
        .order_by(Equipment.id.asc())
        .all()
    )
    result: dict[int, tuple[int, str]] = {}
    for item in rows:
        if item.bound_user_id is None or item.bound_user_id in result:
            continue
        result[item.bound_user_id] = (item.id, item.name)
    return result


def _get_bound_machine_for_user(db: Session, user_id: int) -> Equipment | None:
    return (
        db.query(Equipment)
        .filter(Equipment.bound_user_id == user_id, Equipment.is_active.is_(True))
        .order_by(Equipment.id.asc())
        .first()
    )


def _ensure_machine_for_binding(db: Session, machine_id: int) -> Equipment:
    machine = db.get(Equipment, machine_id)
    if machine is None or not machine.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='机列不存在或已停用')
    return machine


def _ensure_machine_workshop_matches_user(db: Session, *, user: User, machine: Equipment) -> None:
    if user.team_id is not None:
        team = db.get(Team, user.team_id)
        if team is not None and team.workshop_id != machine.workshop_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='机列不属于所选车间')
    if user.workshop_id is None:
        user.workshop_id = machine.workshop_id
        return
    if user.workshop_id != machine.workshop_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='机列不属于所选车间')


def _apply_machine_binding(db: Session, *, user: User, bound_machine_id: int | None) -> None:
    if bound_machine_id is None:
        db.query(Equipment).filter(Equipment.bound_user_id == user.id).update(
            {'bound_user_id': None},
            synchronize_session='fetch',
        )
        return

    machine = _ensure_machine_for_binding(db, bound_machine_id)
    if machine.bound_user_id is not None and machine.bound_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='机列已绑定其他用户')

    _ensure_machine_workshop_matches_user(db, user=user, machine=machine)
    db.query(Equipment).filter(Equipment.bound_user_id == user.id, Equipment.id != machine.id).update(
        {'bound_user_id': None},
        synchronize_session='fetch',
    )
    machine.bound_user_id = user.id


def _ensure_current_binding_matches_user_scope(db: Session, user: User) -> None:
    bound_machine = _get_bound_machine_for_user(db, user.id)
    if bound_machine is None:
        return
    _ensure_machine_workshop_matches_user(db, user=user, machine=bound_machine)


def _clean_contact_value(value) -> str | None:
    cleaned = str(value or '').strip()
    return cleaned or None


def _normalize_dingtalk_contact(raw: dict) -> dict[str, str | None]:
    user_id = _clean_contact_value(raw.get('userid') or raw.get('userId') or raw.get('user_id'))
    union_id = _clean_contact_value(raw.get('unionid') or raw.get('unionId') or raw.get('union_id'))
    mobile = _clean_contact_value(raw.get('mobile') or raw.get('phone') or raw.get('telephone'))
    name = _clean_contact_value(raw.get('name') or raw.get('username') or raw.get('nick'))
    return {
        'dingtalk_user_id': user_id,
        'dingtalk_union_id': union_id,
        'mobile': mobile,
        'name': name or mobile or user_id or union_id,
    }


def _find_users_by_field(db: Session, column, value: str) -> list[User]:
    query = db.query(User).filter(column == value)
    if hasattr(query, 'limit'):
        return list(query.limit(2).all())
    return list(query.all())


def _find_dingtalk_sync_user(db: Session, contact: dict[str, str | None]) -> tuple[User | None, bool]:
    user_id = contact.get('dingtalk_user_id')
    union_id = contact.get('dingtalk_union_id')
    mobile = contact.get('mobile')
    candidates: dict[int, User] = {}
    inactive_candidate_found = False
    if user_id:
        for user in _find_users_by_field(db, User.dingtalk_user_id, user_id):
            if user.is_active:
                candidates[int(user.id)] = user
            else:
                inactive_candidate_found = True
    if union_id:
        for user in _find_users_by_field(db, User.dingtalk_union_id, union_id):
            if user.is_active:
                candidates[int(user.id)] = user
            else:
                inactive_candidate_found = True
    for username in (mobile,):
        if username:
            for user in _find_users_by_field(db, User.username, username):
                if user.is_active:
                    candidates[int(user.id)] = user
                else:
                    inactive_candidate_found = True
    if len(candidates) > 1:
        return None, True
    if not candidates:
        return None, inactive_candidate_found
    return next(iter(candidates.values())), False


def _serialize_synced_user(user: User) -> dict:
    return {
        'id': user.id,
        'username': user.username,
        'name': user.name,
        'role': user.role,
        'dingtalk_user_id': user.dingtalk_user_id,
        'dingtalk_union_id': user.dingtalk_union_id,
        'is_mobile_user': user.is_mobile_user,
        'is_active': user.is_active,
    }


def _serialize_user_item(
    db: Session,
    user: User,
    *,
    workshop_name: str | None,
    team_name: str | None,
) -> dict:
    bound_machine_map = _load_bound_machine_map(db, [user.id])
    machine_payload = bound_machine_map.get(user.id, (None, None))
    return _serialize_user_row(
        user,
        workshop_name,
        team_name,
        bound_machine_id=machine_payload[0],
        bound_machine_name=machine_payload[1],
    )


@router.get('/', response_model=PaginatedResponse[UserListItem], name='users-list')
def list_users(
    workshop_id: int | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    query = (
        db.query(User, Workshop.name.label('workshop_name'), Team.name.label('team_name'))
        .outerjoin(Workshop, Workshop.id == User.workshop_id)
        .outerjoin(Team, Team.id == User.team_id)
        .order_by(User.id.asc())
    )
    if workshop_id is not None:
        query = query.filter(User.workshop_id == workshop_id)
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))
    total = query.count()
    rows = query.offset(skip).limit(limit).all()
    user_ids = [user.id for user, _workshop_name, _team_name in rows]
    bound_machine_map = _load_bound_machine_map(db, user_ids)

    items = []
    for user, workshop_name, team_name in rows:
        machine_payload = bound_machine_map.get(user.id, (None, None))
        items.append(
            _serialize_user_row(
                user,
                workshop_name,
                team_name,
                bound_machine_id=machine_payload[0],
                bound_machine_name=machine_payload[1],
            )
        )

    return {
        'items': items,
        'total': total,
        'skip': skip,
        'limit': limit,
    }


@router.post('/sync-dingtalk', name='users-sync-dingtalk')
def sync_dingtalk_users(
    payload: UserDingtalkSyncRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)

    try:
        contacts = dingtalk_service.service.fetch_department_users(payload.department_id)
    except dingtalk_service.DingTalkNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='钉钉应用未配置') from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc) or '钉钉通讯录同步失败') from exc
    created_count = 0
    updated_count = 0
    skipped_count = 0
    users: list[dict] = []

    for raw_contact in contacts:
        contact = _normalize_dingtalk_contact(raw_contact)
        if not any(contact.get(key) for key in ('dingtalk_user_id', 'dingtalk_union_id', 'mobile')):
            skipped_count += 1
            continue

        user, has_binding_conflict = _find_dingtalk_sync_user(db, contact)
        if has_binding_conflict:
            skipped_count += 1
            continue
        if dingtalk_service.has_dingtalk_binding_conflict(
            db,
            dingtalk_user_id=contact.get('dingtalk_user_id'),
            dingtalk_union_id=contact.get('dingtalk_union_id'),
            target_user_id=int(user.id) if user is not None else None,
        ):
            skipped_count += 1
            continue

        try:
            with db.begin_nested():
                if user is None:
                    username = contact.get('mobile') or contact.get('dingtalk_user_id') or contact.get('dingtalk_union_id')
                    if not username or db.query(User).filter(User.username == username).first() is not None:
                        skipped_count += 1
                        continue
                    user = User(
                        username=username,
                        password_hash=get_password_hash(secrets.token_urlsafe(24)),
                        name=contact.get('name') or username,
                        role=payload.role,
                        dingtalk_user_id=contact.get('dingtalk_user_id'),
                        dingtalk_union_id=contact.get('dingtalk_union_id'),
                        data_scope_type=_resolve_scope_type(
                            role=payload.role,
                            workshop_id=None,
                            team_id=None,
                            is_reviewer=False,
                            is_manager=False,
                        ),
                        is_mobile_user=payload.is_mobile_user,
                        is_reviewer=False,
                        is_manager=False,
                        is_active=True,
                    )
                    db.add(user)
                    db.flush()
                    created_count += 1
                else:
                    changed = False
                    if contact.get('name') and user.name != contact['name']:
                        user.name = contact['name']
                        changed = True
                    if contact.get('dingtalk_user_id') and user.dingtalk_user_id != contact['dingtalk_user_id']:
                        user.dingtalk_user_id = contact['dingtalk_user_id']
                        changed = True
                    if contact.get('dingtalk_union_id') and user.dingtalk_union_id != contact['dingtalk_union_id']:
                        user.dingtalk_union_id = contact['dingtalk_union_id']
                        changed = True
                    if payload.is_mobile_user and not user.is_mobile_user:
                        user.is_mobile_user = True
                        changed = True
                    if changed:
                        db.flush()
                        updated_count += 1
        except IntegrityError:
            skipped_count += 1
            continue
        users.append(_serialize_synced_user(user))

    record_entity_change(
        db,
        user=current_user,
        module='users',
        entity_type='users',
        entity_id=None,
        action='sync_dingtalk',
        new_value={
            'department_id': payload.department_id,
            'created_count': created_count,
            'updated_count': updated_count,
            'skipped_count': skipped_count,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
        auto_commit=False,
    )
    db.commit()
    return {
        'created_count': created_count,
        'updated_count': updated_count,
        'skipped_count': skipped_count,
        'users': users,
    }


@router.get('/{user_id}', response_model=UserListItem, name='users-detail')
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    item = db.get(User, user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='用户不存在')

    workshop = db.get(Workshop, item.workshop_id) if item.workshop_id else None
    team = db.get(Team, item.team_id) if item.team_id else None
    return _serialize_user_item(
        db,
        item,
        workshop_name=workshop.name if workshop else None,
        team_name=team.name if team else None,
    )


@router.post('/', response_model=UserListItem, status_code=status.HTTP_201_CREATED, name='users-create')
def create_user(
    payload: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    _ensure_unique_username(db, payload.username)
    workshop, team = _ensure_workshop_and_team(db, workshop_id=payload.workshop_id, team_id=payload.team_id)

    item = User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        pin_code=payload.pin_code,
        name=payload.name,
        role=payload.role,
        workshop_id=payload.workshop_id,
        team_id=payload.team_id,
        data_scope_type=_resolve_scope_type(
            role=payload.role,
            workshop_id=payload.workshop_id,
            team_id=payload.team_id,
            is_reviewer=payload.is_reviewer,
            is_manager=payload.is_manager,
        ),
        is_mobile_user=payload.is_mobile_user,
        is_reviewer=payload.is_reviewer,
        is_manager=payload.is_manager,
        is_active=True,
    )
    db.add(item)
    db.flush()
    if payload.bound_machine_id is not None:
        _apply_machine_binding(db, user=item, bound_machine_id=payload.bound_machine_id)
        item.data_scope_type = _resolve_scope_type(
            role=item.role,
            workshop_id=item.workshop_id,
            team_id=item.team_id,
            is_reviewer=item.is_reviewer,
            is_manager=item.is_manager,
        )
        db.flush()
        workshop = db.get(Workshop, item.workshop_id) if item.workshop_id else None
    record_entity_change(
        db,
        user=current_user,
        module='users',
        entity_type='users',
        entity_id=item.id,
        action='create',
        new_value=_serialize_user_item(
            db,
            item,
            workshop_name=workshop.name if workshop else None,
            team_name=team.name if team else None,
        ),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
        auto_commit=False,
    )
    db.commit()
    db.refresh(item)
    return _serialize_user_item(
        db,
        item,
        workshop_name=workshop.name if workshop else None,
        team_name=team.name if team else None,
    )


@router.put('/{user_id}', response_model=UserListItem, name='users-update')
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    item = db.get(User, user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='用户不存在')

    data = payload.model_dump(exclude_unset=True)
    username = data.get('username', item.username)
    _ensure_unique_username(db, username, exclude_user_id=item.id)
    workshop_id = data.get('workshop_id', item.workshop_id)
    team_id = data.get('team_id', item.team_id)
    workshop, team = _ensure_workshop_and_team(db, workshop_id=workshop_id, team_id=team_id)

    old_value = _serialize_user_item(db, item, workshop_name=None, team_name=None)
    if 'username' in data:
        item.username = data['username']
    if 'password' in data and data['password']:
        item.password_hash = get_password_hash(data['password'])
    if 'pin_code' in data:
        item.pin_code = data['pin_code']
    if 'name' in data:
        item.name = data['name']
    if 'role' in data:
        item.role = data['role']
    if 'workshop_id' in data:
        item.workshop_id = data['workshop_id']
    if 'team_id' in data:
        item.team_id = data['team_id']
    if 'is_mobile_user' in data:
        item.is_mobile_user = data['is_mobile_user']
    if 'is_reviewer' in data:
        item.is_reviewer = data['is_reviewer']
    if 'is_manager' in data:
        item.is_manager = data['is_manager']
    if 'is_active' in data:
        item.is_active = data['is_active']

    if 'bound_machine_id' in data:
        _apply_machine_binding(db, user=item, bound_machine_id=data['bound_machine_id'])
    else:
        _ensure_current_binding_matches_user_scope(db, item)
    item.data_scope_type = _resolve_scope_type(
        role=item.role,
        workshop_id=item.workshop_id,
        team_id=item.team_id,
        is_reviewer=item.is_reviewer,
        is_manager=item.is_manager,
    )
    db.flush()
    workshop = db.get(Workshop, item.workshop_id) if item.workshop_id else None
    team = db.get(Team, item.team_id) if item.team_id else None
    record_entity_change(
        db,
        user=current_user,
        module='users',
        entity_type='users',
        entity_id=item.id,
        action='update',
        old_value=old_value,
        new_value=_serialize_user_item(
            db,
            item,
            workshop_name=workshop.name if workshop else None,
            team_name=team.name if team else None,
        ),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
        auto_commit=False,
    )
    db.commit()
    db.refresh(item)
    return _serialize_user_item(
        db,
        item,
        workshop_name=workshop.name if workshop else None,
        team_name=team.name if team else None,
    )


@router.delete('/{user_id}', name='users-delete')
def deactivate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    item = db.get(User, user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='用户不存在')

    item.is_active = False
    db.flush()
    record_entity_change(
        db,
        user=current_user,
        module='users',
        entity_type='users',
        entity_id=item.id,
        action='deactivate',
        old_value={'is_active': True},
        new_value={'is_active': False},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
        auto_commit=False,
    )
    db.commit()
    return {'success': True, 'message': '用户已停用'}


@router.post('/{user_id}/reset-password', response_model=UserResetPasswordResponse, name='users-reset-password')
def reset_user_password(
    user_id: int,
    payload: UserResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_admin(current_user)
    item = db.get(User, user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='用户不存在')

    old_value = {'pin_code': item.pin_code}
    item.password_hash = get_password_hash(payload.password)
    if payload.pin_code is not None:
        item.pin_code = payload.pin_code
    db.flush()
    record_entity_change(
        db,
        user=current_user,
        module='users',
        entity_type='users',
        entity_id=item.id,
        action='reset_password',
        old_value=old_value,
        new_value={'pin_code': item.pin_code},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
        auto_commit=False,
    )
    db.commit()
    return {'id': item.id, 'username': item.username, 'message': '密码已重置'}
