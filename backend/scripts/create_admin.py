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
from app.services.bootstrap import apply_admin_account_contract


def create_admin(username: str, password: str, name: str, *, reset_password: bool = False) -> User:
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            apply_admin_account_contract(user, name=name, password=password if reset_password else None)
        else:
            user = User(
                username=username,
                password_hash=get_password_hash(password),
                name='admin',
                role='admin',
            )
            apply_admin_account_contract(user, name=name)
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
    parser.add_argument('--reset-password', action='store_true')
    args = parser.parse_args()
    user = create_admin(args.username, args.password, args.name, reset_password=args.reset_password)
    print(f'admin ready: {user.username}')


if __name__ == '__main__':
    main()
