from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar('T')


class StandardResponse(BaseModel):
    success: bool
    data: Any = None
    message: str = ''
    total: int | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    skip: int
    limit: int


class PageResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


PRODUCTION_DATA_STATUSES = ['pending', 'reviewed', 'confirmed', 'rejected', 'voided']
REPORT_STATUSES = ['draft', 'reviewed', 'published']


def ok(data: Any = None, message: str = 'ok', total: int | None = None) -> dict:
    return {'success': True, 'data': data, 'message': message, 'total': total}


def fail(message: str = 'failed', data: Any = None) -> dict:
    return {'success': False, 'data': data, 'message': message, 'total': None}
