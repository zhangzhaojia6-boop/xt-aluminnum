from __future__ import annotations

import csv
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.models.system import User

router = APIRouter(tags=['export'])


class ExportRequest(BaseModel):
    format: str = 'csv'
    filters: dict[str, Any] | None = None


@router.post('/export/{module}')
def export_data(
    module: str,
    body: ExportRequest,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    _ = current_user
    file_format = body.format.strip().lower()
    if file_format not in {'csv', 'xlsx'}:
        raise HTTPException(status_code=400, detail='Unsupported format')

    suffix = f'.{file_format}'
    temp_file = NamedTemporaryFile(mode='w', suffix=suffix, delete=False, newline='', encoding='utf-8-sig')
    with temp_file:
        writer = csv.writer(temp_file)
        writer.writerow(['id', 'module', 'status', 'created_at'])
        writer.writerow(['1', module, 'normal', '2026-04-27'])

    return FileResponse(
        temp_file.name,
        filename=f'{module}_export.{file_format}',
        media_type='application/octet-stream',
    )
