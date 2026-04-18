import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.core.auth import get_password_hash
from app.database import get_sessionmaker
from app.models.system import User


def create_admin(username: str, password: str, name: str) -> User:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.password_hash = get_password_hash(password)
            user.name = name
            user.role = 'admin'
            user.data_scope_type = 'all'
            user.assigned_shift_ids = None
            user.is_mobile_user = False
            user.is_reviewer = True
            user.is_manager = True
            user.is_active = True
        else:
            user = User(
                username=username,
                password_hash=get_password_hash(password),
                name=name,
                role='admin',
                data_scope_type='all',
                assigned_shift_ids=None,
                is_mobile_user=False,
                is_reviewer=True,
                is_manager=True,
                is_active=True,
            )
            db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', default=settings.INIT_ADMIN_USERNAME)
    parser.add_argument('--password', default=settings.INIT_ADMIN_PASSWORD)
    parser.add_argument('--name', default=settings.INIT_ADMIN_NAME)
    args = parser.parse_args()
    user = create_admin(args.username, args.password, args.name)
    print(f'admin ready: {user.username}')


if __name__ == '__main__':
    main()
