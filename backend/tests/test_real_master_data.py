from datetime import time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Equipment, MasterCodeAlias, Team, Workshop
from app.models.shift import ShiftConfig
from app.models.system import User
from tests.path_helpers import REPO_ROOT


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'real-master-data.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            User.__table__,
            Equipment.__table__,
            MasterCodeAlias.__table__,
            ShiftConfig.__table__,
        ],
    )
    db = sessionmaker(bind=engine, future=True)()
    db.add_all(
        [
            ShiftConfig(
                code='A',
                name='长白班',
                shift_type='day',
                start_time=time(8, 0),
                end_time=time(16, 0),
                is_cross_day=False,
                sort_order=1,
                is_active=True,
            ),
            ShiftConfig(
                code='B',
                name='小夜班',
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
                name='大夜班',
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
            'ZR5',
            'ZR6',
            'RZ',
            'LZ2050',
            'LZ1850',
            'LZ1650',
            'LZ1450',
            'LZ3',
            'HWB',
            'JZ',
            'JZ2',
            'JQ',
            'LJ',
            'CT',
            'HS',
            'CPK',
            'ZXTF-N',
            'ZXTF-P',
            'ZXTF',
            'CH',
        ]
        assert [item.name for item in workshops] == [
            '铸锭分厂',
            '铸轧二',
            '铸轧三',
            '铸轧五',
            '铸轧六',
            '热轧',
            '2050冷轧',
            '1850冷轧',
            '1650冷轧',
            '老厂',
            '冷轧三车间',
            '花纹板车间',
            '精整车间',
            '二分厂精整车间',
            '剪切车间',
            '拉矫车间',
            '彩涂',
            '回收车间',
            '成品库',
            '新厂在线退火',
            '园区在线退火',
            '在线退火分厂',
            '淬火车间',
        ]
        assert [item.workshop_type for item in workshops] == [
            'casting',
            'casting',
            'casting',
            'casting',
            'casting',
            'hot_roll',
            'cold_roll',
            'cold_roll',
            'cold_roll',
            'cold_roll',
            'cold_roll',
            'cold_roll',
            'finishing',
            'finishing',
            'shearing',
            'straightening',
            'coating',
            'recycling',
            'inventory',
            'annealing',
            'annealing',
            'annealing',
            'finishing',
        ]
        assert len(teams) == 69
        assert [(item.code, item.name) for item in teams if item.code.startswith('ZR2-')] == [
            ('ZR2-A', '长白班组'),
            ('ZR2-B', '小夜班组'),
            ('ZR2-C', '大夜班组'),
        ]

        zr2_equipment = [item for item in equipment if item.code.startswith('ZR2-') and item.equipment_type != 'virtual_role_qr']
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

        zr3_equipment = [item for item in equipment if item.code.startswith('ZR3-') and item.equipment_type != 'virtual_role_qr']
        assert [(item.code, item.name, item.equipment_type) for item in zr3_equipment] == [
            ('ZR3-1', '1#机', 'cast_roller'),
            ('ZR3-2', '2#机', 'cast_roller'),
            ('ZR3-3', '3#机', 'cast_roller'),
            ('ZR3-4', '4#机', 'cast_roller'),
            ('ZR3-5', '5#机', 'cast_roller'),
            ('ZR3-6', '6#机', 'cast_roller'),
            ('ZR3-7', '7#机', 'cast_roller'),
            ('ZR3-8', '8#机', 'cast_roller'),
            ('ZR3-9', '9#机', 'cast_roller'),
        ]
        assert all(item.operational_status == 'running' for item in zr3_equipment)

        milling = next(item for item in equipment if item.code == 'RZ-FM')
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

        assert running_machine.qr_code == 'XT-ZR2-1'
        # Auto-seed of per-equipment accounts retired — bound_user_id stays None for fresh seed
        assert running_machine.bound_user_id is None

        assert stopped_machine.qr_code == 'XT-ZR2-3'
        assert stopped_machine.bound_user_id is None

        # New owner role QRs — factory-wide unique (G14)
        qm = db.execute(select(User).where(User.username == 'CPK-QM')).scalar_one()
        pl = db.execute(select(User).where(User.username == 'CPK-PL')).scalar_one()
        ec = db.execute(select(User).where(User.username == 'CPK-EC')).scalar_one()
        fs = db.execute(select(User).where(User.username == 'CPK-FS')).scalar_one()

        assert qm.role == 'quality_owner'
        assert qm.is_mobile_user is True
        assert pl.role == 'planning_owner'
        assert ec.role == 'energy_chief'
        assert fs.role == 'storage_owner'

        zxtf_new = next(item for item in workshops if item.code == 'ZXTF-N')
        zxtf_park = next(item for item in workshops if item.code == 'ZXTF-P')
        legacy_online_en = db.execute(select(User).where(User.username == 'ZXTF-EN')).scalar_one()
        legacy_online_cs = db.execute(select(User).where(User.username == 'ZXTF-CS')).scalar_one()
        park_online_en = db.execute(select(User).where(User.username == 'ZXTF-P-EN')).scalar_one()
        park_online_cs = db.execute(select(User).where(User.username == 'ZXTF-P-CS')).scalar_one()
        assert legacy_online_en.role == 'energy_stat'
        assert legacy_online_en.workshop_id == zxtf_new.id
        assert legacy_online_cs.role == 'consumable_stat'
        assert legacy_online_cs.workshop_id == zxtf_new.id
        assert park_online_en.role == 'energy_stat'
        assert park_online_en.workshop_id == zxtf_park.id
        assert park_online_cs.role == 'consumable_stat'
        assert park_online_cs.workshop_id == zxtf_park.id
        assert db.execute(select(Equipment).where(Equipment.code == 'ZXTF-N-EN')).scalar_one_or_none() is None

        zxtf_equipment = [item for item in equipment if item.code.startswith('ZXTF-') and item.equipment_type != 'virtual_role_qr']
        assert [(item.code, item.name, item.equipment_type, item.qr_code) for item in zxtf_equipment] == [
            ('ZXTF-1', '新厂北', 'annealing_line', 'XT-ZXTF-1'),
            ('ZXTF-2', '新厂南', 'annealing_line', 'XT-ZXTF-2'),
            ('ZXTF-3', '园区北', 'annealing_line', 'XT-ZXTF-3'),
            ('ZXTF-4', '园区南', 'annealing_line', 'XT-ZXTF-4'),
        ]
        workshops_by_id = {item.id: item for item in workshops}
        assert [(item.code, workshops_by_id[item.workshop_id].code) for item in zxtf_equipment] == [
            ('ZXTF-1', 'ZXTF-N'),
            ('ZXTF-2', 'ZXTF-N'),
            ('ZXTF-3', 'ZXTF-P'),
            ('ZXTF-4', 'ZXTF-P'),
        ]
    finally:
        db.close()


def test_seed_real_master_data_preserves_existing_qr_codes_and_seeds_mes_aliases(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        workshop = Workshop(code='LZ2050', name='旧2050', workshop_type='cold_roll', sort_order=99, is_active=True)
        db.add(workshop)
        db.commit()
        db.refresh(workshop)
        db.add(
            Equipment(
                code='LZ2050-1',
                name='旧2050轧机',
                workshop_id=workshop.id,
                equipment_type='cold_mill',
                operational_status='running',
                qr_code='PRINTED-LZ2050-1',
                is_active=True,
            )
        )
        db.commit()

        seed_real_master_data(db)
        seed_real_master_data(db)

        machine = db.execute(select(Equipment).where(Equipment.code == 'LZ2050-1')).scalar_one()
        assert machine.qr_code == 'PRINTED-LZ2050-1'
        # Auto-seed retired — no pre-existing user so bound_user_id stays None
        assert machine.bound_user_id is None

        aliases = {
            (item.entity_type, item.canonical_code, item.alias_code, item.alias_name, item.source_type)
            for item in db.execute(select(MasterCodeAlias).where(MasterCodeAlias.is_active.is_(True))).scalars().all()
        }
        assert ('workshop', 'LZ2050', '2050车间', '2050车间', 'mes_mvc') in aliases
        assert ('workshop', 'LZ1450', '1450车间', '1450车间', 'mes_mvc') in aliases
        assert ('workshop', 'RZ', '热轧', '热轧', 'mes_mvc') in aliases
        assert ('workshop', 'LJ', '拉矫车间', '拉矫车间', 'mes_mvc') in aliases
        assert ('workshop', 'JQ', '园区精整', '园区精整', 'mes_mvc') in aliases
        assert ('workshop', 'ZXTF-N', '新厂在线车间', '新厂在线车间', 'mes_mvc') in aliases
        assert ('workshop', 'ZXTF-P', '园区在线车间', '园区在线车间', 'mes_mvc') in aliases

        zxtf_new = db.execute(select(Workshop).where(Workshop.code == 'ZXTF-N')).scalar_one()
        zxtf_park = db.execute(select(Workshop).where(Workshop.code == 'ZXTF-P')).scalar_one()
        legacy_zxtf = db.execute(select(Workshop).where(Workshop.code == 'ZXTF')).scalar_one()
        zxtf_lines = db.execute(
            select(Equipment).where(Equipment.workshop_id.in_([zxtf_new.id, zxtf_park.id])).order_by(Equipment.code.asc())
        ).scalars().all()
        assert zxtf_new.name == '新厂在线退火'
        assert zxtf_park.name == '园区在线退火'
        assert legacy_zxtf.is_active is False
        assert [(item.code, item.qr_code, item.operational_status) for item in zxtf_lines if item.equipment_type != 'virtual_role_qr'] == [
            ('ZXTF-1', 'XT-ZXTF-1', 'running'),
            ('ZXTF-2', 'XT-ZXTF-2', 'running'),
            ('ZXTF-3', 'XT-ZXTF-3', 'running'),
            ('ZXTF-4', 'XT-ZXTF-4', 'running'),
        ]
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

        assert refreshed_workshop.name == '铸轧二'
        assert refreshed_workshop.sort_order == 2
        assert refreshed_workshop.workshop_type == 'casting'
        assert refreshed_workshop.is_active is True
        assert refreshed_equipment.name == '1#机'
        assert refreshed_equipment.equipment_type == 'cast_roller'
        assert refreshed_equipment.operational_status == 'running'
        assert refreshed_equipment.shift_mode == 'three'
        assert refreshed_equipment.is_active is True
        assert refreshed_team.name == '长白班组'
        assert refreshed_team.sort_order == 1
        assert refreshed_team.is_active is True
        assert legacy_workshop.is_active is False
        assert placeholder_workshop.is_active is False
        assert placeholder_equipment.is_active is False
        assert placeholder_team.is_active is False

        assert len(db.execute(select(Workshop)).scalars().all()) == 25
        assert len(db.execute(select(Team).where(Team.code == 'ZR2-A')).scalars().all()) == 1
        assert len(db.execute(select(Equipment).where(Equipment.code == 'ZR2-1')).scalars().all()) == 1
    finally:
        db.close()


def test_seed_real_master_data_keeps_existing_machine_account_binding_and_pin(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        from app.core.auth import get_password_hash
        # Pre-create a user account so the seed function binds it
        pre_user = User(
            username='ZR2-1',
            password_hash=get_password_hash('123456'),
            name='铸轧二 1#机',
            role='shift_leader',
            is_mobile_user=True,
            is_active=True,
            pin_code='123456',
        )
        db.add(pre_user)
        db.commit()
        db.refresh(pre_user)
        original_user_id = pre_user.id

        seed_real_master_data(db)

        first_machine = db.execute(select(Equipment).where(Equipment.code == 'ZR2-1')).scalar_one()
        first_user = db.get(User, first_machine.bound_user_id)
        assert first_user is not None
        assert first_user.id == original_user_id
        original_pin = first_user.pin_code

        seed_real_master_data(db)

        refreshed_machine = db.execute(select(Equipment).where(Equipment.code == 'ZR2-1')).scalar_one()
        refreshed_user = db.get(User, refreshed_machine.bound_user_id)
        assert refreshed_user is not None
        assert refreshed_user.id == original_user_id
        assert refreshed_user.pin_code == original_pin
    finally:
        db.close()


def test_seed_real_master_data_reactivates_role_qr_and_binds_role_accounts(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        workshop = Workshop(code='ZR2', name='旧铸二', sort_order=99, is_active=True)
        db.add(workshop)
        db.commit()
        db.refresh(workshop)
        db.add_all(
            [
                Equipment(
                    code='ZR2-1-OP',
                    name='铸二车间 1# 主操',
                    workshop_id=workshop.id,
                    equipment_type='virtual_role_qr',
                    operational_status='running',
                    qr_code='XT-ZR2-1-OP',
                    is_active=False,
                ),
                Equipment(
                    code='ZR2-EN',
                    name='铸二车间 电工',
                    workshop_id=workshop.id,
                    equipment_type='virtual_role_qr',
                    operational_status='running',
                    qr_code='XT-ZR2-EN',
                    is_active=False,
                ),
            ]
        )
        db.commit()

        seed_real_master_data(db)

        operator_qr = db.execute(select(Equipment).where(Equipment.qr_code == 'XT-ZR2-1-OP')).scalar_one()
        electrician_qr = db.execute(select(Equipment).where(Equipment.qr_code == 'XT-ZR2-EN')).scalar_one()
        operator_user = db.execute(select(User).where(User.username == 'ZR2-1-OP')).scalar_one()
        electrician_user = db.execute(select(User).where(User.username == 'ZR2-EN')).scalar_one()

        assert operator_qr.is_active is True
        assert electrician_qr.is_active is True
        assert operator_qr.bound_user_id == operator_user.id
        assert electrician_qr.bound_user_id == electrician_user.id

        assert operator_user.role == 'machine_operator'
        assert electrician_user.role == 'energy_stat'
        assert operator_user.workshop_id == operator_qr.workshop_id
        assert electrician_user.workshop_id == electrician_qr.workshop_id
        assert operator_user.is_mobile_user is True
        assert electrician_user.is_mobile_user is True
        assert operator_user.is_active is True
        assert electrician_user.is_active is True
    finally:
        db.close()


def test_seed_real_master_data_rehomes_legacy_zxtf_role_qr_after_online_split(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        workshop = Workshop(code='ZXTF', name='在线退火车间', workshop_type='annealing', sort_order=200, is_active=False)
        db.add(workshop)
        db.commit()
        db.refresh(workshop)
        db.add(
            Equipment(
                code='ZXTF-1-OP',
                name='在线退火车间 1# 主操',
                workshop_id=workshop.id,
                equipment_type='virtual_role_qr',
                operational_status='running',
                qr_code='XT-ZXTF-1-OP',
                is_active=False,
            )
        )
        db.commit()

        seed_real_master_data(db)

        refreshed_workshop = db.execute(select(Workshop).where(Workshop.code == 'ZXTF')).scalar_one()
        new_workshop = db.execute(select(Workshop).where(Workshop.code == 'ZXTF-N')).scalar_one()
        operator_qr = db.execute(select(Equipment).where(Equipment.qr_code == 'XT-ZXTF-1-OP')).scalar_one()
        operator_user = db.execute(select(User).where(User.username == 'ZXTF-1-OP')).scalar_one()

        assert refreshed_workshop.is_active is False
        assert new_workshop.is_active is True
        assert operator_qr.is_active is True
        assert operator_qr.workshop_id == new_workshop.id
        assert operator_qr.bound_user_id == operator_user.id
        assert operator_user.role == 'machine_operator'
        assert operator_user.workshop_id == new_workshop.id
        assert operator_user.is_mobile_user is True
    finally:
        db.close()


def test_seed_real_master_data_does_not_resurrect_retired_role_qr(tmp_path) -> None:
    from app.core.auth import get_password_hash
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        retired = Workshop(code='LZ3', name='旧冷轧三', sort_order=88, is_active=False)
        db.add(retired)
        db.commit()
        db.refresh(retired)
        db.add_all([
            Equipment(
                code='LZ3-CS',
                name='冷轧三内勤',
                workshop_id=retired.id,
                equipment_type='virtual_role_qr',
                operational_status='running',
                qr_code='XT-LZ3-CS',
                is_active=True,
            ),
            User(
                username='LZ3-CS',
                password_hash=get_password_hash('123456'),
                name='冷轧三内勤',
                role='utility_manager',
                workshop_id=retired.id,
                is_mobile_user=True,
                is_active=True,
            ),
        ])
        db.commit()

        seed_real_master_data(db)

        refreshed_workshop = db.execute(select(Workshop).where(Workshop.code == 'LZ3')).scalar_one()
        role_qr = db.execute(select(Equipment).where(Equipment.code == 'LZ3-CS')).scalar_one()
        role_user = db.execute(select(User).where(User.username == 'LZ3-CS')).scalar_one()

        assert refreshed_workshop.is_active is False
        assert role_qr.is_active is False
        assert role_qr.operational_status == 'stopped'
        assert role_user.is_active is False
    finally:
        db.close()


def test_seed_real_master_data_includes_1650_1850_and_keeps_retired_hwb_inactive(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        seed_real_master_data(db)

        all_workshops = {item.code: item for item in db.execute(select(Workshop)).scalars().all()}
        active_workshops = {code: item for code, item in all_workshops.items() if item.is_active}
        for code in ('LZ1650', 'LZ1850'):
            assert code in active_workshops, f'workshop {code} missing after seed'
        for code in ('LZ1450', 'LZ3', 'HWB', 'JZ2', 'CT'):
            assert code in all_workshops, f'workshop {code} missing after seed'
            assert all_workshops[code].is_active is False, f'workshop {code} should stay retired'

        active_equipment = {item.code: item for item in db.execute(select(Equipment)).scalars().all() if item.is_active}
        for code in ('LZ1650-1', 'LZ1850-1'):
            assert code in active_equipment, f'equipment {code} missing after seed'

        inactive_equipment = {item.code: item for item in db.execute(select(Equipment)).scalars().all() if not item.is_active}
        for code in ('HWB-1', 'CT-TQ', 'JZ2-1'):
            assert code in inactive_equipment, f'equipment {code} should stay retired'
    finally:
        db.close()


def test_seed_real_master_data_includes_zr3_operator_reporting_machines(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        seed_real_master_data(db)

        equipment = {item.code: item for item in db.execute(select(Equipment)).scalars().all() if item.is_active}
        expected_codes = {f'ZR3-{index}' for index in range(1, 10)}
        missing = expected_codes - set(equipment)
        assert not missing, f'missing ZR3 reporting machines: {missing}'
        assert equipment['ZR3-2'].name == '2#机'
        assert equipment['ZR3-2'].equipment_type == 'cast_roller'
        assert equipment['ZR3-3'].operational_status == 'running'
    finally:
        db.close()


def test_seed_real_master_data_creates_active_workshop_directors(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        seed_real_master_data(db)

        active_workshop = db.execute(select(Workshop).where(Workshop.code == 'ZXTF-P')).scalar_one()
        retired_workshop = db.execute(select(Workshop).where(Workshop.code == 'LZ3')).scalar_one()
        director = db.execute(select(User).where(User.username == 'ZXTF-P-DIR')).scalar_one()
        retired_director = db.execute(select(User).where(User.username == 'LZ3-DIR')).scalar_one_or_none()

        assert director.role == 'workshop_director'
        assert director.workshop_id == active_workshop.id
        assert director.data_scope_type == 'self_workshop'
        assert director.is_reviewer is True
        assert director.is_manager is True
        assert director.is_mobile_user is False
        assert director.is_active is True
        assert retired_workshop.is_active is False
        assert retired_director is None
    finally:
        db.close()


def test_seed_real_master_data_preserves_existing_director_password(tmp_path) -> None:
    from app.core.auth import get_password_hash
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        workshop = Workshop(code='ZXTF-P', name='旧园区在线', sort_order=10, is_active=True)
        db.add(workshop)
        db.flush()
        password_hash = get_password_hash('Keep#2026')
        db.add(
            User(
                username='ZXTF-P-DIR',
                password_hash=password_hash,
                name='旧主任',
                role='manager',
                workshop_id=workshop.id,
                is_active=True,
            )
        )
        db.commit()

        seed_real_master_data(db)

        director = db.execute(select(User).where(User.username == 'ZXTF-P-DIR')).scalar_one()
        assert director.password_hash == password_hash
        assert director.role == 'workshop_director'
        assert director.data_scope_type == 'self_workshop'
    finally:
        db.close()


def test_seed_real_master_data_aliases_1650_1850_hwb(tmp_path) -> None:
    from app.services.real_master_data import seed_real_master_data

    db = build_session(tmp_path)
    try:
        seed_real_master_data(db)

        aliases = {
            (item.alias_code, item.canonical_code)
            for item in db.execute(select(MasterCodeAlias)).scalars().all()
            if item.is_active
        }
        expected = {
            ('1650车间', 'LZ1650'),
            ('冷轧1650车间', 'LZ1650'),
            ('1850车间', 'LZ1850'),
            ('冷轧1850车间', 'LZ1850'),
            ('花纹板', 'HWB'),
            ('花纹板车间', 'HWB'),
        }
        missing = expected - aliases
        assert not missing, f'missing aliases: {missing}'
    finally:
        db.close()


def test_process_business_hierarchy_covers_factory_workshop_machine_roles() -> None:
    from app.services.real_master_data import build_process_business_hierarchy

    payload = build_process_business_hierarchy()
    units = {item['unit_code']: item for item in payload['units']}

    assert set(units) == {
        'casting_branch',
        'rolling_branch',
        'finishing_branch',
        'lazheng_branch',
        'shearing_branch',
        'quenching_branch',
        'coating_branch',
        'warehouse_logistics',
        'online_annealing',
    }

    casting_workshops = {item['workshop_code']: item for item in units['casting_branch']['workshops']}
    assert casting_workshops['ZD']['process_business'] == '铸锭/熔炼前段'
    assert casting_workshops['ZR2']['machines'][0]['process_business'] == '铸轧'

    rolling_workshops = {item['workshop_code']: item for item in units['rolling_branch']['workshops']}
    assert [item['process_business'] for item in rolling_workshops['RZ']['machines']] == [
        '热轧轧制',
        '六面铣',
        '双面铣',
        '中厚板',
        '加热炉',
        '锯切',
    ]
    assert rolling_workshops['LZ2050']['mes_aliases'] == ['2050车间', '冷轧2050车间', '2050冷轧']

    finishing_workshops = {item['workshop_code']: item for item in units['finishing_branch']['workshops']}
    assert {item['process_business'] for item in finishing_workshops['JZ']['machines']} >= {'19辊精整', '新19辊精整', '纵剪'}

    online_workshops = {item['workshop_code']: item for item in units['online_annealing']['workshops']}
    assert online_workshops['ZXTF-N']['area_status'] == 'confirmed'
    assert online_workshops['ZXTF-P']['area_status'] == 'confirmed'
    assert online_workshops['ZXTF-N']['mes_aliases'] == ['新厂在线车间', '新厂在线退火']
    assert online_workshops['ZXTF-P']['mes_aliases'] == ['园区在线车间', '园区在线退火']
    assert [item['machine_code'] for item in online_workshops['ZXTF-N']['machines']] == ['ZXTF-1', 'ZXTF-2']
    assert [item['machine_code'] for item in online_workshops['ZXTF-P']['machines']] == ['ZXTF-3', 'ZXTF-4']

    missing_machine_roles = [
        machine['machine_code']
        for unit in payload['units']
        for workshop in unit['workshops']
        for machine in workshop['machines']
        if not machine['process_business']
    ]
    assert missing_machine_roles == []


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
