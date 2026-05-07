# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import Base, get_sessionmaker
import app.models  # noqa: F401  # register metadata for dry-run databases
from app.models.energy import EnergyImportRecord
from app.models.imports import ImportBatch, ImportRow
from app.services.daily_energy_report_service import (
    ParsedDailyEnergyRow,
    daily_energy_row_summary_fields,
    parse_daily_energy_workbooks,
)
from app.services.real_master_data import seed_real_master_data


LOCKED_SOURCE_TYPE = 'daily_energy_report_locked'


def _parse_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('日期格式必须为 YYYY-MM-DD') from exc


def _create_dry_run_session() -> Session:
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
    return SessionLocal()


def _quality_status(rows: list[ParsedDailyEnergyRow]) -> str:
    if not rows:
        return 'blocked'
    if any(row.status == 'failed' for row in rows):
        return 'blocked'
    if any(row.status == 'skipped' for row in rows):
        return 'warning'
    return 'ready'


def _sum_rows(rows: list[ParsedDailyEnergyRow], energy_type: str) -> float:
    total = sum(float(row.energy_value or 0.0) for row in rows if row.status == 'success' and row.energy_type == energy_type)
    return round(total, 3)


def _mapping_payload(rows: list[ParsedDailyEnergyRow]) -> dict[str, Any]:
    ready_rows = [row for row in rows if row.status == 'success']
    skipped_rows = [row for row in rows if row.status == 'skipped']
    failed_rows = [row for row in rows if row.status == 'failed']
    return {
        'total_rows': len(rows),
        'ready_rows': len(ready_rows),
        'skipped_rows': len(skipped_rows),
        'failed_rows': len(failed_rows),
        'rows': [
            {
                **row.mapped_data,
                'error_msg': row.error_msg,
            }
            for row in rows
        ],
    }


def _blocking_issues(rows: list[ParsedDailyEnergyRow]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not rows:
        issues.append({'code': 'no_daily_energy_rows', 'message': '未解析到可用能耗行。'})
    if not any(row.status == 'success' for row in rows):
        issues.append({'code': 'no_mapped_daily_energy_rows', 'message': '未匹配到可写入的车间能耗行。'})
    failed_rows = [row for row in rows if row.status == 'failed']
    if failed_rows:
        issues.append({'code': 'failed_daily_energy_rows', 'message': f'存在 {len(failed_rows)} 行解析失败。'})
    return issues


def _file_summary(electricity_file: str | Path | None, gas_file: str | Path | None) -> dict[str, Any]:
    return {
        'electricity_file': str(electricity_file) if electricity_file else None,
        'gas_file': str(gas_file) if gas_file else None,
    }


def _build_output_payload(
    *,
    report_date: date,
    rows: list[ParsedDailyEnergyRow],
    electricity_file: str | Path | None,
    gas_file: str | Path | None,
    staging_write: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocking_issues = _blocking_issues(rows)
    payload = {
        'hard_gate_passed': not blocking_issues,
        'business_date': report_date.isoformat(),
        'source': _file_summary(electricity_file, gas_file),
        'parse': {
            'quality_status': _quality_status(rows),
            'columns': daily_energy_row_summary_fields(),
        },
        'totals': {
            'electricity_value': _sum_rows(rows, 'electricity'),
            'gas_value': _sum_rows(rows, 'gas'),
            'water_value': _sum_rows(rows, 'water'),
        },
        'mapping': _mapping_payload(rows),
        'blocking_issues': blocking_issues,
    }
    if staging_write is not None:
        payload['staging_write'] = staging_write
    return payload


def build_daily_energy_dry_run(
    *,
    report_date: date,
    electricity_file: str | Path | None = None,
    gas_file: str | Path | None = None,
) -> dict[str, Any]:
    rows = parse_daily_energy_workbooks(
        report_date=report_date,
        electricity_file=electricity_file,
        gas_file=gas_file,
    )
    return _build_output_payload(
        report_date=report_date,
        rows=rows,
        electricity_file=electricity_file,
        gas_file=gas_file,
    )


def _store_transient_batch(
    db: Session,
    *,
    report_date: date,
    rows: list[ParsedDailyEnergyRow],
    electricity_file: str | Path | None,
    gas_file: str | Path | None,
    source_type: str,
    commit: bool,
) -> ImportBatch:
    batch = ImportBatch(
        batch_no=f"IMP-ENERGY-LOCKED-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        import_type='energy',
        source_type=source_type,
        file_name=f'daily-energy-{report_date.isoformat()}',
        file_size=sum(Path(path).stat().st_size for path in (electricity_file, gas_file) if path),
        file_path=json.dumps(_file_summary(electricity_file, gas_file), ensure_ascii=False),
        total_rows=len(rows),
        success_rows=len([row for row in rows if row.status == 'success']),
        failed_rows=len([row for row in rows if row.status == 'failed']),
        skipped_rows=len([row for row in rows if row.status == 'skipped']),
        status='completed',
        quality_status=_quality_status(rows),
        parsed_successfully=bool(rows) and any(row.status == 'success' for row in rows),
    )
    db.add(batch)
    db.flush()
    for row_number, row in enumerate(rows, start=1):
        db.add(
            ImportRow(
                batch_id=batch.id,
                row_number=row_number,
                raw_data=row.raw_data,
                mapped_data=row.mapped_data,
                status=row.status,
                error_msg=row.error_msg,
            )
        )
    db.flush()
    if commit:
        db.commit()
    return batch


def stage_daily_energy_import(
    *,
    report_date: date,
    db: Session,
    electricity_file: str | Path | None = None,
    gas_file: str | Path | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    rows = parse_daily_energy_workbooks(
        report_date=report_date,
        electricity_file=electricity_file,
        gas_file=gas_file,
    )
    batch = _store_transient_batch(
        db,
        report_date=report_date,
        rows=rows,
        electricity_file=electricity_file,
        gas_file=gas_file,
        source_type=LOCKED_SOURCE_TYPE,
        commit=False,
    )
    payload = _build_output_payload(
        report_date=report_date,
        rows=rows,
        electricity_file=electricity_file,
        gas_file=gas_file,
    )
    if not commit or not payload['hard_gate_passed']:
        db.rollback()
        payload['staging_write'] = {
            'committed': False,
            'batch_id': None,
            'rows_written': 0,
            'energy_record_rows_written': 0,
        }
        return payload

    db.commit()
    payload['staging_write'] = {
        'committed': True,
        'batch_id': batch.id,
        'rows_written': len(rows),
        'energy_record_rows_written': 0,
    }
    return payload


def _successful_import_rows(db: Session, *, batch_id: int) -> list[ImportRow]:
    return (
        db.query(ImportRow)
        .filter(ImportRow.batch_id == batch_id, ImportRow.status == 'success')
        .order_by(ImportRow.row_number.asc())
        .all()
    )


def _duplicate_records(db: Session, *, rows: list[ImportRow]) -> list[dict[str, Any]]:
    duplicates: list[dict[str, Any]] = []
    for row in rows:
        mapped = row.mapped_data if isinstance(row.mapped_data, dict) else {}
        business_date = date.fromisoformat(str(mapped.get('business_date')))
        workshop_code = mapped.get('workshop_code')
        energy_type = mapped.get('energy_type')
        existing = (
            db.query(EnergyImportRecord)
            .filter(
                EnergyImportRecord.business_date == business_date,
                EnergyImportRecord.workshop_code == workshop_code,
                EnergyImportRecord.shift_code.is_(None),
                EnergyImportRecord.energy_type == energy_type,
            )
            .first()
        )
        if existing is not None:
            duplicates.append(
                {
                    'existing_id': existing.id,
                    'business_date': business_date.isoformat(),
                    'workshop_code': workshop_code,
                    'energy_type': energy_type,
                }
            )
    return duplicates


def promote_daily_energy_batch(
    db: Session,
    *,
    batch_id: int,
    commit: bool = False,
) -> dict[str, Any]:
    batch = db.get(ImportBatch, batch_id)
    if batch is None or batch.import_type != 'energy' or batch.source_type != LOCKED_SOURCE_TYPE:
        raise ValueError(f'daily energy batch not found: {batch_id}')

    rows = _successful_import_rows(db, batch_id=batch.id)
    blocking_issues: list[dict[str, Any]] = []
    if batch.quality_status == 'blocked':
        blocking_issues.append({'code': 'blocked_daily_energy_batch', 'message': '能耗暂存批次处于 blocked 状态。'})
    if not rows:
        blocking_issues.append({'code': 'no_mapped_daily_energy_rows', 'message': '暂存批次没有可写入能耗行。'})
    duplicates = _duplicate_records(db, rows=rows)
    if duplicates:
        blocking_issues.append(
            {
                'code': 'duplicate_daily_energy_record',
                'message': f'已有 {len(duplicates)} 条同日/车间/类型能耗记录，默认拒绝覆盖。',
                'duplicates': duplicates,
            }
        )

    if blocking_issues:
        db.rollback()
        return {
            'committed': False,
            'batch_id': batch.id,
            'record_rows_written': 0,
            'projected_record_rows': len(rows),
            'blocking_issues': blocking_issues,
        }

    if not commit:
        return {
            'committed': False,
            'batch_id': batch.id,
            'record_rows_written': 0,
            'projected_record_rows': len(rows),
            'blocking_issues': [],
        }

    written = 0
    for row in rows:
        mapped = row.mapped_data if isinstance(row.mapped_data, dict) else {}
        record = EnergyImportRecord(
            import_batch_id=batch.id,
            business_date=date.fromisoformat(str(mapped.get('business_date'))),
            workshop_code=mapped.get('workshop_code'),
            shift_code=None,
            energy_type=mapped.get('energy_type'),
            energy_value=mapped.get('energy_value'),
            unit=mapped.get('unit'),
            source_row_no=mapped.get('source_row_no') or row.row_number,
            raw_payload=row.raw_data,
        )
        db.add(record)
        written += 1
    db.commit()
    return {
        'committed': True,
        'batch_id': batch.id,
        'record_rows_written': written,
        'projected_record_rows': written,
        'blocking_issues': [],
    }


def _print_text(payload: dict[str, Any]) -> None:
    print(f"硬门禁：{'通过' if payload['hard_gate_passed'] else '未通过'}")
    print(f"报告日：{payload['business_date']}")
    print(f"电耗文件：{payload['source']['electricity_file'] or '--'}")
    print(f"气耗文件：{payload['source']['gas_file'] or '--'}")
    print(
        '能耗合计：'
        f"电 {payload['totals']['electricity_value']} kWh，"
        f"气 {payload['totals']['gas_value']} m3"
    )
    mapping = payload['mapping']
    print(
        '映射结果：'
        f"{mapping['ready_rows']}/{mapping['total_rows']} ready，"
        f"跳过 {mapping['skipped_rows']}，"
        f"失败 {mapping['failed_rows']}"
    )
    if payload['blocking_issues']:
        print('硬阻断：')
        for issue in payload['blocking_issues']:
            print(f"- [{issue.get('code')}] {issue.get('message')}")
    if payload.get('staging_write'):
        staging = payload['staging_write']
        print(
            '暂存写入：'
            f"{'已提交' if staging['committed'] else '未提交'}，"
            f"批次 {staging.get('batch_id') or '--'}，"
            f"暂存行 {staging['rows_written']}，"
            f"正式能耗行 {staging['energy_record_rows_written']}"
        )


def _print_promotion_text(payload: dict[str, Any]) -> None:
    print(f"正式能耗写入：{'已提交' if payload['committed'] else '未提交'}")
    print(f"批次：{payload['batch_id']}")
    print(f"写入能耗行：{payload['record_rows_written']}")
    if not payload['committed']:
        print(f"预计写入：{payload.get('projected_record_rows', 0)} 行")
    if payload.get('blocking_issues'):
        print('硬阻断：')
        for issue in payload['blocking_issues']:
            print(f"- [{issue.get('code')}] {issue.get('message')}")


def main() -> int:
    parser = argparse.ArgumentParser(description='每日能耗真实报表只读 dry-run 对账')
    parser.add_argument('--electricity-file', help='各车间能耗统计表 xls/xlsx 文件')
    parser.add_argument('--gas-file', help='各车间天然气用量统计表 xls/xlsx 文件')
    parser.add_argument('--report-date', type=_parse_date, help='锁定报告日，格式 YYYY-MM-DD')
    parser.add_argument('--write-staging', action='store_true', help='写入导入暂存表；硬门禁失败会回滚')
    parser.add_argument('--promote-records', action='store_true', help='将已通过门禁的暂存批次写入正式能耗记录表')
    parser.add_argument('--batch-id', type=int, default=None, help='--promote-records 使用的 ImportBatch id')
    parser.add_argument('--json', dest='json_mode', action='store_true', help='输出完整 JSON')
    args = parser.parse_args()

    if args.promote_records:
        if args.batch_id is None:
            parser.error('--promote-records requires --batch-id')
        SessionLocal = get_sessionmaker()
        with SessionLocal() as db:
            payload = promote_daily_energy_batch(db, batch_id=args.batch_id, commit=True)
        if args.json_mode:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        else:
            _print_promotion_text(payload)
        return 0 if payload['committed'] else 1

    if args.report_date is None or (not args.electricity_file and not args.gas_file):
        parser.error('--report-date and at least one input file are required unless --promote-records is used')

    if args.write_staging:
        SessionLocal = get_sessionmaker()
        with SessionLocal() as db:
            payload = stage_daily_energy_import(
                electricity_file=args.electricity_file,
                gas_file=args.gas_file,
                report_date=args.report_date,
                db=db,
                commit=True,
            )
    else:
        payload = build_daily_energy_dry_run(
            electricity_file=args.electricity_file,
            gas_file=args.gas_file,
            report_date=args.report_date,
        )
    if args.json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0 if payload['hard_gate_passed'] else 2


if __name__ == '__main__':
    sys.exit(main())
