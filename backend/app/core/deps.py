from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.requests import HTTPConnection
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import decode_token
from app.database import get_db
from app.domain.procurement_flow import PROCUREMENT_ONLY_ROLE
from app.models.system import User

security = HTTPBearer(auto_error=False)


def _procurement_only_paths() -> tuple[str, ...]:
    return (
        f'{settings.API_V1_PREFIX}/procurement',
        f'{settings.API_V1_PREFIX}/auth',
        f'{settings.API_V1_PREFIX}/user/preferences',
    )


def get_current_user(
    connection: HTTPConnection,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid authentication credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )
    if credentials is None:
        raise credentials_exception

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise credentials_exception

    user_id = payload.get('sub')
    if user_id is None:
        raise credentials_exception

    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == uid, User.is_active.is_(True)).first()
    if user is None:
        raise credentials_exception
    # 采购账号只开采购接口，避免只带登录校验的接口把工厂数据暴露给它
    if user.role == PROCUREMENT_ONLY_ROLE and not connection.url.path.startswith(_procurement_only_paths()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Permission denied')
    return user


def require_roles(*roles: str) -> Callable:
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Permission denied')
        return current_user

    return checker
