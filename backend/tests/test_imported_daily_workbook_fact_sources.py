from __future__ import annotations

from datetime import date, time, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.business_time import production_business_window
from app.database import Base
from app.domain.daily_report_field_contract import DAILY_REPORT_FIELD_CONTRACT_VERSION
from app.models.energy import EnergyImportRecord
from app.models.imports import ImportBatch, ImportedDailyMetricFact, ImportRow
from app.models.master import Equipment, Team, Workshop
from app.models.production import ShiftProductionData
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.daily_energy_report_service import daily_energy_report_fact_field
from app.services.daily_production_canonical_service import build_daily_production_lineage_hash
from app.services.daily_production_mapping_service import build_daily_production_mapping_preview
from app.services.report import template_daily_fact_sources


REPORT_DATE = date(2026, 7, 17)


def test_daily_energy_field_map_preserves_first_furnace_explicit_zeroes() -> None:
    assert daily_energy_report_fact_field('gas', '热轧加热炉/1#东炉') == 'east_furnace_gas_m3'
    assert daily_energy_report_fact_field('gas', '热轧加热炉/1#西炉') == 'west_furnace_gas_m3'


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            User.__table__,
            Equipment.__table__,
            ShiftConfig.__table__,
            ImportBatch.__table__,
            ImportRow.__table__,
            ImportedDailyMetricFact.__table__,
            ShiftProductionData.__table__,
            EnergyImportRecord.__table__,
        ],
    )
    return sessionmaker(bind=engine, autoflush=False, future=True)()


def _workshop(code: str, name: str) -> Workshop:
    return Workshop(code=code, name=name, workshop_type='production', is_active=True)


def _equipment(code: str, name: str, workshop: Workshop) -> Equipment:
    return Equipment(
        code=code,
        name=name,
        workshop_id=workshop.id,
        equipment_type='production',
        operational_status='running',
        is_active=True,
    )


def _production_row(
    row_index: int,
    workshop_label: str,
    project_label: str | None,
    daily_output: float,
    monthly_output: float,
) -> dict:
    return {
        'row_index': row_index,
        'workshop_label': workshop_label,
        'project_label': project_label,
        'daily_output_tons': daily_output,
        'month_to_date_output_tons': monthly_output,
    }


def _production_mapped_data(
    rows: list[dict],
    *,
    business_date: date = REPORT_DATE,
    quality_status: str = 'ready',
    report_metrics: list[dict] | None = None,
) -> dict:
    payload = {
        'business_date': business_date.isoformat(),
        'source_unit': 't',
        'quality_status': quality_status,
        'workshop_rows': rows,
        'report_metrics': report_metrics or [],
    }
    return {**payload, 'lineage_hash': build_daily_production_lineage_hash(payload)}


def _confirmed_metric_fact(
    *,
    batch: ImportBatch,
    import_row: ImportRow,
    field_name: str,
    value: float,
    unit: str,
    business_date: date = REPORT_DATE,
) -> ImportedDailyMetricFact:
    metric = next(item for item in import_row.mapped_data['report_metrics'] if item['field_name'] == field_name)
    return ImportedDailyMetricFact(
        business_date=business_date,
        field_name=field_name,
        metric_value=value,
        unit=unit,
        source_kind='daily_production_report',
        import_batch_id=batch.id,
        import_row_id=import_row.id,
        source_anchors=metric['source_anchors'],
        lineage_hash=import_row.mapped_data['lineage_hash'],
        metric_contract_version=DAILY_REPORT_FIELD_CONTRACT_VERSION,
        data_status='confirmed',
        version_no=1,
    )


def _confirm_production_preview(db, batch: ImportBatch, shift: ShiftConfig) -> list[ShiftProductionData]:
    db.flush()
    preview = build_daily_production_mapping_preview(db, batch_id=batch.id)
    buckets: dict[tuple[date, int, int | None], list] = {}
    for row in preview.rows:
        if row.status != 'ready' or row.business_date is None or row.workshop_id is None:
            continue
        key = (date.fromisoformat(row.business_date), row.workshop_id, row.equipment_id)
        buckets.setdefault(key, []).append(row)

    confirmed = []
    for (business_date, workshop_id, equipment_id), rows in buckets.items():
        def metric(name: str):
            values = [getattr(row, name) for row in rows if getattr(row, name) is not None]
            return round(sum(float(value) for value in values), 3) if values else None

        output_weight = metric('daily_output_tons')
        confirmed.append(
            ShiftProductionData(
                business_date=business_date,
                shift_config_id=shift.id,
                workshop_id=workshop_id,
                equipment_id=equipment_id,
                input_weight=metric('daily_input_tons'),
                output_weight=output_weight,
                qualified_weight=output_weight,
                scrap_weight=metric('daily_scrap_tons'),
                data_source='daily_production_report',
                import_batch_id=batch.id,
                data_status='confirmed',
            )
        )
    db.add_all(confirmed)
    return confirmed


def test_promoted_daily_production_workbook_fills_only_report_semantic_rows() -> None:
    db = _session()
    try:
        workshops = {
            code: _workshop(code, name)
            for code, name in [
                ('ZD', '铸锭分厂'),
                ('ZR2', '铸轧二'),
                ('ZR3', '铸轧三'),
                ('RZ', '热轧车间'),
                ('LZ1650', '1650冷轧'),
                ('LZ1850', '1850冷轧'),
                ('LZ2050', '2050冷轧'),
                ('JZ', '精整车间'),
                ('JQ', '剪切车间'),
                ('LJ', '拉矫车间'),
                ('ZXTF-N', '新厂在线退火'),
                ('ZXTF-P', '园区在线退火'),
            ]
        }
        db.add_all(workshops.values())
        db.flush()
        db.add_all(
            [
                _equipment('RZ-ZJ', '热轧机', workshops['RZ']),
                _equipment('LZ1650-1', '1650#', workshops['LZ1650']),
                _equipment('LZ1850-1', '1850#', workshops['LZ1850']),
                _equipment('LZ2050-1', '2050#', workshops['LZ2050']),
                _equipment('JZ-ZJ-Z', '纵剪', workshops['JZ']),
                _equipment('JQ-LJ', '拉矫', workshops['LJ']),
                _equipment('ZXTF-1', '新厂北', workshops['ZXTF-N']),
                _equipment('ZXTF-3', '园区北', workshops['ZXTF-P']),
            ]
        )
        shift = ShiftConfig(
            code='A',
            name='白班',
            shift_type='day',
            start_time=time(8, 0),
            end_time=time(16, 0),
            is_active=True,
        )
        db.add(shift)
        db.flush()
        batch = ImportBatch(
            batch_no='IMP-DAILY-LOCKED-20260717',
            import_type='daily_production_report',
            source_type='daily_production_report_locked',
            file_name='daily-production.xls',
            total_rows=1,
            success_rows=1,
            failed_rows=0,
            status='completed',
            quality_status='ready',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        import_row = ImportRow(
            batch_id=batch.id,
            row_number=1,
            status='success',
            raw_data={'sheet_name': '综合报表'},
            mapped_data=_production_mapped_data(
                [
                        _production_row(3, '铸锭', None, 309.806, 4788.837),
                        _production_row(4, '铸轧', '铸二', 36.91, 704.49),
                        _production_row(5, '铸轧', '铸三', 43.61, 902.6),
                        _production_row(9, '热轧', '铣床', 281.22, 4387.07),
                        _production_row(10, '热轧', '热轧', 346.32, 4250.62),
                        _production_row(11, '冷轧', '1650', 90.43, 2486.133),
                        _production_row(12, '冷轧', '1850', 40.6, 834.22),
                        _production_row(13, '冷轧', '2050', 57.06, 2032.14),
                        _production_row(16, '精整', '剪子', 76.289, 1356.564),
                        _production_row(17, '精整', '纵剪', 91.4, 1477.0),
                        _production_row(18, '拉矫', '拉矫', 156.57, 2284.55),
                        _production_row(25, '在线退火', '新厂北线', 89.68, 3557.0),
                        _production_row(27, '在线退火', '园区北线', 112.32, 2111.05),
                        _production_row(33, '园区剪切', None, 53.37, 1174.955),
                ]
            ),
        )
        db.add(import_row)
        _confirm_production_preview(db, batch, shift)
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_imported_daily_production_facts(db, facts)

        assert facts.values['foundry_daily'] == 309.806
        assert facts.values['cast_2_daily'] == 36.91
        assert facts.values['cast_3_daily'] == 43.61
        assert facts.values['hot_roll_daily'] == 346.32
        assert facts.values['cold_1650_daily'] == 90.43
        assert facts.values['cold_1850_daily'] == 40.6
        assert facts.values['cold_2050_daily'] == 57.06
        assert facts.values['finishing_daily'] == 76.289
        assert facts.values['shearing_daily'] == 53.37
        assert facts.values['straightening_daily'] == 156.57
        assert facts.values['online_anneal_daily'] == 202.0
        assert all(
            field not in facts.values
            for field in ('hot_roll_month', 'finishing_month', 'shearing_month', 'online_anneal_month')
        )
        assert facts.sources['hot_roll_daily']['source_type'] == 'manual_workbook'
        assert facts.sources['hot_roll_daily']['import_batch_id'] == batch.id
        assert facts.sources['hot_roll_daily']['metric_contract_version'] == DAILY_REPORT_FIELD_CONTRACT_VERSION
        daily_start, daily_end = production_business_window(REPORT_DATE, workshop_name='热轧车间')
        assert facts.sources['hot_roll_daily']['business_window'] == f'{daily_start.isoformat()}/{daily_end.isoformat()}'
        assert facts.sources['hot_roll_daily']['row_anchors'] == [
            {
                'import_row_id': import_row.id,
                'import_row_number': 1,
                'workbook_row_index': 10,
            }
        ]
        assert ':hot_roll_daily:' in facts.sources['hot_roll_daily']['trace_id']
        assert [anchor['workbook_row_index'] for anchor in facts.sources['online_anneal_daily']['row_anchors']] == [
            25,
            27,
        ]
    finally:
        db.close()


def test_confirmed_imported_metric_facts_publish_with_report_rounding_and_proxy_replacement() -> None:
    db = _session()
    try:
        workshop = _workshop('RZ', '热轧车间')
        db.add(workshop)
        db.flush()
        equipment = _equipment('RZ-ZJ', '热轧机', workshop)
        shift = ShiftConfig(
            code='A',
            name='白班',
            shift_type='day',
            start_time=time(8, 0),
            end_time=time(16, 0),
            is_active=True,
        )
        db.add_all([equipment, shift])
        db.flush()
        previous_date = REPORT_DATE - timedelta(days=1)
        previous_batch = ImportBatch(
            batch_no='IMP-DAILY-METRICS-20260716',
            import_type='daily_production_report',
            source_type='daily_production_report_locked',
            file_name='daily-production-metrics-previous.xls',
            total_rows=1,
            success_rows=1,
            failed_rows=0,
            status='completed',
            quality_status='ready',
            parsed_successfully=True,
        )
        db.add(previous_batch)
        db.flush()
        previous_metrics = [
            {
                'field_name': 'total_output_daily',
                'value': 304.306,
                'unit': '吨',
                'source_anchors': [{'sheet_name': '2026-7-16', 'row_index': 39, 'column_index': 26}],
            }
        ]
        previous_import_row = ImportRow(
            batch_id=previous_batch.id,
            row_number=1,
            status='success',
            raw_data={'sheet_name': '2026-7-16'},
            mapped_data=_production_mapped_data(
                [],
                business_date=previous_date,
                report_metrics=previous_metrics,
            ),
        )
        db.add(previous_import_row)
        db.flush()
        db.add(
            _confirmed_metric_fact(
                batch=previous_batch,
                import_row=previous_import_row,
                field_name='total_output_daily',
                value=304.306,
                unit='吨',
                business_date=previous_date,
            )
        )
        batch = ImportBatch(
            batch_no='IMP-DAILY-METRICS-20260717',
            import_type='daily_production_report',
            source_type='daily_production_report_locked',
            file_name='daily-production-metrics.xls',
            total_rows=1,
            success_rows=1,
            failed_rows=0,
            status='completed',
            quality_status='ready',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        report_metrics = [
            {
                'field_name': 'total_output_daily',
                'value': 285.545,
                'unit': '吨',
                'source_anchors': [{'sheet_name': '综合报表', 'row_index': 39, 'column_index': 26}],
            },
            {
                'field_name': 'hot_roll_month',
                'value': 4250.62,
                'unit': '吨',
                'source_anchors': [{'sheet_name': '综合报表', 'row_index': 50, 'column_index': 2}],
            },
            {
                'field_name': 'foundry_gas_per_ton_daily',
                'value': 79.1592,
                'unit': 'm³/吨',
                'source_anchors': [{'sheet_name': '综合报表', 'row_index': 49, 'column_index': 15}],
            },
            {
                'field_name': 'coating_daily',
                'value': 0.0,
                'unit': '吨',
                'source_anchors': [{'sheet_name': '综合报表', 'row_index': 58, 'column_index': 1}],
            },
            {
                'field_name': 'cost_basis_weight',
                'value': 285.545,
                'unit': '吨',
                'source_anchors': [{'sheet_name': '综合报表', 'row_index': 39, 'column_index': 26}],
            },
        ]
        import_row = ImportRow(
            batch_id=batch.id,
            row_number=1,
            status='success',
            raw_data={'sheet_name': '综合报表'},
            mapped_data=_production_mapped_data(
                [_production_row(10, '热轧', '热轧', 346.32, 4250.62)],
                report_metrics=report_metrics,
            ),
        )
        db.add(import_row)
        db.flush()
        db.add(
            ShiftProductionData(
                business_date=REPORT_DATE,
                shift_config_id=shift.id,
                workshop_id=workshop.id,
                equipment_id=equipment.id,
                output_weight=346.32,
                qualified_weight=346.32,
                data_source='daily_production_report',
                import_batch_id=batch.id,
                data_status='confirmed',
            )
        )
        db.add_all(
            [
                _confirmed_metric_fact(
                    batch=batch,
                    import_row=import_row,
                    field_name=metric['field_name'],
                    value=metric['value'],
                    unit=metric['unit'],
                )
                for metric in report_metrics
            ]
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        facts.values['total_output_daily'] = 267.36
        facts.sources['total_output_daily'] = {
            'source_type': 'mes_packaging_output',
            'source_ref': 'mes_workshop_process_records',
            'trace_id': 'projection-read:mes-workshop-process',
        }
        facts.values['cost_basis_weight'] = 267.36
        facts.sources['cost_basis_weight'] = {
            'source_type': 'mes_packaging_output',
            'source_ref': 'mes_workshop_process_records',
            'trace_id': 'projection-read:mes-workshop-process:cost-basis',
        }
        template_daily_fact_sources.collect_imported_daily_production_facts(db, facts)

        assert facts.values['total_output_daily'] == 286.0
        assert facts.values['hot_roll_month'] == 4251.0
        assert facts.values['foundry_gas_per_ton_daily'] == 79.2
        assert facts.values['coating_daily'] == 0.0
        assert facts.values['cost_basis_weight'] == 285.545
        assert facts.values['total_output_delta'] == -18.0
        assert facts.sources['hot_roll_month']['source_ref'] == 'imported_daily_metric_facts'
        assert facts.sources['hot_roll_month']['import_batch_id'] == batch.id
        assert facts.sources['hot_roll_month']['metric_fact_id'] is not None
        assert facts.sources['hot_roll_month']['row_anchors'] == report_metrics[1]['source_anchors']
        assert ':hot_roll_month:' in facts.sources['hot_roll_month']['trace_id']
        metric_start, _unused = production_business_window(REPORT_DATE.replace(day=1))
        _unused, metric_end = production_business_window(REPORT_DATE)
        assert facts.sources['hot_roll_month']['business_window'] == (
            f'{metric_start.isoformat()}/{metric_end.isoformat()}'
        )
        delta_start, _unused = production_business_window(previous_date)
        _unused, delta_end = production_business_window(REPORT_DATE)
        assert facts.sources['total_output_delta']['business_window'] == (
            f'{delta_start.isoformat()}/{delta_end.isoformat()}'
        )
    finally:
        db.close()


def test_imported_metric_fact_rejects_tampering_and_does_not_overwrite_dingtalk() -> None:
    db = _session()
    try:
        workshop = _workshop('ZD', '铸锭分厂')
        db.add(workshop)
        db.flush()
        shift = ShiftConfig(
            code='A',
            name='白班',
            shift_type='day',
            start_time=time(8, 0),
            end_time=time(16, 0),
            is_active=True,
        )
        db.add(shift)
        db.flush()
        batch = ImportBatch(
            batch_no='IMP-DAILY-METRIC-TAMPER-20260717',
            import_type='daily_production_report',
            source_type='daily_production_report_locked',
            file_name='daily-production-tamper.xls',
            total_rows=1,
            success_rows=1,
            failed_rows=0,
            status='completed',
            quality_status='ready',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        report_metrics = [
            {
                'field_name': 'hot_roll_month',
                'value': 4250.62,
                'unit': '吨',
                'source_anchors': [{'sheet_name': '综合报表', 'row_index': 50, 'column_index': 2}],
            },
            {
                'field_name': 'total_output_daily',
                'value': 285.545,
                'unit': '吨',
                'source_anchors': [{'sheet_name': '综合报表', 'row_index': 39, 'column_index': 26}],
            },
        ]
        import_row = ImportRow(
            batch_id=batch.id,
            row_number=1,
            status='success',
            raw_data={'sheet_name': '综合报表'},
            mapped_data=_production_mapped_data(
                [_production_row(3, '铸锭', None, 10.0, 10.0)],
                report_metrics=report_metrics,
            ),
        )
        db.add(import_row)
        db.flush()
        db.add(
            ShiftProductionData(
                business_date=REPORT_DATE,
                shift_config_id=shift.id,
                workshop_id=workshop.id,
                output_weight=10.0,
                qualified_weight=10.0,
                data_source='daily_production_report',
                import_batch_id=batch.id,
                data_status='confirmed',
            )
        )
        tampered = _confirmed_metric_fact(
            batch=batch,
            import_row=import_row,
            field_name='hot_roll_month',
            value=9999.0,
            unit='吨',
        )
        trusted = _confirmed_metric_fact(
            batch=batch,
            import_row=import_row,
            field_name='total_output_daily',
            value=285.545,
            unit='吨',
        )
        db.add_all([tampered, trusted])
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        facts.values['total_output_daily'] = 300.0
        facts.sources['total_output_daily'] = {
            'source_type': 'dingtalk_group_content',
            'source_ref': 'multimodal_evidence',
            'trace_id': 'dingtalk-evidence:total-output',
        }
        template_daily_fact_sources.collect_imported_daily_production_facts(db, facts)

        assert 'hot_roll_month' not in facts.values
        assert facts.values['total_output_daily'] == 300.0
        assert facts.sources['total_output_daily']['source_type'] == 'dingtalk_group_content'
        assert any(conflict['reason'] == 'promoted_metric_lineage_mismatch' for conflict in facts.conflicts)
    finally:
        db.close()


def test_unpromoted_daily_production_workbook_is_not_a_report_fact() -> None:
    db = _session()
    try:
        db.add(
            ImportBatch(
                batch_no='IMP-DAILY-STAGED-ONLY',
                import_type='daily_production_report',
                source_type='daily_production_report_locked',
                file_name='staged-only.xls',
                total_rows=1,
                success_rows=1,
                failed_rows=0,
                status='completed',
                quality_status='ready',
                parsed_successfully=True,
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_imported_daily_production_facts(db, facts)

        assert facts.values == {}
    finally:
        db.close()


def test_daily_production_workbook_uses_latest_promoted_batch_and_preserves_explicit_zero() -> None:
    db = _session()
    try:
        workshop = _workshop('ZD', '铸锭分厂')
        db.add(workshop)
        db.flush()
        shift = ShiftConfig(
            code='A',
            name='白班',
            shift_type='day',
            start_time=time(8, 0),
            end_time=time(16, 0),
            is_active=True,
        )
        db.add(shift)
        db.flush()

        for suffix, daily_output, monthly_output in (
            ('OLD', 120.0, 1200.0),
            ('NEW', 0.0, 9999.0),
        ):
            batch = ImportBatch(
                batch_no=f'IMP-DAILY-{suffix}-20260717',
                import_type='daily_production_report',
                source_type='daily_production_report_locked',
                file_name=f'daily-production-{suffix.lower()}.xls',
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
                    raw_data={'sheet_name': 'daily-production'},
                    mapped_data=_production_mapped_data(
                        [
                            _production_row(3, '铸锭', None, daily_output, monthly_output),
                        ]
                    ),
                )
            )
            db.add(
                ShiftProductionData(
                    business_date=REPORT_DATE,
                    shift_config_id=shift.id,
                    workshop_id=workshop.id,
                    equipment_id=None,
                    output_weight=daily_output,
                    qualified_weight=daily_output,
                    data_source='daily_production_report',
                    import_batch_id=batch.id,
                    data_status='confirmed',
                )
            )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_imported_daily_production_facts(db, facts)

        assert facts.values['foundry_daily'] == 0.0
        assert 'foundry_month' not in facts.values
        assert facts.sources['foundry_daily']['file_name'] == 'daily-production-new.xls'
    finally:
        db.close()


def test_promoted_daily_production_workbook_rejects_failed_blocked_and_wrong_date_rows() -> None:
    db = _session()
    try:
        workshop = _workshop('ZD', '铸锭分厂')
        db.add(workshop)
        db.flush()
        shift = ShiftConfig(
            code='A',
            name='白班',
            shift_type='day',
            start_time=time(8, 0),
            end_time=time(16, 0),
            is_active=True,
        )
        db.add(shift)
        db.flush()
        batch = ImportBatch(
            batch_no='IMP-DAILY-TRUSTED-ROWS-20260717',
            import_type='daily_production_report',
            source_type='daily_production_report_locked',
            file_name='daily-production-trusted-rows.xls',
            total_rows=4,
            success_rows=3,
            failed_rows=1,
            status='completed',
            quality_status='warning',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        payloads = [
            ('success', REPORT_DATE, 'ready', 10.0),
            ('failed', REPORT_DATE, 'ready', 100.0),
            ('success', REPORT_DATE, 'blocked', 1000.0),
            ('success', date(2026, 7, 16), 'ready', 10000.0),
        ]
        import_rows = []
        for row_number, (status, business_date, quality_status, output) in enumerate(payloads, start=1):
            import_rows.append(
                ImportRow(
                    batch_id=batch.id,
                    row_number=row_number,
                    status=status,
                    raw_data={'sheet_name': f'row-{row_number}'},
                    mapped_data=_production_mapped_data(
                        [_production_row(row_number + 2, '铸锭', None, output, output)],
                        business_date=business_date,
                        quality_status=quality_status,
                    ),
                )
            )
        db.add_all(import_rows)
        db.add(
            ShiftProductionData(
                business_date=REPORT_DATE,
                shift_config_id=shift.id,
                workshop_id=workshop.id,
                equipment_id=None,
                output_weight=10.0,
                qualified_weight=10.0,
                data_source='daily_production_report',
                import_batch_id=batch.id,
                data_status='confirmed',
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_imported_daily_production_facts(db, facts)

        assert facts.values['foundry_daily'] == 10.0
        assert facts.sources['foundry_daily']['row_anchors'] == [
            {
                'import_row_id': import_rows[0].id,
                'import_row_number': 1,
                'workbook_row_index': 3,
            }
        ]
    finally:
        db.close()


def test_daily_production_workbook_requires_matching_promoted_bucket() -> None:
    db = _session()
    try:
        workshop = _workshop('ZD', '铸锭分厂')
        db.add(workshop)
        db.flush()
        shift = ShiftConfig(
            code='A',
            name='白班',
            shift_type='day',
            start_time=time(8, 0),
            end_time=time(16, 0),
            is_active=True,
        )
        db.add(shift)
        db.flush()
        batch = ImportBatch(
            batch_no='IMP-DAILY-PARTIAL-PROMOTION-20260717',
            import_type='daily_production_report',
            source_type='daily_production_report_locked',
            file_name='daily-production-partial-promotion.xls',
            total_rows=2,
            success_rows=2,
            failed_rows=0,
            status='completed',
            quality_status='ready',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ImportRow(
                    batch_id=batch.id,
                    row_number=1,
                    status='success',
                    raw_data={'sheet_name': 'trusted'},
                    mapped_data=_production_mapped_data([_production_row(3, '铸锭', None, 10.0, 10.0)]),
                ),
                ImportRow(
                    batch_id=batch.id,
                    row_number=2,
                    status='success',
                    raw_data={'sheet_name': 'not-promoted'},
                    mapped_data=_production_mapped_data([_production_row(4, '铸锭', None, 999.0, 999.0)]),
                ),
            ]
        )
        db.add(
            ShiftProductionData(
                business_date=REPORT_DATE,
                shift_config_id=shift.id,
                workshop_id=workshop.id,
                equipment_id=None,
                input_weight=None,
                output_weight=10.0,
                qualified_weight=10.0,
                scrap_weight=None,
                data_source='daily_production_report',
                import_batch_id=batch.id,
                data_status='confirmed',
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_imported_daily_production_facts(db, facts)

        assert 'foundry_daily' not in facts.values
        assert facts.conflicts == [
            {
                'field': 'daily_production_workbook',
                'reason': 'promoted_lineage_mismatch',
                'import_batch_id': batch.id,
                'bucket_count': 1,
            }
        ]
    finally:
        db.close()


def _energy_row(row_number: int, energy_type: str, source_label: str, value: float) -> ImportRow:
    report_field = daily_energy_report_fact_field(energy_type, source_label)
    return ImportRow(
        batch_id=0,
        row_number=row_number,
        status='success' if source_label not in {'合计', '高压合计', '回收', '餐厅'} else 'skipped',
        raw_data={'source_label': source_label},
        mapped_data={
            'business_date': REPORT_DATE.isoformat(),
            'source_kind': f'workshop_{energy_type}',
            'source_file': f'{energy_type}-2026-07-17.xlsx',
            'source_sheet': '用量',
            'source_row_no': row_number + 10,
            'energy_type': energy_type,
            'source_label': source_label,
            'energy_value': value,
            'unit': 'kWh' if energy_type == 'electricity' else 'm3',
            'report_field': report_field,
        },
    )


def test_promoted_energy_workbook_fills_explicit_totals_and_gas_breakdown() -> None:
    db = _session()
    try:
        batch = ImportBatch(
            batch_no='IMP-ENERGY-LOCKED-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-energy-2026-07-17',
            total_rows=15,
            success_rows=10,
            failed_rows=0,
            skipped_rows=5,
            status='completed',
            quality_status='warning',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        rows = [
            _energy_row(1, 'electricity', '合计', 172010),
            _energy_row(2, 'electricity', '高压合计', 173500),
            _energy_row(3, 'gas', '铸锭', 24524),
            _energy_row(4, 'gas', '回收', 690),
            _energy_row(5, 'gas', '铸二', 5454),
            _energy_row(6, 'gas', '铸三', 5601),
            _energy_row(7, 'gas', '热轧/2#加热炉东', 5189),
            _energy_row(8, 'gas', '热轧/2#加热炉西', 4733),
            _energy_row(9, 'gas', '热轧/锅炉', 2607),
            _energy_row(10, 'gas', '拉矫/退火炉', 3621),
            _energy_row(11, 'gas', '拉矫/锅炉', 1179),
            _energy_row(12, 'gas', '北线', 2424),
            _energy_row(13, 'gas', '南线', 2152),
            _energy_row(14, 'gas', '餐厅', 17),
            _energy_row(15, 'gas', '合计', 58191),
        ]
        for row in rows:
            row.batch_id = batch.id
        db.add_all(rows)
        db.add(
            EnergyImportRecord(
                import_batch_id=batch.id,
                business_date=REPORT_DATE,
                workshop_code='ZD',
                shift_code=None,
                energy_type='gas',
                energy_value=24524,
                unit='m3',
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        facts.values['cost_basis_weight'] = 2000.0
        facts.sources['cost_basis_weight'] = {
            'source_type': 'mes_packaging_output',
            'source_ref': 'mes_stock_records',
            'trace_id': 'mes-read:mes_stock_records:2026-07-17',
        }
        template_daily_fact_sources.collect_imported_energy_workbook_facts(db, facts)

        assert facts.values['total_electricity_kwh'] == 173500
        assert facts.values['subitem_electricity_kwh'] == 172010
        assert facts.values['total_gas_m3'] == 58191
        assert facts.values['cast_roll_gas_m3'] == 11055
        assert facts.values['hot_roll_furnace_gas_m3'] == 9922
        assert facts.values['recovery_gas_m3'] == 690
        assert facts.values['canteen_gas_m3'] == 17
        assert facts.values['electricity_cost_10k'] == 13.88
        assert facts.values['gas_cost_10k'] == 20.95
        assert facts.values['total_cost_10k'] == 34.83
        assert facts.values['cost_per_ton'] == 174.0
        assert facts.sources['total_electricity_kwh']['source_type'] == 'manual_workbook'
        assert facts.sources['total_electricity_kwh']['import_batch_id'] == batch.id
        energy_start, energy_end = production_business_window(REPORT_DATE)
        assert facts.sources['total_electricity_kwh']['business_window'] == (
            f'{energy_start.isoformat()}/{energy_end.isoformat()}'
        )
        assert facts.sources['total_electricity_kwh']['metric_contract_version'] == '2026-07-11'
        assert facts.sources['total_electricity_kwh']['field_contract_version'] == (
            DAILY_REPORT_FIELD_CONTRACT_VERSION
        )
        assert facts.sources['total_electricity_kwh']['row_anchors'] == [
            {
                'import_row_id': rows[1].id,
                'import_row_number': 2,
                'workbook_row_number': 12,
                'source_file': 'electricity-2026-07-17.xlsx',
                'source_sheet': '用量',
                'source_label': '高压合计',
            }
        ]
        assert ':total_electricity_kwh:' in facts.sources['total_electricity_kwh']['trace_id']
        component_sources = facts.sources['total_cost_10k']['component_sources']
        assert component_sources['total_electricity_kwh']['source_type'] == 'manual_workbook'
        assert component_sources['total_electricity_kwh']['import_batch_id'] == batch.id
        assert component_sources['total_electricity_kwh']['row_anchors'] == (
            facts.sources['total_electricity_kwh']['row_anchors']
        )
        assert component_sources['total_gas_m3']['source_type'] == 'manual_workbook'
        assert component_sources['total_gas_m3']['import_batch_id'] == batch.id
        assert facts.sources['total_cost_10k']['unit_prices'] == {
            'electricity': 0.8,
            'gas': 3.6,
        }
        assert [anchor['import_row_id'] for anchor in facts.sources['cast_roll_gas_m3']['row_anchors']] == [
            rows[4].id,
            rows[5].id,
        ]
        assert facts.sources['total_cost_10k']['trace_id'] != facts.sources['cost_per_ton']['trace_id']
        assert facts.sources['cost_per_ton']['components'] == [
            'total_electricity_kwh',
            'total_gas_m3',
            'cost_basis_weight',
        ]
        assert facts.sources['cost_per_ton']['component_sources']['cost_basis_weight'] == {
            'source_type': 'mes_packaging_output',
            'source_ref': 'mes_stock_records',
            'trace_id': 'mes-read:mes_stock_records:2026-07-17',
        }
    finally:
        db.close()


def test_legacy_furnace_field_is_reclassified_only_with_matching_promoted_records() -> None:
    db = _session()
    try:
        batch = ImportBatch(
            batch_no='IMP-ENERGY-LEGACY-FURNACE-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-energy-legacy-furnace.xlsx',
            total_rows=2,
            success_rows=2,
            failed_rows=0,
            skipped_rows=0,
            status='completed',
            quality_status='ready',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        east = _energy_row(1, 'gas', '热轧加热炉/1#东炉', 0)
        west = _energy_row(2, 'gas', '热轧加热炉/1#西炉', 0)
        for row in (east, west):
            row.batch_id = batch.id
            row.mapped_data['report_field'] = 'hot_roll_furnace_gas_m3'
        db.add_all([east, west])
        db.add_all(
            [
                EnergyImportRecord(
                    import_batch_id=batch.id,
                    business_date=REPORT_DATE,
                    workshop_code='RZ',
                    shift_code=None,
                    energy_type='gas',
                    energy_value=0,
                    unit='m3',
                    source_row_no=11,
                ),
                EnergyImportRecord(
                    import_batch_id=batch.id,
                    business_date=REPORT_DATE,
                    workshop_code='RZ',
                    shift_code=None,
                    energy_type='gas',
                    energy_value=0,
                    unit='m3',
                    source_row_no=12,
                ),
            ]
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_imported_energy_workbook_facts(db, facts)

        assert facts.values['east_furnace_gas_m3'] == 0
        assert facts.values['west_furnace_gas_m3'] == 0
        assert facts.values['hot_roll_furnace_gas_m3'] == 0
    finally:
        db.close()


def test_legacy_furnace_field_without_matching_promoted_record_is_rejected() -> None:
    db = _session()
    try:
        batch = ImportBatch(
            batch_no='IMP-ENERGY-UNPROVEN-LEGACY-FURNACE-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-energy-unproven-legacy-furnace.xlsx',
            total_rows=1,
            success_rows=1,
            failed_rows=0,
            skipped_rows=0,
            status='completed',
            quality_status='ready',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        row = _energy_row(1, 'gas', '热轧加热炉/1#东炉', 0)
        row.batch_id = batch.id
        row.mapped_data['report_field'] = 'hot_roll_furnace_gas_m3'
        db.add(row)
        db.add(
            EnergyImportRecord(
                import_batch_id=batch.id,
                business_date=REPORT_DATE,
                workshop_code='RZ',
                shift_code=None,
                energy_type='gas',
                energy_value=1,
                unit='m3',
                source_row_no=99,
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_imported_energy_workbook_facts(db, facts)

        assert 'east_furnace_gas_m3' not in facts.values
        assert 'hot_roll_furnace_gas_m3' not in facts.values
    finally:
        db.close()


def test_promoted_energy_workbook_does_not_invent_total_cost_when_gas_is_missing() -> None:
    db = _session()
    try:
        batch = ImportBatch(
            batch_no='IMP-ENERGY-ELECTRICITY-ONLY-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-electricity-2026-07-17',
            total_rows=1,
            success_rows=0,
            failed_rows=0,
            skipped_rows=1,
            status='completed',
            quality_status='warning',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        row = _energy_row(1, 'electricity', '高压合计', 173500)
        row.batch_id = batch.id
        db.add(row)
        db.add(
            EnergyImportRecord(
                import_batch_id=batch.id,
                business_date=REPORT_DATE,
                workshop_code='RZ',
                shift_code=None,
                energy_type='electricity',
                energy_value=1000,
                unit='kWh',
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_imported_energy_workbook_facts(db, facts)

        assert facts.values['total_electricity_kwh'] == 173500
        assert facts.values['electricity_cost_10k'] == 13.88
        assert 'gas_cost_10k' not in facts.values
        assert 'total_cost_10k' not in facts.values
        assert 'cost_per_ton' not in facts.values
    finally:
        db.close()


def test_energy_cost_per_ton_uses_unrounded_component_costs() -> None:
    db = _session()
    try:
        batch = ImportBatch(
            batch_no='IMP-ENERGY-UNROUNDED-COST-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-energy-unrounded.xlsx',
            total_rows=2,
            success_rows=0,
            failed_rows=0,
            skipped_rows=2,
            status='completed',
            quality_status='warning',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        electricity_row = _energy_row(1, 'electricity', '高压合计', 183500)
        gas_row = _energy_row(2, 'gas', '合计', 60961)
        electricity_row.batch_id = batch.id
        gas_row.batch_id = batch.id
        db.add_all([electricity_row, gas_row])
        db.add(
            EnergyImportRecord(
                import_batch_id=batch.id,
                business_date=REPORT_DATE,
                workshop_code='RZ',
                shift_code=None,
                energy_type='electricity',
                energy_value=1000,
                unit='kWh',
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        facts.values['cost_basis_weight'] = 343.781
        facts.sources['cost_basis_weight'] = {
            'source_type': 'manual_workbook',
            'source_ref': 'imported_daily_metric_facts',
            'trace_id': 'import-read:cost-basis',
        }
        template_daily_fact_sources.collect_imported_energy_workbook_facts(db, facts)

        assert facts.values['electricity_cost_10k'] == 14.68
        assert facts.values['gas_cost_10k'] == 21.95
        assert facts.values['total_cost_10k'] == 36.63
        assert facts.values['cost_per_ton'] == 1065.0
    finally:
        db.close()


def test_energy_workbook_uses_latest_promoted_batch_and_ignores_newer_staged_batch() -> None:
    db = _session()
    try:
        promoted_batches = []
        for suffix, total in (('OLD', 170000), ('NEW', 180000)):
            batch = ImportBatch(
                batch_no=f'IMP-ENERGY-{suffix}-20260717',
                import_type='energy',
                source_type='daily_energy_report_locked',
                file_name=f'daily-energy-{suffix.lower()}.xlsx',
                total_rows=1,
                success_rows=0,
                failed_rows=0,
                skipped_rows=1,
                status='completed',
                quality_status='warning',
                parsed_successfully=True,
            )
            db.add(batch)
            db.flush()
            row = _energy_row(1, 'electricity', '高压合计', total)
            row.batch_id = batch.id
            db.add(row)
            db.add(
                EnergyImportRecord(
                    import_batch_id=batch.id,
                    business_date=REPORT_DATE,
                    workshop_code='RZ',
                    shift_code=None,
                    energy_type='electricity',
                    energy_value=1000,
                    unit='kWh',
                )
            )
            promoted_batches.append(batch)

        staged = ImportBatch(
            batch_no='IMP-ENERGY-STAGED-ONLY-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-energy-staged-only.xlsx',
            total_rows=1,
            success_rows=0,
            failed_rows=0,
            skipped_rows=1,
            status='completed',
            quality_status='warning',
            parsed_successfully=True,
        )
        db.add(staged)
        db.flush()
        staged_row = _energy_row(1, 'electricity', '高压合计', 999999)
        staged_row.batch_id = staged.id
        db.add(staged_row)
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_imported_energy_workbook_facts(db, facts)

        assert facts.values['total_electricity_kwh'] == 180000
        assert facts.sources['total_electricity_kwh']['import_batch_id'] == promoted_batches[-1].id
    finally:
        db.close()


def test_promoted_energy_workbook_rejects_untrusted_rows() -> None:
    db = _session()
    try:
        batch = ImportBatch(
            batch_no='IMP-ENERGY-CANONICAL-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-energy-canonical.xlsx',
            total_rows=5,
            success_rows=0,
            failed_rows=1,
            skipped_rows=4,
            status='completed',
            quality_status='warning',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        trusted = _energy_row(1, 'electricity', '高压合计', 173500)
        trusted.batch_id = batch.id
        tampered = _energy_row(2, 'electricity', '任意跳过行', 999999)
        tampered.batch_id = batch.id
        tampered.status = 'skipped'
        tampered.mapped_data = {**tampered.mapped_data, 'report_field': 'total_electricity_kwh'}
        failed = _energy_row(3, 'electricity', '高压合计', 888888)
        failed.batch_id = batch.id
        failed.status = 'failed'
        wrong_date = _energy_row(4, 'electricity', '高压合计', 777777)
        wrong_date.batch_id = batch.id
        wrong_date.mapped_data = {
            **wrong_date.mapped_data,
            'business_date': date(2026, 7, 16).isoformat(),
        }
        nonfinite = _energy_row(5, 'electricity', '高压合计', float('nan'))
        nonfinite.batch_id = batch.id
        db.add_all([trusted, tampered, failed, wrong_date, nonfinite])
        db.add(
            EnergyImportRecord(
                import_batch_id=batch.id,
                business_date=REPORT_DATE,
                workshop_code='RZ',
                shift_code=None,
                energy_type='electricity',
                energy_value=1000,
                unit='kWh',
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_imported_energy_workbook_facts(db, facts)

        assert facts.values['total_electricity_kwh'] == 173500
        assert facts.sources['total_electricity_kwh']['row_anchors'][0]['import_row_id'] == trusted.id
        assert len(facts.sources['total_electricity_kwh']['row_anchors']) == 1
    finally:
        db.close()


def test_energy_workbook_does_not_mix_manual_workbook_batches_for_total_cost() -> None:
    db = _session()
    try:
        old_batch = ImportBatch(
            batch_no='IMP-ENERGY-OLD-GAS-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-energy-old-gas.xlsx',
            total_rows=1,
            success_rows=0,
            failed_rows=0,
            skipped_rows=1,
            status='completed',
            quality_status='warning',
            parsed_successfully=True,
        )
        db.add(old_batch)
        db.flush()
        old_row = _energy_row(1, 'gas', '合计', 58191)
        old_row.batch_id = old_batch.id
        db.add(old_row)
        db.add(
            EnergyImportRecord(
                import_batch_id=old_batch.id,
                business_date=REPORT_DATE,
                workshop_code='ZD',
                shift_code=None,
                energy_type='gas',
                energy_value=1000,
                unit='m3',
            )
        )

        new_batch = ImportBatch(
            batch_no='IMP-ENERGY-NEW-ELECTRICITY-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-energy-new-electricity.xlsx',
            total_rows=1,
            success_rows=0,
            failed_rows=0,
            skipped_rows=1,
            status='completed',
            quality_status='warning',
            parsed_successfully=True,
        )
        db.add(new_batch)
        db.flush()
        new_row = _energy_row(1, 'electricity', '高压合计', 173500)
        new_row.batch_id = new_batch.id
        db.add(new_row)
        db.add(
            EnergyImportRecord(
                import_batch_id=new_batch.id,
                business_date=REPORT_DATE,
                workshop_code='RZ',
                shift_code=None,
                energy_type='electricity',
                energy_value=1000,
                unit='kWh',
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        facts.values['total_gas_m3'] = 58191.0
        facts.sources['total_gas_m3'] = {
            'source_type': 'manual_workbook',
            'source_ref': 'import_rows',
            'import_batch_id': old_batch.id,
            'trace_id': f'import-read:import_rows:{old_batch.id}:total_gas_m3:1',
        }
        template_daily_fact_sources.collect_imported_energy_workbook_facts(db, facts)

        assert facts.values['electricity_cost_10k'] == 13.88
        assert facts.values['gas_cost_10k'] == 20.95
        assert 'total_cost_10k' not in facts.values
        assert 'cost_per_ton' not in facts.values
        assert facts.conflicts == [
            {
                'field': 'total_cost_10k',
                'reason': 'mixed_energy_source_batch',
                'component_fields': ['total_electricity_kwh', 'total_gas_m3'],
            }
        ]
    finally:
        db.close()


def test_energy_workbook_does_not_derive_per_ton_cost_from_rejected_total_cost() -> None:
    db = _session()
    try:
        batch = ImportBatch(
            batch_no='IMP-ENERGY-HIGH-PRIORITY-COST-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-energy-high-priority-cost.xlsx',
            total_rows=2,
            success_rows=1,
            failed_rows=0,
            skipped_rows=1,
            status='completed',
            quality_status='warning',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        electricity_row = _energy_row(1, 'electricity', '高压合计', 173500)
        gas_row = _energy_row(2, 'gas', '合计', 58191)
        electricity_row.batch_id = batch.id
        gas_row.batch_id = batch.id
        db.add_all([electricity_row, gas_row])
        db.add(
            EnergyImportRecord(
                import_batch_id=batch.id,
                business_date=REPORT_DATE,
                workshop_code='RZ',
                shift_code=None,
                energy_type='electricity',
                energy_value=1000,
                unit='kWh',
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        facts.values.update({'total_cost_10k': 50.0, 'cost_basis_weight': 2000.0})
        facts.sources['total_cost_10k'] = {
            'source_type': 'dingtalk_group_content',
            'source_ref': 'multimodal_evidence',
            'trace_id': 'dingtalk-evidence:total-cost:2026-07-17',
        }
        facts.sources['cost_basis_weight'] = {
            'source_type': 'mes_packaging_output',
            'source_ref': 'mes_stock_records',
            'trace_id': 'mes-read:cost-basis:2026-07-17',
        }
        template_daily_fact_sources.collect_imported_energy_workbook_facts(db, facts)

        assert facts.values['total_cost_10k'] == 50.0
        assert 'cost_per_ton' not in facts.values
        assert facts.conflicts == [
            {
                'field': 'cost_per_ton',
                'reason': 'total_cost_source_rejected_workbook_value',
                'component_fields': ['total_cost_10k', 'cost_basis_weight'],
            }
        ]
    finally:
        db.close()


def test_template_fact_setter_rejects_nonfinite_numbers() -> None:
    facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)

    template_daily_fact_sources._set_value(facts, 'total_electricity_kwh', float('nan'), 'manual_workbook')
    template_daily_fact_sources._set_value(facts, 'total_gas_m3', float('inf'), 'manual_workbook')

    assert facts.values == {}
    assert facts.sources == {}


def test_manual_energy_workbook_cannot_overwrite_dingtalk_fact() -> None:
    db = _session()
    try:
        batch = ImportBatch(
            batch_no='IMP-ENERGY-PRIORITY-20260717',
            import_type='energy',
            source_type='daily_energy_report_locked',
            file_name='daily-energy-priority.xlsx',
            total_rows=2,
            success_rows=1,
            failed_rows=0,
            skipped_rows=1,
            status='completed',
            quality_status='warning',
            parsed_successfully=True,
        )
        db.add(batch)
        db.flush()
        electricity_row = _energy_row(1, 'electricity', '高压合计', 173500)
        gas_row = _energy_row(2, 'gas', '合计', 58191)
        electricity_row.batch_id = batch.id
        gas_row.batch_id = batch.id
        db.add_all([electricity_row, gas_row])
        db.add(
            EnergyImportRecord(
                import_batch_id=batch.id,
                business_date=REPORT_DATE,
                workshop_code='RZ',
                shift_code=None,
                energy_type='electricity',
                energy_value=1000,
                unit='kWh',
            )
        )
        db.commit()

        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        facts.values['total_electricity_kwh'] = 175000.0
        facts.sources['total_electricity_kwh'] = {
            'source_type': 'dingtalk_group_content',
            'source_ref': 'multimodal_evidence',
            'trace_id': 'dingtalk-evidence:energy:2026-07-17',
            'business_date': REPORT_DATE.isoformat(),
        }
        template_daily_fact_sources.collect_imported_energy_workbook_facts(db, facts)

        assert facts.values['total_electricity_kwh'] == 175000.0
        assert facts.sources['total_electricity_kwh']['source_type'] == 'dingtalk_group_content'
        assert facts.sources['total_electricity_kwh']['trace_id'] == 'dingtalk-evidence:energy:2026-07-17'
        assert facts.values['electricity_cost_10k'] == 14.0
        assert facts.sources['electricity_cost_10k']['component_sources']['total_electricity_kwh'] == {
            'source_type': 'dingtalk_group_content',
            'source_ref': 'multimodal_evidence',
            'trace_id': 'dingtalk-evidence:energy:2026-07-17',
            'business_date': REPORT_DATE.isoformat(),
        }
        assert facts.values['total_gas_m3'] == 58191
        assert facts.values['gas_cost_10k'] == 20.95
        assert 'total_cost_10k' not in facts.values
        assert 'cost_per_ton' not in facts.values
        assert facts.conflicts == [
            {
                'field': 'total_cost_10k',
                'reason': 'mixed_energy_source_batch',
                'component_fields': ['total_electricity_kwh', 'total_gas_m3'],
            }
        ]
    finally:
        db.close()


@pytest.mark.parametrize(
    ('latest_batch_name', 'collector_name'),
    [
        ('_latest_promoted_daily_production_batch', 'collect_imported_daily_production_facts'),
        ('_latest_promoted_energy_batch', 'collect_imported_energy_workbook_facts'),
    ],
)
def test_imported_workbook_collectors_propagate_database_errors_without_rollback(
    monkeypatch: pytest.MonkeyPatch,
    latest_batch_name: str,
    collector_name: str,
) -> None:
    db = MagicMock()
    error = OperationalError('SELECT batch', {}, RuntimeError('database unavailable'))
    monkeypatch.setattr(template_daily_fact_sources, '_has_table', lambda *_args: True)
    monkeypatch.setattr(template_daily_fact_sources, latest_batch_name, MagicMock(side_effect=error))

    with pytest.raises(OperationalError):
        getattr(template_daily_fact_sources, collector_name)(
            db,
            template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE),
        )

    db.rollback.assert_not_called()
