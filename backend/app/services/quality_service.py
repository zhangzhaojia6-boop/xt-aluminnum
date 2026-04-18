from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceResult
from app.models.energy import EnergyImportRecord
from app.models.master import Workshop
from app.models.mes import MesImportRecord
from app.models.production import ShiftProductionData
from app.models.shift import ShiftConfig
from app.models.quality import DataQualityIssue
from app.models.reports import DailyReport
from app.models.system import User
from app.services import master_service, reconciliation_service
from app.services.audit_service import record_audit


ISSUE_LEVEL_BLOCKER = 'blocker'
ISSUE_LEVEL_WARNING = 'warning'


def list_issues(
    db: Session,
    *,
    business_date: date | None = None,
    issue_type: str | None = None,
    issue_level: str | None = None,
    status: str | None = None,
    issue_id: int | None = None,
) -> list[DataQualityIssue]:
    query = db.query(DataQualityIssue)
    if issue_id:
        query = query.filter(DataQualityIssue.id == issue_id)
    if business_date:
        query = query.filter(DataQualityIssue.business_date == business_date)
    if issue_type:
        query = query.filter(DataQualityIssue.issue_type == issue_type)
    if issue_level:
        query = query.filter(DataQualityIssue.issue_level == issue_level)
    if status:
        query = query.filter(DataQualityIssue.status == status)
    return query.order_by(DataQualityIssue.business_date.desc(), DataQualityIssue.id.desc()).all()


def count_open_issues(db: Session, *, business_date: date) -> int:
    return int(
        db.query(func.count(DataQualityIssue.id))
        .filter(DataQualityIssue.business_date == business_date, DataQualityIssue.status == 'open')
        .scalar()
        or 0
    )


def count_open_blockers(db: Session, *, business_date: date) -> int:
    return int(
        db.query(func.count(DataQualityIssue.id))
        .filter(
            DataQualityIssue.business_date == business_date,
            DataQualityIssue.status == 'open',
            DataQualityIssue.issue_level == ISSUE_LEVEL_BLOCKER,
        )
        .scalar()
        or 0
    )


def blocker_summary(db: Session, *, business_date: date, limit: int = 5) -> str | None:
    rows = (
        db.query(DataQualityIssue)
        .filter(
            DataQualityIssue.business_date == business_date,
            DataQualityIssue.status == 'open',
            DataQualityIssue.issue_level == ISSUE_LEVEL_BLOCKER,
        )
        .order_by(DataQualityIssue.id.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return None
    return '；'.join(item.issue_desc for item in rows)


def _add_issue(
    db: Session,
    *,
    business_date: date,
    issue_type: str,
    source_type: str | None,
    dimension_key: str | None,
    field_name: str | None,
    issue_level: str,
    issue_desc: str,
) -> DataQualityIssue:
    issue = DataQualityIssue(
        business_date=business_date,
        issue_type=issue_type,
        source_type=source_type,
        dimension_key=dimension_key,
        field_name=field_name,
        issue_level=issue_level,
        issue_desc=issue_desc,
        status='open',
    )
    db.add(issue)
    return issue


def _clear_open_issues(db: Session, *, business_date: date) -> None:
    db.query(DataQualityIssue).filter(
        DataQualityIssue.business_date == business_date, DataQualityIssue.status == 'open'
    ).delete()


def run_quality_checks(
    db: Session,
    *,
    business_date: date,
    operator: User | None,
) -> list[DataQualityIssue]:
    _clear_open_issues(db, business_date=business_date)
    created: list[DataQualityIssue] = []

    energy_rows = db.query(EnergyImportRecord).filter(EnergyImportRecord.business_date == business_date).all()
    for row in energy_rows:
        if row.workshop_code and not master_service.is_valid_code(db, entity_type='workshop', code=row.workshop_code):
            created.append(
                _add_issue(
                    db,
                    business_date=business_date,
                    issue_type='master_mapping',
                    source_type='energy',
                    dimension_key=f'workshop:{row.workshop_code}|shift:{row.shift_code}',
                    field_name='workshop_code',
                    issue_level=ISSUE_LEVEL_BLOCKER,
                    issue_desc=f'能耗导入车间编码未匹配: {row.workshop_code}',
                )
            )
        if row.shift_code and not master_service.is_valid_code(db, entity_type='shift', code=row.shift_code):
            created.append(
                _add_issue(
                    db,
                    business_date=business_date,
                    issue_type='master_mapping',
                    source_type='energy',
                    dimension_key=f'workshop:{row.workshop_code}|shift:{row.shift_code}',
                    field_name='shift_code',
                    issue_level=ISSUE_LEVEL_BLOCKER,
                    issue_desc=f'能耗导入班次编码未匹配: {row.shift_code}',
                )
            )

    mes_rows = db.query(MesImportRecord).filter(MesImportRecord.business_date == business_date).all()
    for row in mes_rows:
        if row.workshop_code and not master_service.is_valid_code(db, entity_type='workshop', code=row.workshop_code):
            created.append(
                _add_issue(
                    db,
                    business_date=business_date,
                    issue_type='master_mapping',
                    source_type='mes_export',
                    dimension_key=f'workshop:{row.workshop_code}|shift:{row.shift_code}',
                    field_name='workshop_code',
                    issue_level=ISSUE_LEVEL_BLOCKER,
                    issue_desc=f'MES车间编码未匹配: {row.workshop_code}',
                )
            )
        if row.shift_code and not master_service.is_valid_code(db, entity_type='shift', code=row.shift_code):
            created.append(
                _add_issue(
                    db,
                    business_date=business_date,
                    issue_type='master_mapping',
                    source_type='mes_export',
                    dimension_key=f'workshop:{row.workshop_code}|shift:{row.shift_code}',
                    field_name='shift_code',
                    issue_level=ISSUE_LEVEL_BLOCKER,
                    issue_desc=f'MES班次编码未匹配: {row.shift_code}',
                )
            )

    production_count = int(
        db.query(func.count(ShiftProductionData.id))
        .filter(ShiftProductionData.business_date == business_date)
        .scalar()
        or 0
    )
    if production_count == 0:
        created.append(
            _add_issue(
                db,
                business_date=business_date,
                issue_type='missing_data',
                source_type='production',
                dimension_key='production',
                field_name='output_weight',
                issue_level=ISSUE_LEVEL_BLOCKER,
                issue_desc='当日未导入生产班次数据',
            )
        )

    attendance_count = int(
        db.query(func.count(AttendanceResult.id))
        .filter(AttendanceResult.business_date == business_date)
        .scalar()
        or 0
    )
    if attendance_count == 0:
        created.append(
            _add_issue(
                db,
                business_date=business_date,
                issue_type='missing_data',
                source_type='attendance',
                dimension_key='attendance',
                field_name='attendance',
                issue_level=ISSUE_LEVEL_BLOCKER,
                issue_desc='当日未生成考勤结果',
            )
        )

    if not energy_rows:
        created.append(
            _add_issue(
                db,
                business_date=business_date,
                issue_type='missing_data',
                source_type='energy',
                dimension_key='energy',
                field_name='energy_value',
                issue_level=ISSUE_LEVEL_BLOCKER,
                issue_desc='当日未导入能耗数据',
            )
        )

    open_reconciliation = reconciliation_service.count_open_items(db, business_date=business_date)
    if open_reconciliation > 0:
        created.append(
            _add_issue(
                db,
                business_date=business_date,
                issue_type='unreconciled',
                source_type='reconciliation',
                dimension_key='reconciliation',
                field_name='status',
                issue_level=ISSUE_LEVEL_BLOCKER,
                issue_desc=f'仍有 {open_reconciliation} 条差异未处理',
            )
        )

    report = (
        db.query(DailyReport)
        .filter(DailyReport.report_date == business_date, DailyReport.report_type == 'production')
        .first()
    )
    if report and (not report.report_data or report.report_data.get('total_output_weight') in {None, 0}):
        created.append(
            _add_issue(
                db,
                business_date=business_date,
                issue_type='publish_blocker',
                source_type='reports',
                dimension_key='report:production',
                field_name='total_output_weight',
                issue_level=ISSUE_LEVEL_BLOCKER,
                issue_desc='生产日报已生成但产量为空',
            )
        )

    # energy vs output weight check
    if energy_rows:
        energy_totals = (
            db.query(
                EnergyImportRecord.workshop_code,
                EnergyImportRecord.shift_code,
                func.sum(EnergyImportRecord.energy_value).label('energy_total'),
            )
            .filter(EnergyImportRecord.business_date == business_date)
            .group_by(EnergyImportRecord.workshop_code, EnergyImportRecord.shift_code)
            .all()
        )
        for workshop_code, shift_code, energy_total in energy_totals:
            if not workshop_code or not shift_code:
                continue
            energy_total_val = float(energy_total or 0)
            if energy_total_val <= 0:
                continue
            output_weight = float(
                db.query(func.sum(ShiftProductionData.output_weight))
                .filter(
                    ShiftProductionData.business_date == business_date,
                    ShiftProductionData.data_status != 'voided',
                )
                .filter(ShiftProductionData.workshop_id.in_(
                    db.query(Workshop.id).filter(Workshop.code == workshop_code)
                ))
                .filter(ShiftProductionData.shift_config_id.in_(
                    db.query(ShiftConfig.id).filter(ShiftConfig.code == shift_code)
                ))
                .scalar()
                or 0
            )
            if output_weight <= 0:
                created.append(
                    _add_issue(
                        db,
                        business_date=business_date,
                        issue_type='invalid_value',
                        source_type='energy',
                        dimension_key=f'workshop:{workshop_code}|shift:{shift_code}',
                        field_name='output_weight',
                        issue_level=ISSUE_LEVEL_BLOCKER,
                        issue_desc=f'存在能耗记录但产量为0: {workshop_code}/{shift_code}',
                    )
                )

    db.commit()
    for item in created:
        db.refresh(item)

    record_audit(
        db,
        user=operator,
        action='run_quality_checks',
        module='quality',
        entity_type='data_quality_issues',
        entity_id=created[0].id if created else None,
        detail={'business_date': business_date.isoformat(), 'count': len(created)},
    )
    return created


def resolve_issue(
    db: Session,
    *,
    issue_id: int,
    operator: User,
    note: str | None = None,
) -> DataQualityIssue:
    issue = db.get(DataQualityIssue, issue_id)
    if issue is None:
        raise ValueError('quality issue not found')
    issue.status = 'resolved'
    issue.resolved_by = operator.id
    issue.resolved_at = datetime.utcnow()
    issue.resolve_note = note
    db.flush()
    record_audit(
        db,
        user=operator,
        action='quality_resolve',
        module='quality',
        entity_type='data_quality_issues',
        entity_id=issue.id,
        detail={'status': issue.status, 'note': note},
        reason=note,
        auto_commit=False,
    )
    db.commit()
    db.refresh(issue)
    return issue


def ignore_issue(
    db: Session,
    *,
    issue_id: int,
    operator: User,
    note: str | None = None,
) -> DataQualityIssue:
    issue = db.get(DataQualityIssue, issue_id)
    if issue is None:
        raise ValueError('quality issue not found')
    issue.status = 'ignored'
    issue.resolved_by = operator.id
    issue.resolved_at = datetime.utcnow()
    issue.resolve_note = note
    db.flush()
    record_audit(
        db,
        user=operator,
        action='quality_ignore',
        module='quality',
        entity_type='data_quality_issues',
        entity_id=issue.id,
        detail={'status': issue.status, 'note': note},
        reason=note,
        auto_commit=False,
    )
    db.commit()
    db.refresh(issue)
    return issue
