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


def _seed_batch(db, *, batch_no: str = 'IMP-DAILY-1', extra_rows: list[dict] | None = None) -> ImportBatch:
    workshop_rows = [
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
    ]
    if extra_rows:
        workshop_rows.extend(extra_rows)

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
                'workshop_rows': workshop_rows,
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
        _equipment('RZ-XC', '铣床', rz),
        _equipment('LZ2050-1', '2050-1#', lz2050),
    ])
    batch = _seed_batch(db)

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
    assert rows[('铸轧', '铸二')].equipment_code == 'ZR2'
    assert rows[('热轧', '铣床')].equipment_code == 'RZ-XC'
    assert rows[('冷轧', '2050')].workshop_code == 'LZ2050'
    assert rows[('冷轧', '2050')].equipment_code == 'LZ2050-1'
    assert rows[('冷轧', '2050')].daily_output_tons == 120.46
    assert rows[('冷轧', '1650')].status == 'unresolved_workshop'
    assert rows[('冷轧', '1650')].workshop_id is None
    assert rows[('冷轧', '1650')].equipment_id is None


def test_daily_production_mapping_preview_marks_missing_equipment_mapping():
    db = _session()
    rz = _workshop('RZ', '热轧')
    db.add(rz)
    _seed_batch(db)

    preview = build_daily_production_mapping_preview(db)

    milling = next(row for row in preview.rows if row.workshop_label == '热轧' and row.project_label == '铣床')
    assert preview.batch_no == 'IMP-DAILY-1'
    assert milling.status == 'needs_equipment_mapping'
    assert milling.workshop_code == 'RZ'
    assert milling.expected_equipment_code == 'RZ-XC'
    assert milling.equipment_id is None


def test_daily_production_mapping_preview_suggests_active_candidates_for_unresolved_rows():
    db = _session()
    jz = _workshop('JZ', '精整车间')
    inactive_jz = _workshop('JZ-OLD', '旧精整车间')
    inactive_jz.is_active = False
    db.add_all([jz, inactive_jz])
    db.flush()
    db.add_all([
        _equipment('JZ-ZJ1', '纵剪1#', jz, equipment_type='slitter'),
        _equipment('JZ-ZJ-OLD', '旧纵剪', jz, equipment_type='slitter', is_active=False),
    ])
    batch = _seed_batch(
        db,
        extra_rows=[
            {
                'row_index': 8,
                'workshop_label': '精整',
                'project_label': '纵剪',
                'daily_input_tons': 70.0,
                'daily_output_tons': 68.0,
                'daily_scrap_tons': 2.0,
            }
        ],
    )

    preview = build_daily_production_mapping_preview(db, batch_id=batch.id)

    row = next(item for item in preview.rows if item.workshop_label == '精整' and item.project_label == '纵剪')
    assert row.status == 'unresolved_workshop'
    assert [item.code for item in row.candidate_workshops] == ['JZ']
    assert [item.code for item in row.candidate_equipment] == ['JZ-ZJ1']
