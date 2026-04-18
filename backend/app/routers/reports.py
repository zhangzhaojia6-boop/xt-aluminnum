from __future__ import annotations

from datetime import date, datetime

import csv
import json
from io import BytesIO, StringIO

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.schemas.reports import (
    DailyReportOut,
    ReportActionRequest,
    ReportFinalizeRequest,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportPipelineRequest,
    ReportPipelineResponse,
)
from app.services import report_service

router = APIRouter(tags=['reports'])


@router.post('/generate', response_model=ReportGenerateResponse)
def generate_report(
    body: ReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportGenerateResponse:
    try:
        entities = report_service.generate_daily_reports(
            db,
            report_date=body.report_date,
            report_type=body.report_type,
            scope=body.scope,
            output_mode=body.output_mode,
            operator=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ReportGenerateResponse(
        reports=[DailyReportOut.model_validate(item) for item in entities],
        count=len(entities),
    )


@router.get('', response_model=list[DailyReportOut])
def list_daily_reports(
    start_date: date | None = None,
    end_date: date | None = None,
    report_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DailyReportOut]:
    _ = current_user
    rows = report_service.list_reports(
        db,
        start_date=start_date,
        end_date=end_date,
        report_type=report_type,
        status=status,
    )
    return [DailyReportOut.model_validate(item) for item in rows]


@router.get('/{report_id}', response_model=DailyReportOut)
def report_detail(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyReportOut:
    _ = current_user
    entity = report_service.get_report(db, report_id=report_id)
    if entity is None:
        raise HTTPException(status_code=404, detail='report not found')
    return DailyReportOut.model_validate(entity)


@router.post('/{report_id}/review', response_model=DailyReportOut)
def review_report(
    report_id: int,
    body: ReportActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyReportOut:
    try:
        entity = report_service.review_report(
            db,
            report_id=report_id,
            operator=current_user,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DailyReportOut.model_validate(entity)


@router.post('/{report_id}/publish', response_model=DailyReportOut)
def publish_report(
    report_id: int,
    body: ReportActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyReportOut:
    try:
        entity = report_service.publish_report(
            db,
            report_id=report_id,
            operator=current_user,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DailyReportOut.model_validate(entity)


@router.post('/run-daily-pipeline', response_model=ReportPipelineResponse)
def run_daily_pipeline(
    body: ReportPipelineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportPipelineResponse:
    blocked, message, open_count, is_final_version, boss_text, reports = report_service.run_daily_pipeline(
        db,
        report_date=body.report_date,
        scope=body.scope,
        output_mode=body.output_mode,
        force=body.force,
        operator=current_user,
    )
    return ReportPipelineResponse(
        blocked=blocked,
        message=message,
        open_reconciliation_count=open_count,
        is_final_version=is_final_version,
        boss_text_summary=boss_text,
        reports=[DailyReportOut.model_validate(item) for item in reports],
    )


@router.post('/{report_id}/finalize', response_model=DailyReportOut)
def finalize_report(
    report_id: int,
    body: ReportFinalizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyReportOut:
    try:
        entity = report_service.finalize_report(
            db,
            report_id=report_id,
            operator=current_user,
            note=body.note,
            force=body.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DailyReportOut.model_validate(entity)


@router.get('/{report_id}/export')
def export_report(
    report_id: int,
    format: str = 'json',
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    _ = current_user
    entity = report_service.get_report(db, report_id=report_id)
    if entity is None:
        raise HTTPException(status_code=404, detail='report not found')

    payload = DailyReportOut.model_validate(entity).model_dump()
    if format == 'json':
        content = json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8')
        headers = {'Content-Disposition': f'attachment; filename=report_{report_id}.json'}
        return Response(content=content, media_type='application/json', headers=headers)

    if format == 'csv':
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['field', 'value'])
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, default=str)
            writer.writerow([key, value])
        headers = {'Content-Disposition': f'attachment; filename=report_{report_id}.csv'}
        return Response(content=buffer.getvalue().encode('utf-8-sig'), media_type='text/csv', headers=headers)

    if format == 'xlsx':
        try:
            import pandas as pd
        except ImportError as exc:
            raise HTTPException(status_code=400, detail=f'xlsx export not available: {exc}') from exc
        rows = []
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, default=str)
            elif isinstance(value, (date, datetime)):
                value = value.isoformat()
            rows.append({'field': key, 'value': value})
        df = pd.DataFrame(rows)
        output = BytesIO()
        df.to_excel(output, index=False)
        headers = {'Content-Disposition': f'attachment; filename=report_{report_id}.xlsx'}
        return Response(content=output.getvalue(), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)

    raise HTTPException(status_code=400, detail='format must be json/csv/xlsx')
