from datetime import time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.master import Employee, MasterCodeAlias, Team, Workshop
from app.models.shift import ShiftConfig
from app.models.system import AuditLog, User


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'master-write-permissions.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            Employee.__table__,
            ShiftConfig.__table__,
            MasterCodeAlias.__table__,
            User.__table__,
            AuditLog.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)


def seed_master_rows(session_factory) -> None:
    with session_factory() as db:
        workshop = Workshop(code='JZ', name='精整车间', workshop_type='finishing', sort_order=1, is_active=True)
        db.add(workshop)
        db.flush()
        team = Team(code='JZ-A', name='精整A班', workshop_id=workshop.id, sort_order=1, is_active=True)
        db.add(team)
        db.flush()
        db.add_all(
            [
                Employee(employee_no='E001', name='张三', workshop_id=workshop.id, team_id=team.id, is_active=True),
                ShiftConfig(
                    code='A',
                    name='长白班',
                    shift_type='day',
                    start_time=time(7, 30),
                    end_time=time(15, 30),
                    sort_order=1,
                    is_active=True,
                ),
                MasterCodeAlias(
                    entity_type='workshop',
                    canonical_code='JZ',
                    alias_code='精整',
                    alias_name='精整车间',
                    source_type='mes',
                    is_active=True,
                ),
            ]
        )
        db.commit()


def fake_manager_user() -> User:
    return User(
        id=2,
        username='manager',
        password_hash='x',
        name='普通管理查看用户',
        role='manager',
        data_scope_type='all',
        is_mobile_user=False,
        is_reviewer=True,
        is_manager=True,
        is_active=True,
    )


def test_non_admin_cannot_write_master_reference_data(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    seed_master_rows(session_factory)

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_manager_user
    client = TestClient(app)

    cases = [
        ('post', '/api/v1/master/workshops', {'code': 'LX', 'name': '拉矫车间', 'workshop_type': 'finishing'}),
        ('put', '/api/v1/master/workshops/1', {'name': '精整车间-改'}),
        ('delete', '/api/v1/master/workshops/1', None),
        ('post', '/api/v1/master/teams', {'workshop_id': 1, 'code': 'JZ-B', 'name': '精整B班'}),
        ('put', '/api/v1/master/teams/1', {'name': '精整A班-改'}),
        ('delete', '/api/v1/master/teams/1', None),
        ('post', '/api/v1/master/employees', {'employee_no': 'E002', 'name': '李四', 'workshop_id': 1, 'team_id': 1}),
        ('put', '/api/v1/master/employees/1', {'name': '张三-改'}),
        ('delete', '/api/v1/master/employees/1', None),
        (
            'post',
            '/api/v1/master/shift-configs',
            {'code': 'B', 'name': '小夜班', 'shift_type': 'evening', 'start_time': '15:30:00', 'end_time': '23:30:00'},
        ),
        ('put', '/api/v1/master/shift-configs/1', {'name': '长白班-改'}),
        ('delete', '/api/v1/master/shift-configs/1', None),
        (
            'post',
            '/api/v1/master/aliases',
            {
                'entity_type': 'workshop',
                'canonical_code': 'JZ',
                'alias_code': '精整二',
                'alias_name': '精整二车间',
                'source_type': 'mes',
            },
        ),
        ('put', '/api/v1/master/aliases/1', {'alias_name': '精整车间-改'}),
        ('delete', '/api/v1/master/aliases/1', None),
    ]

    try:
        for method, path, payload in cases:
            response = getattr(client, method)(path, json=payload) if payload is not None else getattr(client, method)(path)
            assert response.status_code == 403, f'{method.upper()} {path} should require admin'
    finally:
        app.dependency_overrides.clear()
