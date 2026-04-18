from datetime import time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Equipment, Team, Workshop
from app.models.shift import ShiftConfig
from app.models.system import User
from tests.path_helpers import REPO_ROOT


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'real-master-data.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[Workshop.__table__, Team.__table__, User.__table__, Equipment.__table__, ShiftConfig.__table__],
    )
    db = sessionmaker(bind=engine, future=True)()
    db.add_all(
        [
            ShiftConfig(
                code='A',
                name='白班',
                shift_type='day',
                start_time=time(8, 0),
                end_time=time(16, 0),
                is_cross_day=False,
                sort_order=1,
                is_active=True,
            ),
            ShiftConfig(
                code='B',
                name='小夜',
                shift_type='swing',
                start_time=time(16, 0),
                end_time=time(0, 0),
                is_cross_day=True,
                business_day_offset=0,
                sort_order=2,
                is_active=True,
            ),
            ShiftConfig(
                code='C',
                name='大夜',
                shift_type='night',
                start_time=time(0, 0),
                end_time=time(8, 0),
                is_cross_day=False,
                business_day_offset=0,
                sort_order=3,
                is_active=True,
            ),
        ]
    )
    db.commit()
    return db


def test_seed_real_master_data_creates_revised_workshops_equipment_and_shift_teams(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        seed_real_master_data(db)

        workshops = db.execute(select(Workshop).order_by(Workshop.sort_order.asc())).scalars().all()
        teams = db.execute(select(Team).order_by(Team.code.asc())).scalars().all()
        equipment = db.execute(select(Equipment).order_by(Equipment.code.asc())).scalars().all()

        assert [item.code for item in workshops] == [
            'ZD',
            'ZR2',
            'ZR3',
            'RZ',
            'LZ2050',
            'LZ1450',
            'LZ3',
            'JZ',
            'JZ2',
            'JQ',
            'CPK',
        ]
        assert [item.name for item in workshops] == [
            '铸锭车间',
            '铸二车间',
            '铸三车间',
            '热轧车间',
            '2050冷轧车间',
            '1450冷轧车间',
            '冷轧三车间',
            '精整车间',
            '二分厂精整车间',
            '园区剪切车间',
            '成品库',
        ]
        assert [item.workshop_type for item in workshops] == [
            'casting',
            'casting',
            'casting',
            'hot_roll',
            'cold_roll',
            'cold_roll',
            'cold_roll',
            'finishing',
            'finishing',
            'shearing',
            'inventory',
        ]
        assert len(teams) == 33
        assert [(item.code, item.name) for item in teams if item.code.startswith('ZR2-')] == [
            ('ZR2-A', '白班组'),
            ('ZR2-B', '小夜班组'),
            ('ZR2-C', '大夜班组'),
        ]

        zr2_equipment = [item for item in equipment if item.code.startswith('ZR2-')]
        assert [(item.code, item.name, item.equipment_type) for item in zr2_equipment] == [
            ('ZR2-1', '1#机', 'cast_roller'),
            ('ZR2-2', '2#机', 'cast_roller'),
            ('ZR2-3', '3#机', 'cast_roller'),
            ('ZR2-4', '4#机', 'cast_roller'),
            ('ZR2-5', '5#机', 'cast_roller'),
            ('ZR2-6', '6#机', 'cast_roller'),
        ]
        assert all(item.shift_mode == 'three' for item in zr2_equipment)
        assert [item.operational_status for item in zr2_equipment] == [
            'running',
            'running',
            'stopped',
            'stopped',
            'running',
            'running',
        ]
        assert zr2_equipment[0].custom_fields and zr2_equipment[0].custom_fields[0]['name'] == 'al_liquid_kg'

        milling = next(item for item in equipment if item.code == 'RZ-XC')
        assert milling.shift_mode == 'two'
        assert milling.assigned_shift_ids == [1, 2]
        assert milling.operational_status == 'running'

        hot_mill = next(item for item in equipment if item.code == 'RZ-ZJ')
        assert hot_mill.custom_fields == [
            {'name': 'trim_weight', 'label': '切头重量', 'type': 'number', 'unit': 'kg'},
            {'name': 'oil_consumption', 'label': '润滑油', 'type': 'number', 'unit': 'L'},
        ]

        running_machine = next(item for item in equipment if item.code == 'ZR2-1')
        stopped_machine = next(item for item in equipment if item.code == 'ZR2-3')
        running_user = db.get(User, running_machine.bound_user_id)
        stopped_user = db.get(User, stopped_machine.bound_user_id)

        assert running_machine.qr_code == 'XT-ZR2-1'
        assert running_machine.bound_user_id is not None
        assert running_user is not None
        assert running_user.username == 'ZR2-1'
        assert running_user.name == '铸二车间 1#机'
        assert running_user.pin_code is not None
        assert len(running_user.pin_code) == 6
        assert running_user.pin_code.isdigit()
        assert running_user.is_active is True
        assert running_user.assigned_shift_ids == [1, 2, 3]

        assert stopped_machine.qr_code == 'XT-ZR2-3'
        assert stopped_machine.bound_user_id is not None
        assert stopped_user is not None
        assert stopped_user.username == 'ZR2-3'
        assert stopped_user.is_active is False

        energy_owner = db.execute(select(User).where(User.username == 'ZR2-A-EN')).scalar_one()
        qc_owner = db.execute(select(User).where(User.username == 'ZR2-B-QC')).scalar_one()
        inventory_owner = db.execute(select(User).where(User.username == 'CPK-A-INV')).scalar_one()
        utility_owner = db.execute(select(User).where(User.username == 'CPK-C-UTILITY')).scalar_one()

        assert energy_owner.role == 'energy_stat'
        assert energy_owner.workshop_id == next(item for item in workshops if item.code == 'ZR2').id
        assert energy_owner.assigned_shift_ids == [1]
        assert energy_owner.is_mobile_user is True

        assert qc_owner.role == 'qc'
        assert qc_owner.assigned_shift_ids == [2]
        assert qc_owner.is_active is True

        assert inventory_owner.role == 'inventory_keeper'
        assert inventory_owner.workshop_id == next(item for item in workshops if item.code == 'CPK').id
        assert inventory_owner.assigned_shift_ids == [1]

        assert utility_owner.role == 'utility_manager'
        assert utility_owner.assigned_shift_ids == [3]
        assert utility_owner.pin_code is not None
    finally:
        db.close()


def test_seed_real_master_data_updates_existing_records_idempotently_and_deactivates_placeholders(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        old_workshop = Workshop(code='ZR2', name='旧铸二', sort_order=99, is_active=False)
        legacy_workshop = Workshop(code='W1', name='示例车间', sort_order=0, is_active=True)
        placeholder_workshop = Workshop(code='TMP-WS', name='??????车间', sort_order=100, is_active=True)
        db.add_all([old_workshop, legacy_workshop, placeholder_workshop])
        db.commit()
        db.refresh(old_workshop)
        db.refresh(legacy_workshop)
        db.refresh(placeholder_workshop)

        old_equipment = Equipment(
            code='ZR2-1',
            name='旧设备',
            workshop_id=old_workshop.id,
            equipment_type='unknown',
            is_active=False,
        )
        placeholder_equipment = Equipment(
            code='TMP-EQ',
            name='??????设备',
            workshop_id=old_workshop.id,
            equipment_type='unknown',
            is_active=True,
        )
        old_team = Team(code='ZR2-A', name='旧班组', workshop_id=old_workshop.id, sort_order=99, is_active=False)
        placeholder_team = Team(
            code='TMP-TEAM',
            name='??????班组',
            workshop_id=old_workshop.id,
            sort_order=100,
            is_active=True,
        )
        db.add_all([old_equipment, placeholder_equipment, old_team, placeholder_team])
        db.commit()

        seed_real_master_data(db)
        seed_real_master_data(db)

        refreshed_workshop = db.execute(select(Workshop).where(Workshop.code == 'ZR2')).scalar_one()
        refreshed_equipment = db.execute(select(Equipment).where(Equipment.code == 'ZR2-1')).scalar_one()
        refreshed_team = db.execute(select(Team).where(Team.code == 'ZR2-A')).scalar_one()
        placeholder_workshop = db.execute(select(Workshop).where(Workshop.code == 'TMP-WS')).scalar_one()
        legacy_workshop = db.execute(select(Workshop).where(Workshop.code == 'W1')).scalar_one()
        placeholder_equipment = db.execute(select(Equipment).where(Equipment.code == 'TMP-EQ')).scalar_one()
        placeholder_team = db.execute(select(Team).where(Team.code == 'TMP-TEAM')).scalar_one()

        assert refreshed_workshop.name == '铸二车间'
        assert refreshed_workshop.sort_order == 2
        assert refreshed_workshop.workshop_type == 'casting'
        assert refreshed_workshop.is_active is True
        assert refreshed_equipment.name == '1#机'
        assert refreshed_equipment.equipment_type == 'cast_roller'
        assert refreshed_equipment.operational_status == 'running'
        assert refreshed_equipment.shift_mode == 'three'
        assert refreshed_equipment.is_active is True
        assert refreshed_team.name == '白班组'
        assert refreshed_team.sort_order == 1
        assert refreshed_team.is_active is True
        assert legacy_workshop.is_active is False
        assert placeholder_workshop.is_active is False
        assert placeholder_equipment.is_active is False
        assert placeholder_team.is_active is False

        assert len(db.execute(select(Workshop)).scalars().all()) == 13
        assert len(db.execute(select(Team).where(Team.code == 'ZR2-A')).scalars().all()) == 1
        assert len(db.execute(select(Equipment).where(Equipment.code == 'ZR2-1')).scalars().all()) == 1
    finally:
        db.close()


def test_seed_real_master_data_keeps_existing_machine_account_binding_and_pin(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        seed_real_master_data(db)

        first_machine = db.execute(select(Equipment).where(Equipment.code == 'ZR2-1')).scalar_one()
        first_user = db.get(User, first_machine.bound_user_id)
        assert first_user is not None
        original_user_id = first_user.id
        original_pin = first_user.pin_code

        seed_real_master_data(db)

        refreshed_machine = db.execute(select(Equipment).where(Equipment.code == 'ZR2-1')).scalar_one()
        refreshed_user = db.get(User, refreshed_machine.bound_user_id)
        assert refreshed_user is not None
        assert refreshed_user.id == original_user_id
        assert refreshed_user.pin_code == original_pin
    finally:
        db.close()


def test_docker_compose_runs_real_master_data_init_after_base_init() -> None:
    compose_text = (REPO_ROOT / 'docker-compose.yml').read_text(encoding='utf-8')
    prod_text = (REPO_ROOT / 'docker-compose.prod.yml').read_text(encoding='utf-8')

    assert 'python scripts/init_master_data.py &&' in compose_text
    assert 'python scripts/init_real_master_data.py &&' in compose_text
    assert compose_text.index('python scripts/init_master_data.py &&') < compose_text.index(
        'python scripts/init_real_master_data.py &&'
    )

    assert 'python scripts/init_master_data.py &&' in prod_text
    assert 'python scripts/init_real_master_data.py &&' in prod_text
    assert prod_text.index('python scripts/init_master_data.py &&') < prod_text.index(
        'python scripts/init_real_master_data.py &&'
    )
