from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary
from app.models.system import User
from app.services.rag_service import (
    RagValidationError,
    create_document_from_bytes,
    delete_document,
    get_document_detail,
    list_documents,
    query_knowledge,
    serialize_chunk,
    serialize_document,
)

router = APIRouter(tags=['rag'])


class RagQueryRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=10)


def _ensure_rag_access(user: User) -> None:
    scope = build_scope_summary(user)
    if not (scope.is_admin or scope.is_manager or scope.is_reviewer):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='RAG access denied')


@router.post('/documents/upload')
async def upload_rag_document(
    file: UploadFile = File(...),
    source_name: str | None = Form(default=None),
    version: str | None = Form(default=None),
    workshop: str | None = Form(default=None),
    owner: str | None = Form(default=None),
    effective_date: str | None = Form(default=None),
    permission_scope: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_rag_access(current_user)
    content = await file.read()
    try:
        document = create_document_from_bytes(
            db,
            filename=file.filename or '',
            content=content,
            content_type=file.content_type,
            uploaded_by=current_user,
            source_name=source_name,
            metadata={
                'version': version,
                'workshop': workshop,
                'owner': owner,
                'effective_date': effective_date,
            },
            scope={'permission_scope': permission_scope},
        )
        db.commit()
    except RagValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    return serialize_document(document)


@router.get('/documents')
def get_rag_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_rag_access(current_user)
    items = [serialize_document(document) for document in list_documents(db)]
    return {'items': items, 'total': len(items)}


@router.get('/documents/{document_id}')
def get_rag_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_rag_access(current_user)
    detail = get_document_detail(db, document_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='RAG document not found')
    return {
        'document': serialize_document(detail['document']),
        'chunks': [serialize_chunk(chunk) for chunk in detail['chunks']],
    }


@router.delete('/documents/{document_id}')
def remove_rag_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_rag_access(current_user)
    if not delete_document(db, document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='RAG document not found')
    db.commit()
    return {'deleted': True, 'id': document_id}


@router.post('/query')
def query_rag(
    body: RagQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_rag_access(current_user)
    payload = query_knowledge(db, query=body.query, limit=body.limit, user=current_user)
    db.commit()
    return payload
