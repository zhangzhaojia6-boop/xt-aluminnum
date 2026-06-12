from app.models.master import Workshop
from app.database import Base
from app.models.master import Equipment, Team
from app.models.system import User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from scripts import cleanup_unused_workshops
from scripts.cleanup_unused_workshops import should_keep_workshop


def _workshop(code: str, name: str, *, is_active: bool = True) -> Workshop:
    return Workshop(code=code, name=name, is_active=is_active)


def test_cleanup_keeps_thirteen_active_production_workshops() -> None:
    keep, reason = should_keep_workshop(_workshop('CH', '淬火车间'))

    assert keep is True
    assert '13个生产车间' in reason


def test_cleanup_keeps_finished_goods_storage_and_inactive_workshops() -> None:
    keep_storage, storage_reason = should_keep_workshop(_workshop('CPK', '成品库'))
    keep_inactive, inactive_reason = should_keep_workshop(_workshop('OLD', '冷轧三车间', is_active=False))

    assert keep_storage is True
    assert '成品库' in storage_reason
    assert keep_inactive is True
    assert '未启用' in inactive_reason


def test_cleanup_deactivates_active_useless_workshop() -> None:
    keep, reason = should_keep_workshop(_workshop('ZR5', '铸轧五'))

    assert keep is False
    assert '停用' in reason


def test_cleanup_apply_soft_deactivates_workshop_children(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'cleanup-workshops.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Equipment.__table__,
            Team.__table__,
            User.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    monkeypatch.setattr(cleanup_unused_workshops, 'get_sessionmaker', lambda: SessionLocal)

    with SessionLocal() as db:
        db.add_all([
            Workshop(id=1, code='ZR5', name='铸轧五', is_active=True),
            Workshop(id=2, code='CPK', name='成品库', is_active=True),
            Equipment(id=1, workshop_id=1, code='ZR5-1', name='铸轧五1#机', is_active=True),
            Team(id=1, workshop_id=1, code='ZR5-A', name='铸轧五A班', is_active=True),
            User(id=1, username='ZR5-EN', password_hash='x', name='铸轧五 电工', role='energy_stat', workshop_id=1, is_active=True),
            User(id=2, username='CPK-CS', password_hash='x', name='成品库 内勤', role='consumable_stat', workshop_id=2, is_active=True),
        ])
        db.commit()

    result = cleanup_unused_workshops.cleanup_unused_workshops(apply=True)

    assert result['changed_count'] == 1
    assert result['changed'][0]['user_count'] == 1
    with SessionLocal() as db:
        assert db.get(Workshop, 1).is_active is False
        assert db.get(Equipment, 1).is_active is False
        assert db.get(Team, 1).is_active is False
        assert db.get(User, 1).is_active is False
        assert db.get(Workshop, 2).is_active is True
        assert db.get(User, 2).is_active is True
