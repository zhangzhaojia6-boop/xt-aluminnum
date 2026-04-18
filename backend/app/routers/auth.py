from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import create_access_token, get_password_hash, verify_password
from app.core.deps import get_current_user, get_db
from app.models.master import Equipment, Workshop
from app.models.system import User
from app.schemas.auth import LoginRequest, LoginResponse, QrLoginRequest, QrLoginResponse, UserInfo
from app.services.audit_service import log_action
from app.services.equipment_service import build_machine_info

router = APIRouter(tags=['auth'])


@router.post('/login', response_model=LoginResponse)
def login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> dict:
    user = db.query(User).filter(User.username == body.username).first()
    if not user and body.username == settings.INIT_ADMIN_USERNAME and body.password == settings.INIT_ADMIN_PASSWORD:
        user = User(
            username=settings.INIT_ADMIN_USERNAME,
            password_hash=get_password_hash(settings.INIT_ADMIN_PASSWORD),
            name=settings.INIT_ADMIN_NAME,
            role='admin',
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail='Invalid username or password')
    if not user.is_active:
        raise HTTPException(status_code=403, detail='User is disabled')

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id))
    bound_equipment = (
        db.query(Equipment)
        .filter(Equipment.bound_user_id == user.id)
        .order_by(Equipment.id.asc())
        .first()
    )
    machine_info = None
    if bound_equipment is not None:
        workshop = db.get(Workshop, bound_equipment.workshop_id)
        machine_info = build_machine_info(bound_equipment, workshop=workshop)

    log_action(
        db,
        user_id=user.id,
        user_name=user.name,
        action='login',
        module='auth',
        table_name='users',
        record_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    user_info = UserInfo.model_validate(user)
    return {
        'access_token': token,
        'token_type': 'bearer',
        'user': user_info.model_dump(),
        'machine_info': machine_info,
    }


@router.get('/me', response_model=UserInfo)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post('/qr-login', response_model=QrLoginResponse, name='auth-qr-login')
def qr_login(
    request: Request,
    body: QrLoginRequest,
    db: Session = Depends(get_db),
) -> dict:
    equipment = db.query(Equipment).filter(Equipment.qr_code == body.qr_code).first()
    if equipment is None or not equipment.is_active:
        raise HTTPException(status_code=404, detail='未找到该机台')
    if equipment.operational_status != 'running':
        raise HTTPException(status_code=403, detail='该机台已停机')
    if equipment.bound_user_id is None:
        raise HTTPException(status_code=404, detail='该机台未绑定账号，请联系管理员')

    user = db.get(User, equipment.bound_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail='该机台未绑定账号，请联系管理员')
    if not user.is_active:
        raise HTTPException(status_code=403, detail='该机台已停机')

    workshop = db.get(Workshop, equipment.workshop_id)
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    machine_info = build_machine_info(equipment, workshop=workshop)
    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            'machine_id': equipment.id,
            'workshop_id': equipment.workshop_id,
            'qr_code': equipment.qr_code,
        },
    )
    log_action(
        db,
        user_id=user.id,
        user_name=user.name,
        action='qr_login',
        module='auth',
        table_name='equipment',
        record_id=equipment.id,
        new_value=machine_info,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
    )
    user_info = UserInfo.model_validate(user)
    return {
        'access_token': token,
        'token_type': 'bearer',
        'user': user_info.model_dump(),
        'machine_info': machine_info,
    }


@router.post('/logout')
def logout() -> dict:
    return {'success': True, 'data': None, 'message': 'logout success', 'total': None}
