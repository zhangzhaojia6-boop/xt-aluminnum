from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.schemas.quality import DataQualityIssueOut, QualityCheckRequest, QualityIssueActionRequest
from app.services import quality_service

router = APIRouter(tags=['quality'])


@router.post('/run-checks', response_model=list[DataQualityIssueOut])
def run_quality_checks(
    body: QualityCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DataQualityIssueOut]:
    items = quality_service.run_quality_checks(db, business_date=body.business_date, operator=current_user)
    return [DataQualityIssueOut.model_validate(item) for item in items]


@router.get('/issues', response_model=list[DataQualityIssueOut])
def list_quality_issues(
    business_date: date | None = None,
    issue_type: str | None = None,
    issue_level: str | None = None,
    status: str | None = None,
    issue_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DataQualityIssueOut]:
    _ = current_user
    items = quality_service.list_issues(
        db,
        business_date=business_date,
        issue_type=issue_type,
        issue_level=issue_level,
        status=status,
        issue_id=issue_id,
    )
    return [DataQualityIssueOut.model_validate(item) for item in items]


@router.post('/issues/{issue_id}/resolve', response_model=DataQualityIssueOut)
def resolve_issue(
    issue_id: int,
    body: QualityIssueActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataQualityIssueOut:
    try:
        issue = quality_service.resolve_issue(db, issue_id=issue_id, operator=current_user, note=body.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DataQualityIssueOut.model_validate(issue)


@router.post('/issues/{issue_id}/ignore', response_model=DataQualityIssueOut)
def ignore_issue(
    issue_id: int,
    body: QualityIssueActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataQualityIssueOut:
    try:
        issue = quality_service.ignore_issue(db, issue_id=issue_id, operator=current_user, note=body.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DataQualityIssueOut.model_validate(issue)
