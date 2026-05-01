from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary, can_view_work_order_entries
from app.database import Base
from app.main import app
from app.models.master import Workshop, WorkshopTemplateConfig
from app.models.system import User
from app.routers.mobile import entry_fields
from app.services.mobile_report_service import ShiftContext, get_current_shift, get_mobile_bootstrap


class DummyDB:
    pass


def test_mobile_bootstrap_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=18,
            username='leader',
            password_hash='x',
            name='Leader',
            role='team_leader',
            workshop_id=1,
            team_id=10,
            is_active=True,
        )

    def fake_bootstrap(db, *, current_user):
        assert current_user.id == 18
        return {
            'entry_mode': 'web_debug',
            'data_entry_mode': 'manual_only',
            'scan_assist_enabled': False,
            'mes_display_enabled': False,
            'phase_notice': '当前阶段先由主操手工录入，系统自动校验与汇总；扫码补数与 MES 自动带数后续开放。',
            'dingtalk_enabled': False,
            'user_has_dingtalk_binding': False,
            'current_identity_source': 'dev_fallback',
            'current_scope_summary': {
                'role': 'team_leader',
                'data_scope_type': 'self_team',
                'workshop_id': 1,
                'team_id': 10,
                'is_mobile_user': True,
                'is_reviewer': False,
                'is_manager': False,
            },
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.mobile.mobile_report_service.get_mobile_bootstrap', fake_bootstrap)

    client = TestClient(app)
    response = client.get('/api/v1/mobile/bootstrap')
    assert response.status_code == 200
    assert response.json()['entry_mode'] == 'web_debug'
    assert response.json()['data_entry_mode'] == 'manual_only'
    assert response.json()['scan_assist_enabled'] is False
    assert response.json()['mes_display_enabled'] is False
    assert '主操手工录入' in response.json()['phase_notice']
    assert response.json()['current_scope_summary']['team_id'] == 10

    app.dependency_overrides.clear()


def test_get_mobile_bootstrap_includes_manual_first_contract(monkeypatch) -> None:
    current_user = User(
        id=18,
        username='leader',
        password_hash='x',
        name='Leader',
        role='team_leader',
        workshop_id=1,
        team_id=10,
        is_active=True,
    )

    monkeypatch.setattr('app.services.mobile_report_service.assert_mobile_user_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.mobile_report_service.dingtalk_service.service.build_mobile_bootstrap',
        lambda *_args, **_kwargs: {
            'entry_mode': 'web_debug',
            'dingtalk_enabled': False,
            'user_has_dingtalk_binding': False,
            'current_identity_source': 'dev_fallback',
            'current_scope_summary': {},
        },
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service.build_scope_summary',
        lambda *_args, **_kwargs: SimpleNamespace(role='team_leader'),
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service.scope_to_dict',
        lambda *_args, **_kwargs: {'role': 'team_leader', 'team_id': 10},
    )
    monkeypatch.setattr('app.services.mobile_report_service.get_bound_machine_for_user', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.mobile_report_service.settings.MOBILE_DATA_ENTRY_MODE', 'manual_only')
    monkeypatch.setattr('app.services.mobile_report_service.settings.MOBILE_SCAN_ASSIST_ENABLED', False)
    monkeypatch.setattr('app.services.mobile_report_service.settings.MOBILE_MES_DISPLAY_ENABLED', False)

    payload = get_mobile_bootstrap(DummyDB(), current_user=current_user)

    assert payload['data_entry_mode'] == 'manual_only'
    assert payload['scan_assist_enabled'] is False
    assert payload['mes_display_enabled'] is False
    assert (
        payload['phase_notice']
        == '当前阶段先由主操手工录入，系统自动校验与汇总；扫码补数与 MES 自动带数后续开放。'
    )
    assert payload['workshop_id'] == 1
    assert payload['workshop_name'] is None


def test_settings_mobile_bootstrap_defaults_are_manual_first() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV='production',
        SECRET_KEY='s' * 32,
        INIT_ADMIN_PASSWORD='P' * 12,
    )

    assert settings.MOBILE_DATA_ENTRY_MODE == 'manual_only'
    assert settings.MOBILE_SCAN_ASSIST_ENABLED is False
    assert settings.MOBILE_MES_DISPLAY_ENABLED is False
    settings.validate_runtime_settings()


def test_settings_reject_invalid_mobile_data_entry_mode() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV='production',
        SECRET_KEY='s' * 32,
        INIT_ADMIN_PASSWORD='P' * 12,
        MOBILE_DATA_ENTRY_MODE='invalid_mode',
    )

    with pytest.raises(RuntimeError, match='MOBILE_DATA_ENTRY_MODE'):
        settings.validate_runtime_settings()


@pytest.mark.parametrize(
    ('overrides', 'message'),
    [
        (
            {
                'MOBILE_DATA_ENTRY_MODE': 'manual_only',
                'MOBILE_SCAN_ASSIST_ENABLED': True,
            },
            'manual_only cannot enable MOBILE_SCAN_ASSIST_ENABLED',
        ),
        (
            {
                'MOBILE_DATA_ENTRY_MODE': 'manual_only',
                'MOBILE_MES_DISPLAY_ENABLED': True,
            },
            'manual_only cannot enable MOBILE_MES_DISPLAY_ENABLED',
        ),
        (
            {
                'MOBILE_DATA_ENTRY_MODE': 'mes_assisted',
                'MES_ADAPTER': 'null',
            },
            'mes_assisted requires MES_ADAPTER=rest_api',
        ),
    ],
)
def test_settings_reject_conflicting_mobile_bootstrap_contracts(overrides: dict, message: str) -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV='production',
        SECRET_KEY='s' * 32,
        INIT_ADMIN_PASSWORD='P' * 12,
        **overrides,
    )

    with pytest.raises(RuntimeError, match=message):
        settings.validate_runtime_settings()


@pytest.mark.parametrize('role', ['shift_leader', 'energy_stat', 'maintenance_lead', 'hydraulic_lead', 'inventory_keeper', 'utility_manager', 'contracts'])
def test_phase1_specialized_roles_are_treated_as_mobile_field_owners(role: str) -> None:
    user = User(
        id=28,
        username=f'{role}-user',
        password_hash='x',
        name='字段责任人',
        role=role,
        workshop_id=2,
        is_active=True,
    )

    summary = build_scope_summary(user)

    assert summary.is_mobile_user is True
    assert can_view_work_order_entries(summary) is True


def test_get_current_shift_returns_machine_bound_context(monkeypatch) -> None:
    current_user = User(
        id=18,
        username='ZR2-3',
        password_hash='x',
        name='铸二车间 3#机',
        role='shift_leader',
        workshop_id=2,
        is_mobile_user=True,
        is_active=True,
    )

    monkeypatch.setattr(
        'app.services.mobile_report_service.assert_mobile_user_access',
        lambda *_args, **_kwargs: SimpleNamespace(is_admin=False),
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service._infer_current_shift',
        lambda *_args, **_kwargs: ShiftContext(
            business_date=date(2026, 3, 28),
            shift=type('Shift', (), {'id': 1, 'code': 'A', 'name': '白班'})(),
            workshop=type('Workshop', (), {'id': 2, 'code': 'ZR2', 'name': '铸二车间'})(),
            team=None,
            machine=type(
                'Machine',
                (),
                {
                    'id': 12,
                    'code': 'ZR2-3',
                    'name': '3#机',
                    'shift_mode': 'three',
                    'assigned_shift_ids': [1, 2, 3],
                    'custom_fields': [{'name': 'al_liquid_kg', 'label': '铝液', 'type': 'number', 'unit': '公斤'}],
                },
            )(),
        ),
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service.dingtalk_service.service.resolve_mobile_identity',
        lambda *_args, **_kwargs: {'entry_channel': 'web_debug', 'dingtalk_ready': False, 'dingtalk_hint': None},
    )
    monkeypatch.setattr('app.services.mobile_report_service._find_mobile_report', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.mobile_report_service._active_reminders_for_context', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        'app.services.attendance_confirm_service.get_shift_confirmation_snapshot',
        lambda *_args, **_kwargs: {
            'attendance_confirmation_id': None,
            'attendance_machine_id': None,
            'attendance_machine_name': None,
            'attendance_status': 'not_started',
            'attendance_exception_count': 0,
            'attendance_pending_count': 0,
        },
    )

    payload = get_current_shift(DummyDB(), current_user=current_user)

    assert payload['workshop_name'] == '铸二车间'
    assert payload['machine_id'] == 12
    assert payload['machine_code'] == 'ZR2-3'
    assert payload['machine_name'] == '3#机'
    assert payload['is_machine_bound'] is True
    assert payload['machine_custom_fields'] == [
        {'name': 'al_liquid_kg', 'label': '铝液', 'type': 'number', 'unit': '公斤'}
    ]


def test_get_current_shift_allows_machine_user_when_other_owner_report_exists(monkeypatch) -> None:
    current_user = User(
        id=20,
        username='machine-20',
        password_hash='x',
        name='铸二车间 2#机',
        role='machine_operator',
        workshop_id=2,
        is_mobile_user=True,
        is_active=True,
    )
    existing_report = SimpleNamespace(id=88, owner_user_id=99, leader_user_id=99, report_status='draft')

    monkeypatch.setattr(
        'app.services.mobile_report_service.assert_mobile_user_access',
        lambda *_args, **_kwargs: SimpleNamespace(is_admin=False),
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service._infer_current_shift',
        lambda *_args, **_kwargs: ShiftContext(
            business_date=date(2026, 3, 28),
            shift=type('Shift', (), {'id': 1, 'code': 'A', 'name': '白班'})(),
            workshop=type('Workshop', (), {'id': 2, 'code': 'ZR2', 'name': '铸二车间'})(),
            team=None,
            machine=type(
                'Machine',
                (),
                {
                    'id': 20,
                    'code': 'ZR2-2',
                    'name': '2#机',
                    'shift_mode': 'three',
                    'assigned_shift_ids': [1, 2, 3],
                    'custom_fields': [],
                },
            )(),
        ),
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service.dingtalk_service.service.resolve_mobile_identity',
        lambda *_args, **_kwargs: {'entry_channel': 'qr_machine', 'dingtalk_ready': False, 'dingtalk_hint': None},
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service._find_mobile_report',
        lambda *_args, **_kwargs: existing_report,
    )
    monkeypatch.setattr('app.services.mobile_report_service._active_reminders_for_context', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        'app.services.attendance_confirm_service.get_shift_confirmation_snapshot',
        lambda *_args, **_kwargs: {
            'attendance_confirmation_id': None,
            'attendance_machine_id': None,
            'attendance_machine_name': None,
            'attendance_status': 'not_started',
            'attendance_exception_count': 0,
            'attendance_pending_count': 0,
        },
    )

    payload = get_current_shift(DummyDB(), current_user=current_user)

    assert payload['can_submit'] is True
    assert payload['report_status'] == 'coil_entry'
    assert payload['ownership_note'] is None


@pytest.mark.parametrize(
    'role',
    ['energy_stat', 'maintenance_lead', 'hydraulic_lead', 'consumable_stat', 'qc', 'weigher', 'inventory_keeper', 'utility_manager', 'contracts'],
)
def test_get_current_shift_allows_field_owner_when_shift_report_has_other_owner(monkeypatch, role: str) -> None:
    current_user = User(
        id=30,
        username=f'{role}-30',
        password_hash='x',
        name='字段负责人',
        role=role,
        workshop_id=2,
        is_mobile_user=True,
        is_active=True,
    )
    existing_report = SimpleNamespace(id=88, owner_user_id=99, leader_user_id=99, report_status='draft')

    monkeypatch.setattr(
        'app.services.mobile_report_service.assert_mobile_user_access',
        lambda *_args, **_kwargs: SimpleNamespace(is_admin=False),
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service._infer_current_shift',
        lambda *_args, **_kwargs: ShiftContext(
            business_date=date(2026, 3, 28),
            shift=type('Shift', (), {'id': 1, 'code': 'A', 'name': '白班'})(),
            workshop=type('Workshop', (), {'id': 2, 'code': 'ZR2', 'name': '铸二车间'})(),
            team=None,
            machine=None,
        ),
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service.dingtalk_service.service.resolve_mobile_identity',
        lambda *_args, **_kwargs: {'entry_channel': 'web_debug', 'dingtalk_ready': False, 'dingtalk_hint': None},
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service._find_mobile_report',
        lambda *_args, **_kwargs: existing_report,
    )
    monkeypatch.setattr('app.services.mobile_report_service._active_reminders_for_context', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        'app.services.attendance_confirm_service.get_shift_confirmation_snapshot',
        lambda *_args, **_kwargs: {
            'attendance_confirmation_id': None,
            'attendance_machine_id': None,
            'attendance_machine_name': None,
            'attendance_status': 'not_started',
            'attendance_exception_count': 0,
            'attendance_pending_count': 0,
        },
    )

    payload = get_current_shift(DummyDB(), current_user=current_user)

    assert payload['can_submit'] is True
    assert payload['report_status'] == 'unreported'
    assert payload['ownership_note'] is None


def test_entry_fields_returns_tracking_card_for_machine_operator() -> None:
    class EntryFieldsDB:
        def get(self, *_args, **_kwargs):
            return SimpleNamespace(id=2, code='ZR2', name='铸二车间', workshop_type='casting')

    current_user = User(
        id=21,
        username='machine-21',
        password_hash='x',
        name='铸二车间 1#机',
        role='machine_operator',
        workshop_id=2,
        is_mobile_user=True,
        is_active=True,
    )

    payload = entry_fields(db=EntryFieldsDB(), current_user=current_user)

    assert payload['mode'] == 'per_coil'
    assert payload['submit_target'] == 'coil_entry'
    assert payload['identity_field'] == 'tracking_card_no'
    first_fields = payload['groups'][0]['fields']
    assert first_fields[0]['name'] == 'tracking_card_no'
    assert first_fields[0]['label'] == '随行卡号'
    assert first_fields[0]['required'] is True
    assert all(field['name'] != 'batch_no' or field['label'] == '批号' for field in first_fields)


def test_entry_fields_uses_workshop_template_override_for_machine_operator(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'mobile-entry-fields.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, WorkshopTemplateConfig.__table__])
    session_factory = sessionmaker(bind=engine, future=True)

    with session_factory() as db:
        db.add(Workshop(id=2, code='ZR2', name='铸二车间', workshop_type='casting', sort_order=1, is_active=True))
        db.add(
            WorkshopTemplateConfig(
                template_key='ZR2',
                display_name='铸二模板',
                tempo='slow',
                supports_ocr=False,
                entry_fields=[
                    {'name': 'alloy_grade', 'label': '合金牌号', 'type': 'text', 'required': True, 'enabled': True},
                    {'name': 'input_weight', 'label': '测试投入', 'type': 'number', 'unit': 'kg', 'required': True, 'enabled': True},
                    {'name': 'output_weight', 'label': '测试产出', 'type': 'number', 'unit': 'kg', 'required': True, 'enabled': True},
                ],
                extra_fields=[],
                qc_fields=[],
                readonly_fields=[],
                is_active=True,
            )
        )
        db.commit()

        current_user = User(
            id=21,
            username='machine-21',
            password_hash='x',
            name='铸二车间 1#机',
            role='machine_operator',
            workshop_id=2,
            is_mobile_user=True,
            is_active=True,
        )
        payload = entry_fields(db=db, current_user=current_user)

    first_fields = payload['groups'][0]['fields']
    assert [field['name'] for field in first_fields] == [
        'tracking_card_no',
        'alloy_grade',
        'input_weight',
        'output_weight',
    ]
    assert first_fields[2]['label'] == '测试投入'


def test_get_current_shift_shows_config_hint_when_no_shift(monkeypatch) -> None:
    current_user = User(
        id=19,
        username='leader-no-shift',
        password_hash='x',
        name='班长A',
        role='team_leader',
        workshop_id=2,
        is_mobile_user=True,
        is_active=True,
    )

    monkeypatch.setattr(
        'app.services.mobile_report_service.assert_mobile_user_access',
        lambda *_args, **_kwargs: SimpleNamespace(is_admin=False),
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service._infer_current_shift',
        lambda *_args, **_kwargs: ShiftContext(
            business_date=date(2026, 3, 28),
            shift=None,
            workshop=type('Workshop', (), {'id': 2, 'code': 'ZR2', 'name': '铸二车间'})(),
            team=None,
            machine=None,
        ),
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service.dingtalk_service.service.resolve_mobile_identity',
        lambda *_args, **_kwargs: {'entry_channel': 'web_debug', 'dingtalk_ready': False, 'dingtalk_hint': None},
    )
    monkeypatch.setattr('app.services.mobile_report_service._active_reminders_for_context', lambda *_args, **_kwargs: [])

    payload = get_current_shift(DummyDB(), current_user=current_user)

    assert payload['can_submit'] is False
    assert '未配置可用班次' in (payload['ownership_note'] or '')
