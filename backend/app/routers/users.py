from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.auth import get_password_hash
from app.core.deps import get_current_user, get_db
from app.models.master import Equipment, Team, Workshop
from app.models.system import User
from app.schemas.common import PaginatedResponse
from app.schemas.users import UserCreateRequest, UserListItem, UserResetPasswordRequest, UserResetPasswordResponse, UserUpdateRequest
from app.services.audit_service import record_entity_change


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
    record_entity_change(
        db,
        user=current_user,
        module='users',
        entity_type='users',
        entity_id=item.id,
        action='create',
        new_value={
            'username': item.username,
            'name': item.name,
            'role': item.role,
            'workshop_id': item.workshop_id,
            'team_id': item.team_id,
            'is_mobile_user': item.is_mobile_user,
            'is_reviewer': item.is_reviewer,
            'is_manager': item.is_manager,
            'is_active': item.is_active,
        },
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

    old_value = _serialize_user_row(item, None, None)
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

    item.data_scope_type = _resolve_scope_type(
        role=item.role,
        workshop_id=item.workshop_id,
        team_id=item.team_id,
        is_reviewer=item.is_reviewer,
        is_manager=item.is_manager,
    )
    db.flush()
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
