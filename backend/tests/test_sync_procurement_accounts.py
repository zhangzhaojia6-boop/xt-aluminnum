from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.config import settings
from app.core.auth import create_access_token
from app.database import get_db
from app.domain import procurement_flow as flow
from app.main import app
from app.models.agent_communication import AgentChannelBinding, AgentOutboxMessage, AgentProfile, CommunicationChannel
from app.models.base import Base
from app.models.master import Team, Workshop
from app.models.procurement import ProcurementAssignment, ProcurementDocument, ProcurementQuote, ProcurementRequest, ProcurementStepLog
from app.models.system import AuditLog, User
from app.services import procurement_service as service
from scripts.sync_procurement_accounts import sync_accounts

TABLES = [model.__table__ for model in (
    Workshop, Team, User, AuditLog, AgentProfile, CommunicationChannel, AgentChannelBinding, AgentOutboxMessage,
    ProcurementAssignment, ProcurementRequest, ProcurementQuote, ProcurementDocument, ProcurementStepLog,
)]


@pytest.fixture()
def db():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine, future=True, expire_on_commit=False)()
    session.add(User(id=1, username='admin', password_hash='x', name='管理员', role='admin'))
    session.add(AgentProfile(code=service.NOTIFY_AGENT, name='调度', agent_type='guard', is_active=True))
    session.commit()
    yield session
    session.close()


def _actor(db):
    return db.get(User, 1)


ENTRY = {'name': '王仓库', 'dingtalk_user_id': 'dt-1', 'roles': ['warehouse']}


def test_preview_writes_nothing(db):
    plans = sync_accounts(db, [ENTRY], actor=_actor(db), apply=False)
    assert plans[0]['action'] == 'create'
    assert db.query(User).count() == 1
    assert db.query(ProcurementAssignment).count() == 0


def test_apply_creates_a_powerless_account_with_a_dry_run_channel(db):
    sync_accounts(db, [ENTRY], actor=_actor(db), apply=True)
    user = db.query(User).filter(User.dingtalk_user_id == 'dt-1').one()
    assert user.role == flow.PROCUREMENT_ONLY_ROLE
    assert (user.is_manager, user.is_reviewer, user.is_mobile_user) == (False, False, False)
    assert user.username == 'pc-dt-1'
    assert user.password_hash != 'x'
    assert service.user_roles(db, user) == {'warehouse'}
    channel = db.query(CommunicationChannel).filter(CommunicationChannel.channel_key == service.channel_key_for(user.id)).one()
    assert channel.dry_run is True
    assert channel.target_key == 'dt-1'
    assert db.query(AuditLog).filter(AuditLog.action == 'procurement_account_sync').count() == 1


def test_apply_twice_changes_nothing(db):
    sync_accounts(db, [ENTRY], actor=_actor(db), apply=True)
    sync_accounts(db, [ENTRY], actor=_actor(db), apply=True)
    assert db.query(User).filter(User.dingtalk_user_id == 'dt-1').count() == 1
    assert db.query(ProcurementAssignment).count() == 1
    assert db.query(CommunicationChannel).count() == 1


def test_existing_active_account_keeps_its_role(db):
    db.add(User(id=2, username='dir', password_hash='x', name='王仓库', role='workshop_director', dingtalk_user_id='dt-1'))
    db.commit()
    sync_accounts(db, [ENTRY], actor=_actor(db), apply=True)
    assert db.get(User, 2).role == 'workshop_director'
    assert service.user_roles(db, db.get(User, 2)) == {'warehouse', 'workshop_director'}


def test_same_name_is_never_bound_automatically(db):
    db.add(User(id=2, username='old', password_hash='x', name='王仓库', role='machine_operator'))
    db.commit()
    plans = sync_accounts(db, [ENTRY], actor=_actor(db), apply=True)
    assert plans[0]['action'] == 'skip'
    assert db.get(User, 2).dingtalk_user_id is None
    assert db.query(ProcurementAssignment).count() == 0


def test_disabled_account_is_not_revived(db):
    db.add(User(id=2, username='old', password_hash='x', name='王仓库', role='machine_operator', dingtalk_user_id='dt-1', is_active=False))
    db.commit()
    plans = sync_accounts(db, [ENTRY], actor=_actor(db), apply=True)
    assert plans[0]['action'] == 'skip'
    assert db.get(User, 2).is_active is False


def test_unknown_role_is_rejected(db):
    plans = sync_accounts(db, [{**ENTRY, 'roles': ['admin']}], actor=_actor(db), apply=True)
    assert plans[0]['action'] == 'invalid'
    assert db.query(User).count() == 1


def test_procurement_account_can_only_reach_procurement_and_auth(db, monkeypatch):
    monkeypatch.setattr(settings, 'PROCUREMENT_ENABLED', True)
    sync_accounts(db, [ENTRY], actor=_actor(db), apply=True)
    user = db.query(User).filter(User.dingtalk_user_id == 'dt-1').one()
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        headers = {'Authorization': f'Bearer {create_access_token(subject=str(user.id))}'}
        prefix = settings.API_V1_PREFIX
        assert client.get(f'{prefix}/procurement/meta', headers=headers).status_code == 200
        assert client.get(f'{prefix}/auth/me', headers=headers).status_code == 200
        assert client.get(f'{prefix}/user/preferences', headers=headers).status_code != 403
        for path in ('/dashboard/daily-production', '/users/', '/reports/daily', '/mes/extended/wip-total-snapshots'):
            assert client.get(f'{prefix}{path}', headers=headers).status_code == 403, path
    finally:
        app.dependency_overrides.pop(get_db, None)
