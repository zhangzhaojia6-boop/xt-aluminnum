import os
import sys

from app.database import get_sessionmaker
from app.core.auth import get_password_hash, verify_password
from app.models.system import User

new_pwd = os.environ.get("ADMIN_NEW_PASSWORD")
if not new_pwd:
    print("缺少 ADMIN_NEW_PASSWORD，拒绝使用硬编码密码重置管理员。", file=sys.stderr)
    raise SystemExit(2)

db = get_sessionmaker()()
u = db.query(User).filter(User.username == "admin").first()
u.password_hash = get_password_hash(new_pwd)
db.commit()
print(f"reset admin: id={u.id} username={u.username} role={u.role}")
ok = verify_password(new_pwd, u.password_hash)
print(f"verify -> {ok}")
