from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.imports import ImportBatch, ImportRow
from app.models.master import Equipment, Workshop
from app.models.system import User
from app.services.daily_production_mapping_service import build_daily_production_mapping_preview


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Workshop.__table__,
            Equipment.__table__,
            ImportBatch.__table__,
            ImportRow.__table__,
        ],
    )
    return sessionmaker(bind=engine, autoflush=False, future=True)()


def _workshop(code: str, name: str) -> Workshop:
    return Workshop(code=code, name=name, workshop_type='production', is_active=True)


def _equipment(
    code: str,
    name: str,
    workshop: Workshop,
    *,
    equipment_type: str | None = None,
    is_active: bool = True,
) -> Equipment:
    return Equipment(
        code=code,
        name=name,
        workshop_id=workshop.id,
        equipment_type=equipment_type,
        operational_status='running',
        is_active=is_active,
    )


def _seed_batch(db, *, batch_no: str = 'IMP-DAILY-1', workshop_rows: list[dict] | None = None) -> ImportBatch:
    batch = ImportBatch(
        batch_no=batch_no,
        import_type='daily_production_report',
        file_name='daily-production.xlsx',
        total_rows=1,
        success_rows=1,
        failed_rows=0,
        status='completed',
        quality_status='ready',
        parsed_successfully=True,
    )
    db.add(batch)
    db.flush()
    db.add(
        ImportRow(
            batch_id=batch.id,
            row_number=1,
            status='success',
            raw_data={'sheet_name': '综合报表'},
            mapped_data={
                'business_date': '2026-05-03',
                'source_unit': 't',
                'workshop_rows': workshop_rows
                or [
                    {
                        'row_index': 3,
                        'workshop_label': '铸锭',
                        'project_label': None,
                        'daily_input_tons': 314.19,
                        'daily_output_tons': 301.1,
                        'daily_scrap_tons': 13.09,
                    },
                    {
                        'row_index': 4,
                        'workshop_label': '铸轧',
                        'project_label': '铸二',
                        'daily_input_tons': 410.2,
                        'daily_output_tons': 398.5,
                        'daily_scrap_tons': 11.7,
                    },
                    {
                        'row_index': 5,
                        'workshop_label': '热轧',
                        'project_label': '铣床',
                        'daily_input_tons': 208.3,
                        'daily_output_tons': 205.0,
                        'daily_scrap_tons': 3.3,
                    },
                    {
                        'row_index': 6,
                        'workshop_label': '冷轧',
                        'project_label': '2050',
                        'daily_input_tons': 149.51,
                        'daily_output_tons': 120.46,
                        'daily_scrap_tons': 18.05,
                    },
                    {
                        'row_index': 7,
                        'workshop_label': '冷轧',
                        'project_label': '1650',
                        'daily_input_tons': 88.0,
                        'daily_output_tons': 79.0,
                        'daily_scrap_tons': 9.0,
                    },
                ],
            },
        )
    )
    db.commit()
    return batch


def test_daily_production_mapping_preview_resolves_only_high_confidence_rows():
    db = _session()
    zd = _workshop('ZD', '铸锭')
    zr2 = _workshop('ZR2', '铸轧二号')
    rz = _workshop('RZ', '热轧')
    lz2050 = _workshop('LZ2050', '冷轧2050')
    db.add_all([zd, zr2, rz, lz2050])
    db.flush()
    db.add_all([
        _equipment('ZR2', '铸二', zr2),
        _equipment('RZ-FM', '六面铣', rz),
        _equipment('LZ2050-1', '2050-1#', lz2050),
    ])
    batch = _seed_batch(
        db,
        workshop_rows=[
            {'row_index': 3, 'workshop_label': '铸锭', 'project_label': None, 'daily_output_tons': 301.1},
            {'row_index': 4, 'workshop_label': '铸轧', 'project_label': '铸二', 'daily_output_tons': 398.5},
            {'row_index': 5, 'workshop_label': '热轧', 'project_label': '六面铣', 'daily_output_tons': 205.0},
            {'row_index': 6, 'workshop_label': '冷轧', 'project_label': '2050', 'daily_output_tons': 120.46},
            {'row_index': 7, 'workshop_label': '冷轧', 'project_label': '1650', 'daily_output_tons': 79.0},
        ],
    )

    preview = build_daily_production_mapping_preview(db, batch_id=batch.id)

    assert preview.batch_id == batch.id
    assert preview.total_rows == 5
    assert preview.ready_rows == 4
    assert preview.needs_equipment_mapping_rows == 0
    assert preview.unresolved_rows == 1

    rows = {(row.workshop_label, row.project_label): row for row in preview.rows}
    assert rows[('铸锭', None)].status == 'ready'
    assert rows[('铸锭', None)].workshop_code == 'ZD'
    assert rows[('铸锭', None)].equipment_id is None
    assert rows[('铸轧', '铸二')].workshop_code == 'ZR2'
    assert rows[('铸轧', '铸二')].expected_equipment_code is None
    assert rows[('铸轧', '铸二')].equipment_id is None
    assert rows[('热轧', '六面铣')].equipment_code == 'RZ-FM'
    assert rows[('冷轧', '2050')].workshop_code == 'LZ2050'
    assert rows[('冷轧', '2050')].equipment_code == 'LZ2050-1'
    assert rows[('冷轧', '1650')].status == 'unresolved_workshop'
    assert rows[('冷轧', '1650')].workshop_id is None
    assert rows[('冷轧', '1650')].equipment_id is None


def test_daily_production_mapping_preview_resolves_stable_workshop_level_labels():
    db = _session()
    hot_roll = _workshop('RZ', '热轧车间')
    finishing = _workshop('JZ', '精整车间')
    shearing = _workshop('JQ', '剪切车间')
    db.add_all([hot_roll, finishing, shearing])
    db.flush()
    _seed_batch(
        db,
        workshop_rows=[
            {'row_index': 9, 'workshop_label': '热轧', 'project_label': '铣床', 'daily_output_tons': 281.22},
            {'row_index': 16, 'workshop_label': '精整', 'project_label': '剪子', 'daily_output_tons': 76.289},
            {'row_index': 33, 'workshop_label': '园区剪切', 'project_label': None, 'daily_output_tons': 53.37},
        ],
    )

    preview = build_daily_production_mapping_preview(db)

    assert preview.ready_rows == 3
    assert preview.unresolved_rows == 0
    rows = {(row.workshop_label, row.project_label): row for row in preview.rows}
    assert rows[('热轧', '铣床')].workshop_code == 'RZ'
    assert rows[('精整', '剪子')].workshop_code == 'JZ'
    assert rows[('园区剪切', None)].workshop_code == 'JQ'
    assert all(row.equipment_id is None for row in rows.values())


def test_daily_production_mapping_preview_marks_missing_equipment_mapping():
    db = _session()
    rz = _workshop('RZ', '热轧')
    db.add(rz)
    _seed_batch(
        db,
        workshop_rows=[
            {'row_index': 5, 'workshop_label': '热轧', 'project_label': '六面铣', 'daily_output_tons': 205.0},
        ],
    )

    preview = build_daily_production_mapping_preview(db)

    milling = next(row for row in preview.rows if row.workshop_label == '热轧' and row.project_label == '六面铣')
    assert preview.batch_no == 'IMP-DAILY-1'
    assert milling.status == 'needs_equipment_mapping'
    assert milling.workshop_code == 'RZ'
    assert milling.expected_equipment_code == 'RZ-FM'
    assert milling.equipment_id is None


def test_daily_production_mapping_preview_suggests_readonly_candidates_for_unresolved_rows():
    db = _session()
    finishing = _workshop('JZ', '精整车间')
    second_finishing = _workshop('JZ2', '二分厂精整车间')
    new_annealing = _workshop('ZXTF-N', '新厂在线退火')
    park_annealing = _workshop('ZXTF-P', '园区在线退火')
    db.add_all([finishing, second_finishing, new_annealing, park_annealing])
    db.flush()
    db.add_all([
        _equipment('JZ-ZJ1', '纵剪1#', finishing),
        _equipment('JZ2-LJ-OP', '精整二车间 拉矫 主操', second_finishing),
        _equipment('ZXTF-1-OP', '新厂在线退火 1# 主操', new_annealing),
    ])
    _seed_batch(
        db,
        workshop_rows=[
            {
                'row_index': 17,
                'workshop_label': '精整待确认',
                'project_label': '未知纵剪',
                'daily_output_tons': 75.96,
            },
            {
                'row_index': 25,
                'workshop_label': '在线退火待确认',
                'project_label': '未知北线',
                'daily_output_tons': 302.84,
            },
        ],
    )

    preview = build_daily_production_mapping_preview(db)

    rows = {(row.workshop_label, row.project_label): row for row in preview.rows}
    slitting = rows[('精整待确认', '未知纵剪')]
    assert slitting.status == 'unresolved_workshop'
    assert [item.code for item in slitting.candidate_workshops] == ['JZ', 'JZ2']
    assert [item.code for item in slitting.candidate_equipment] == ['JZ-ZJ1']

    north_line = rows[('在线退火待确认', '未知北线')]
    assert north_line.status == 'unresolved_workshop'
    assert [item.code for item in north_line.candidate_workshops] == ['ZXTF-N', 'ZXTF-P']
    assert north_line.candidate_equipment == []


def test_daily_production_mapping_preview_resolves_real_5_5_labels():
    db = _session()
    workshops = {
        code: _workshop(code, name)
        for code, name in [
            ('ZD', '铸锭车间'),
            ('ZR2', '铸二车间'),
            ('ZR3', '铸三车间'),
            ('RZ', '热轧车间'),
            ('LZ2050', '2050冷轧车间'),
            ('LZ1850', '1850冷轧车间'),
            ('LZ1650', '1650冷轧车间'),
            ('JZ', '精整车间'),
            ('LJ', '拉矫车间'),
            ('JQ', '园区剪切车间'),
            ('ZXTF-N', '新厂在线退火'),
            ('ZXTF-P', '园区在线退火'),
        ]
    }
    db.add_all(workshops.values())
    db.flush()
    db.add_all([
        _equipment('ZR2', '铸二', workshops['ZR2']),
        _equipment('ZR3', '铸三', workshops['ZR3']),
        _equipment('RZ-FM', '六面铣', workshops['RZ']),
        _equipment('RZ-DM', '双面铣', workshops['RZ']),
        _equipment('RZ-ZJ', '热轧机', workshops['RZ']),
        _equipment('LZ2050-1', '2050轧机', workshops['LZ2050']),
        _equipment('LZ1850-1', '1850轧机', workshops['LZ1850']),
        _equipment('LZ1650-1', '1650轧机', workshops['LZ1650']),
        _equipment('JZ-19G', '19辊精整', workshops['JZ']),
        _equipment('JZ-ZJ-Z', '纵剪', workshops['JZ']),
        _equipment('JQ-LJ', '拉矫', workshops['LJ']),
        _equipment('JQ-TH', '退火炉', workshops['LJ']),
        _equipment('LJ-DFC', '大分切', workshops['LJ']),
        _equipment('ZXTF-1', '新厂北', workshops['ZXTF-N']),
        _equipment('ZXTF-2', '新厂南', workshops['ZXTF-N']),
        _equipment('ZXTF-3', '园区北', workshops['ZXTF-P']),
    ])
    batch = _seed_batch(
        db,
        workshop_rows=[
            {'row_index': 3, 'workshop_label': '铸锭', 'project_label': None, 'daily_output_tons': 314.19},
            {'row_index': 4, 'workshop_label': '铸轧', 'project_label': '铸二', 'daily_output_tons': 24.18},
            {'row_index': 5, 'workshop_label': '铸轧', 'project_label': '铸三', 'daily_output_tons': 36.2},
            {'row_index': 9, 'workshop_label': '热轧', 'project_label': '六面铣', 'daily_output_tons': 278.13},
            {'row_index': 10, 'workshop_label': '热轧', 'project_label': '热轧', 'daily_output_tons': 0.0},
            {'row_index': 11, 'workshop_label': '冷轧', 'project_label': '1650', 'daily_output_tons': 224.54},
            {'row_index': 12, 'workshop_label': '冷轧', 'project_label': '1850', 'daily_output_tons': 31.08},
            {'row_index': 13, 'workshop_label': '冷轧', 'project_label': '2050', 'daily_output_tons': 85.13},
            {'row_index': 16, 'workshop_label': '精整', 'project_label': '19辊', 'daily_output_tons': 45.286},
            {'row_index': 17, 'workshop_label': '精整', 'project_label': '纵剪', 'daily_output_tons': 75.96},
            {'row_index': 18, 'workshop_label': '拉矫', 'project_label': '拉矫', 'daily_output_tons': 196.08},
            {'row_index': 19, 'workshop_label': '拉矫', 'project_label': '分切', 'daily_output_tons': 39.58},
            {'row_index': 21, 'workshop_label': '拉矫', 'project_label': '产量', 'daily_output_tons': 55.984},
            {'row_index': 23, 'workshop_label': '退火炉', 'project_label': '拉矫', 'daily_output_tons': 51.0},
            {'row_index': 24, 'workshop_label': '在线退火', 'project_label': '新厂南线', 'daily_output_tons': 0.0},
            {'row_index': 25, 'workshop_label': '在线退火', 'project_label': '新厂北线', 'daily_output_tons': 302.84},
            {'row_index': 27, 'workshop_label': '在线退火', 'project_label': '园区北线', 'daily_output_tons': 181.97},
        ],
    )

    preview = build_daily_production_mapping_preview(db, batch_id=batch.id)

    assert preview.total_rows == 17
    assert preview.ready_rows == 17
    assert preview.needs_equipment_mapping_rows == 0
    assert preview.unresolved_rows == 0
    rows = {(row.workshop_label, row.project_label): row for row in preview.rows}
    assert rows[('铸轧', '铸二')].workshop_code == 'ZR2'
    assert rows[('铸轧', '铸二')].expected_equipment_code is None
    assert rows[('铸轧', '铸三')].workshop_code == 'ZR3'
    assert rows[('铸轧', '铸三')].expected_equipment_code is None
    assert rows[('冷轧', '1650')].equipment_code == 'LZ1650-1'
    assert rows[('冷轧', '1850')].equipment_code == 'LZ1850-1'
    assert rows[('精整', '19辊')].equipment_code == 'JZ-19G'
    assert rows[('精整', '纵剪')].equipment_code == 'JZ-ZJ-Z'
    assert rows[('拉矫', '拉矫')].equipment_code == 'JQ-LJ'
    assert rows[('拉矫', '分切')].equipment_code == 'LJ-DFC'
    assert rows[('拉矫', '产量')].workshop_code == 'LJ'
    assert rows[('拉矫', '产量')].equipment_id is None
    assert rows[('退火炉', '拉矫')].workshop_code == 'LJ'
    assert rows[('在线退火', '新厂南线')].workshop_code == 'ZXTF-N'
    assert rows[('在线退火', '新厂南线')].equipment_code == 'ZXTF-2'
    assert rows[('在线退火', '新厂北线')].workshop_code == 'ZXTF-N'
    assert rows[('在线退火', '新厂北线')].equipment_code == 'ZXTF-1'
    assert rows[('在线退火', '园区北线')].workshop_code == 'ZXTF-P'
    assert rows[('在线退火', '园区北线')].equipment_code == 'ZXTF-3'
