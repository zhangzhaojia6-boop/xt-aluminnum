from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.core.workshop_templates import get_workshop_template
from app.database import Base
from app.main import app
from app.models.master import Workshop, WorkshopTemplateConfig
from app.models.system import User


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workshop-template-admin.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[Workshop.__table__, WorkshopTemplateConfig.__table__],
    )
    return sessionmaker(bind=engine, future=True)


def _admin_user() -> User:
    return User(
        id=1,
        username='admin',
        password_hash='x',
        name='Admin',
        role='admin',
        is_active=True,
    )


def _leader_user() -> User:
    return User(
        id=9,
        username='leader',
        password_hash='x',
        name='Leader',
        role='shift_leader',
        is_active=True,
    )


def test_get_workshop_template_prefers_workshop_code_override_and_hides_disabled_fields(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    with session_factory() as db:
        db.add(Workshop(code='LZ1450', name='1450冷轧车间', workshop_type='cold_roll', sort_order=1, is_active=True))
        db.add(
            WorkshopTemplateConfig(
                template_key='LZ1450',
                display_name='1450冷轧模板',
                tempo='fast',
                supports_ocr=False,
                entry_fields=[
                    {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True, 'enabled': True},
                    {'name': 'input_spec', 'label': '上机规格', 'type': 'text', 'required': True, 'enabled': True},
                    {'name': 'alloy_grade', 'label': '合金成分', 'type': 'text', 'required': True, 'enabled': True},
                    {'name': 'material_state', 'label': '状态', 'type': 'text', 'required': False, 'enabled': True},
                    {'name': 'on_machine_time', 'label': '上机时间', 'type': 'time', 'required': False, 'enabled': True},
                    {'name': 'off_machine_time', 'label': '下机时间', 'type': 'time', 'required': False, 'enabled': True},
                    {'name': 'input_weight', 'label': '上机重量', 'type': 'number', 'unit': 'kg', 'required': True, 'enabled': True},
                    {'name': 'output_weight', 'label': '下机重量', 'type': 'number', 'unit': 'kg', 'required': True, 'enabled': True},
                    {'name': 'spool_weight', 'label': '套筒重量', 'type': 'number', 'unit': 'kg', 'required': False, 'enabled': False},
                    {'name': 'trim_weight', 'label': '切边重量', 'type': 'number', 'unit': 'kg', 'required': False, 'enabled': True},
                ],
                extra_fields=[],
                qc_fields=[],
                readonly_fields=[
                    {
                        'name': 'yield_rate',
                        'label': '成品率',
                        'type': 'number',
                        'unit': '%',
                        'compute': 'output_weight / input_weight * 100',
                        'enabled': True,
                    }
                ],
                is_active=True,
            )
        )
        db.commit()

        payload = get_workshop_template('LZ1450', user_role='shift_leader', db=db)

    assert payload['display_name'] == '1450冷轧模板'
    assert [field['name'] for field in payload['entry_fields']] == [
        'batch_no',
        'input_spec',
        'alloy_grade',
        'material_state',
        'on_machine_time',
        'off_machine_time',
        'input_weight',
        'output_weight',
        'trim_weight',
    ]
    assert 'spool_weight' not in [field['name'] for field in payload['entry_fields']]
    assert [field['name'] for field in payload['readonly_fields']] == ['yield_rate']


def test_admin_can_upsert_workshop_template_and_public_template_endpoint_reads_it(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    with session_factory() as db:
        db.add(Workshop(code='JZ', name='精整车间', workshop_type='finishing', sort_order=1, is_active=True))
        db.commit()

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = _admin_user
    client = TestClient(app)
    try:
        response = client.put(
            '/api/v1/master/workshop-templates/JZ',
            json={
                'display_name': '精整模板',
                'tempo': 'fast',
                'supports_ocr': False,
                'entry_fields': [
                    {'name': 'batch_no', 'label': '批号', 'type': 'text', 'required': True, 'enabled': True},
                    {'name': 'input_spec', 'label': '上机规格', 'type': 'text', 'required': True, 'enabled': True},
                    {'name': 'tray_weight', 'label': '托盘重量', 'type': 'number', 'unit': 'kg', 'required': False, 'enabled': True},
                ],
                'extra_fields': [
                    {'name': 'edge_protector', 'label': '护角数量', 'type': 'number', 'unit': '个', 'required': False, 'enabled': True}
                ],
                'qc_fields': [],
                'readonly_fields': [
                    {
                        'name': 'yield_rate',
                        'label': '成品率',
                        'type': 'number',
                        'unit': '%',
                        'compute': 'output_weight / input_weight * 100',
                        'enabled': True,
                    }
                ],
            },
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = _leader_user
    try:
        template_response = client.get('/api/v1/templates/JZ')
    finally:
        app.dependency_overrides.clear()

    assert template_response.status_code == 200
    payload = template_response.json()
    assert payload['display_name'] == '精整模板'
    assert [field['name'] for field in payload['entry_fields']] == ['batch_no', 'input_spec', 'tray_weight']
    assert [field['name'] for field in payload['extra_fields']] == ['edge_protector']
    assert [field['name'] for field in payload['readonly_fields']] == ['yield_rate']
