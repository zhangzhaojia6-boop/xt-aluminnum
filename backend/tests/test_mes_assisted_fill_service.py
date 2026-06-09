from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord
from app.services import mes_assisted_fill_service


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-assisted-fill.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesCoilSnapshot.__table__, MesWorkshopProcessRecord.__table__])
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def test_assisted_fill_uses_latest_process_record_fields(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-AF-1',
                tracking_card_no='TRACK-AF-1',
                qr_code='QR-AF-1',
                batch_no='BATCH-AF-1',
                material_code='MAT-AF-1',
                alloy_grade='6061',
                material_state='H24',
                spec_display='1.2×1200',
                current_workshop='冷轧车间',
                current_process='冷轧',
            )
        )
        db.add_all(
            [
                MesWorkshopProcessRecord(
                    source_id='PROC-AF-OLD',
                    source_path='mvc',
                    batch_no='BATCH-AF-1',
                    workshop_name='冷轧车间',
                    process_name='冷轧',
                    device_name='1#轧机',
                    input_weight_kg=900,
                    output_weight_kg=860,
                    end_time=datetime(2026, 5, 3, 7, 20, tzinfo=timezone.utc),
                    source_payload={
                        'BeginSpecification': '1.1×1200',
                        'EndSpecification': '0.95×1200',
                        'BeginDatetime': '2026-05-03T06:40:00+00:00',
                        'EndDatetime': '2026-05-03T07:20:00+00:00',
                    },
                ),
                MesWorkshopProcessRecord(
                    source_id='PROC-AF-NEW',
                    source_path='mvc',
                    batch_no='BATCH-AF-1',
                    workshop_name='冷轧车间',
                    process_name='精轧',
                    device_name='2#轧机',
                    input_weight_kg=1000,
                    output_weight_kg=960,
                    end_time=datetime(2026, 5, 3, 8, 20, tzinfo=timezone.utc),
                    source_payload={
                        'BeginSpecification': '1.0×1200',
                        'EndSpecification': '0.8×1200',
                        'BeginDatetime': '2026-05-03T07:40:00+00:00',
                        'EndDatetime': '2026-05-03T08:20:00+00:00',
                    },
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        payload = mes_assisted_fill_service.build_assisted_fill(db, identifier='QR-AF-1')

    assert payload['source'] == 'mes_process_record'
    assert payload['fields'] == {
        'tracking_card_no': 'TRACK-AF-1',
        'alloy_grade': '6061',
        'input_spec': '1.0×1200',
        'output_spec': '0.8×1200',
        'input_weight': 1000.0,
        'output_weight': 960.0,
        'on_machine_time': '15:40',
        'off_machine_time': '16:20',
        'material_state': 'H24',
        'current_workshop': '冷轧车间',
        'current_process': '精轧',
        'machine_line_name': '2#轧机',
    }
    assert payload['lock_keys'] == []


def test_assisted_fill_falls_back_to_coil_snapshot_only(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-AF-SNAPSHOT',
                tracking_card_no='TRACK-SNAPSHOT',
                qr_code='QR-SNAPSHOT',
                batch_no='BATCH-SNAPSHOT',
                alloy_grade='5052',
                material_state='O',
                spec_display='2.0×1500',
            )
        )
        db.commit()

    with session_factory() as db:
        payload = mes_assisted_fill_service.build_assisted_fill(db, identifier='TRACK-SNAPSHOT')

    assert payload['source'] == 'mes_coil_snapshot'
    assert payload['fields'] == {
        'tracking_card_no': 'TRACK-SNAPSHOT',
        'alloy_grade': '5052',
        'input_spec': '2.0×1500',
        'material_state': 'O',
    }
    assert payload['lock_keys'] == []


def test_assisted_fill_returns_empty_when_identifier_missing(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        payload = mes_assisted_fill_service.build_assisted_fill(db, identifier='NO-SUCH-CARD')

    assert payload == {'source': 'none', 'fields': {}, 'lock_keys': []}


def test_assisted_fill_matches_material_code_and_batch_no(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-AF-MATCH',
                tracking_card_no='TRACK-MATCH',
                material_code='MAT-MATCH',
                batch_no='BATCH-MATCH',
                alloy_grade='3003',
                spec_display='1.5×1000',
            )
        )
        db.commit()

    with session_factory() as db:
        by_material = mes_assisted_fill_service.build_assisted_fill(db, identifier='MAT-MATCH')
        by_batch = mes_assisted_fill_service.build_assisted_fill(db, identifier='BATCH-MATCH')

    assert by_material['fields']['tracking_card_no'] == 'TRACK-MATCH'
    assert by_batch['fields']['tracking_card_no'] == 'TRACK-MATCH'


def test_assisted_fill_prefers_highest_id_when_end_time_missing(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-AF-ID',
                tracking_card_no='TRACK-ID',
                batch_no='BATCH-ID',
                alloy_grade='1060',
                spec_display='3.0×1000',
            )
        )
        db.add_all(
            [
                MesWorkshopProcessRecord(
                    source_id='PROC-ID-1',
                    source_path='mvc',
                    batch_no='BATCH-ID',
                    process_name='开坯',
                    input_weight_kg=700,
                    output_weight_kg=680,
                ),
                MesWorkshopProcessRecord(
                    source_id='PROC-ID-2',
                    source_path='mvc',
                    batch_no='BATCH-ID',
                    process_name='成品',
                    input_weight_kg=680,
                    output_weight_kg=650,
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        payload = mes_assisted_fill_service.build_assisted_fill(db, identifier='TRACK-ID')

    assert payload['fields']['current_process'] == '成品'
    assert payload['fields']['input_weight'] == 680.0
    assert payload['fields']['output_weight'] == 650.0
