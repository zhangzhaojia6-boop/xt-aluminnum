from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.master import Equipment, MasterCodeAlias, MesTerminalBinding, Team, Workshop
from app.models.system import AuditLog, User
from app.services import master_service


class DummyDB:
    pass


def test_alias_crud_endpoints(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=10, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_list(db, *, entity_type=None, source_type=None, is_active=None):
        return [
            SimpleNamespace(
                id=1,
                entity_type='workshop',
                canonical_code='W1',
                alias_code='WK-01',
                alias_name='熔铸',
                source_type='mes_export',
                is_active=True,
            )
        ]

    def fake_create(db, *, payload, operator):
        assert payload['canonical_code'] == 'W1'
        return SimpleNamespace(
            id=2,
            entity_type=payload['entity_type'],
            canonical_code=payload['canonical_code'],
            alias_code=payload.get('alias_code'),
            alias_name=payload.get('alias_name'),
            source_type=payload.get('source_type'),
            is_active=True,
        )

    def fake_update(db, *, alias_id, payload, operator):
        assert alias_id == 2
        return SimpleNamespace(
            id=2,
            entity_type=payload.get('entity_type', 'workshop'),
            canonical_code=payload.get('canonical_code', 'W1'),
            alias_code=payload.get('alias_code', 'WK-01'),
            alias_name=payload.get('alias_name', '熔铸'),
            source_type=payload.get('source_type', 'mes_export'),
            is_active=payload.get('is_active', True),
        )

    def fake_delete(db, *, alias_id, operator):
        assert alias_id == 2
        return None

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.master.master_service.list_aliases', fake_list)
    monkeypatch.setattr('app.routers.master.master_service.create_alias', fake_create)
    monkeypatch.setattr('app.routers.master.master_service.update_alias', fake_update)
    monkeypatch.setattr('app.routers.master.master_service.delete_alias', fake_delete)

    client = TestClient(app)
    response = client.get('/api/v1/master/aliases')
    assert response.status_code == 200
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['canonical_code'] == 'W1'

    create = client.post(
        '/api/v1/master/aliases',
        json={'entity_type': 'workshop', 'canonical_code': 'W1', 'alias_code': 'WK-01', 'alias_name': '熔铸'},
    )
    assert create.status_code == 201
    assert create.json()['id'] == 2

    update = client.put('/api/v1/master/aliases/2', json={'alias_name': '熔铸车间'})
    assert update.status_code == 200
    assert update.json()['alias_name'] == '熔铸车间'

    delete = client.delete('/api/v1/master/aliases/2')
    assert delete.status_code == 200

    app.dependency_overrides.clear()


def test_mes_terminal_binding_crud_endpoints(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=10, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_list(db, *, terminal_code=None, workshop_name=None, process_name=None, is_active=None):
        return [
            SimpleNamespace(
                id=1,
                terminal_code='PC-JZ-01',
                terminal_name='精整包装一体机',
                mes_device_name='PC',
                workshop_name='精整',
                process_name='包装',
                equipment_id=21,
                confidence='high',
                valid_from=None,
                valid_to=None,
                is_active=True,
            )
        ]

    def fake_create(db, *, payload, operator):
        assert payload['terminal_code'] == 'PC-JZ-01'
        return SimpleNamespace(id=2, **payload)

    def fake_update(db, *, binding_id, payload, operator):
        assert binding_id == 2
        return SimpleNamespace(
            id=2,
            terminal_code=payload.get('terminal_code', 'PC-JZ-01'),
            terminal_name=payload.get('terminal_name', '精整包装一体机'),
            mes_device_name=payload.get('mes_device_name', 'PC'),
            workshop_name=payload.get('workshop_name', '精整'),
            process_name=payload.get('process_name', '包装'),
            equipment_id=payload.get('equipment_id', 21),
            confidence=payload.get('confidence', 'high'),
            valid_from=payload.get('valid_from'),
            valid_to=payload.get('valid_to'),
            is_active=payload.get('is_active', True),
        )

    def fake_delete(db, *, binding_id, operator):
        assert binding_id == 2
        return None

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.master.master_service.list_mes_terminal_bindings', fake_list)
    monkeypatch.setattr('app.routers.master.master_service.create_mes_terminal_binding', fake_create)
    monkeypatch.setattr('app.routers.master.master_service.update_mes_terminal_binding', fake_update)
    monkeypatch.setattr('app.routers.master.master_service.delete_mes_terminal_binding', fake_delete)

    client = TestClient(app)
    response = client.get('/api/v1/master/mes-terminal-bindings')
    assert response.status_code == 200
    assert response.json()['items'][0]['terminal_code'] == 'PC-JZ-01'

    create = client.post(
        '/api/v1/master/mes-terminal-bindings',
        json={
            'terminal_code': 'PC-JZ-01',
            'terminal_name': '精整包装一体机',
            'mes_device_name': 'PC',
            'workshop_name': '精整',
            'process_name': '包装',
            'equipment_id': 21,
        },
    )
    assert create.status_code == 201
    assert create.json()['id'] == 2

    update = client.put('/api/v1/master/mes-terminal-bindings/2', json={'confidence': 'medium'})
    assert update.status_code == 200
    assert update.json()['confidence'] == 'medium'

    delete = client.delete('/api/v1/master/mes-terminal-bindings/2')
    assert delete.status_code == 200

    app.dependency_overrides.clear()


def test_delete_alias_soft_deactivates_instead_of_physical_delete(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'alias-soft-delete.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[Workshop.__table__, Team.__table__, User.__table__, MasterCodeAlias.__table__, AuditLog.__table__],
    )
    db = sessionmaker(bind=engine, future=True, expire_on_commit=False)()
    alias = MasterCodeAlias(
        entity_type='workshop',
        canonical_code='OLD',
        alias_code='旧车间',
        alias_name='旧车间',
        source_type='mes_mvc',
        is_active=True,
    )
    db.add(alias)
    db.commit()

    master_service.delete_alias(db, alias_id=alias.id, operator=None)

    saved_alias = db.get(MasterCodeAlias, alias.id)
    assert saved_alias is not None
    assert saved_alias.is_active is False
    audit_log = db.query(AuditLog).filter(AuditLog.record_id == alias.id).one()
    assert audit_log.action == 'deactivate_alias'


def test_mes_terminal_binding_service_validates_equipment_and_soft_deactivates(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'terminal-binding.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Equipment.__table__,
            MesTerminalBinding.__table__,
            User.__table__,
            AuditLog.__table__,
        ],
    )
    db = sessionmaker(bind=engine, future=True, expire_on_commit=False)()
    db.add(Workshop(id=1, code='JZ', name='精整', workshop_type='finishing', sort_order=1, is_active=True))
    db.add(
        Equipment(
            id=21,
            code='JZ-PACK-1',
            name='包装入库线',
            workshop_id=1,
            equipment_type='slitter',
            operational_status='running',
            is_active=True,
        )
    )
    db.commit()

    binding = master_service.create_mes_terminal_binding(
        db,
        payload={
            'terminal_code': 'PC-JZ-01',
            'terminal_name': '精整包装一体机',
            'mes_device_name': 'PC',
            'workshop_name': '精整',
            'process_name': '包装',
            'equipment_id': 21,
        },
        operator=None,
    )
    assert binding.id is not None

    updated = master_service.update_mes_terminal_binding(
        db,
        binding_id=binding.id,
        payload={'confidence': 'medium'},
        operator=None,
    )
    assert updated.confidence == 'medium'

    master_service.delete_mes_terminal_binding(db, binding_id=binding.id, operator=None)

    saved = db.get(MesTerminalBinding, binding.id)
    assert saved is not None
    assert saved.is_active is False
    actions = {row.action for row in db.query(AuditLog).all()}
    assert 'create_mes_terminal_binding' in actions
    assert 'update_mes_terminal_binding' in actions
    assert 'deactivate_mes_terminal_binding' in actions
