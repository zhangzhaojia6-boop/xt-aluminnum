from app.database import get_sessionmaker
from app.core.auth import get_password_hash, verify_password
from app.models.system import User

db = get_sessionmaker()()
u = db.query(User).filter(User.username == "admin").first()
new_pwd = "zzj200123"
u.password_hash = get_password_hash(new_pwd)
db.commit()
print(f"reset admin: id={u.id} username={u.username} role={u.role}")
ok = verify_password(new_pwd, u.password_hash)
print(f"verify -> {ok}")
