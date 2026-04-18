from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.imports import ImportBatch
from app.models.system import User


class _FakeQuery:
    def __init__(self, items):
        self._items = list(items)
        self._skip = 0
        self._limit = None

    def order_by(self, *_args):
        return self

    def count(self):
        return len(self._items)

    def offset(self, skip: int):
        self._skip = skip
        return self

    def limit(self, limit: int):
        self._limit = limit
        return self

    def all(self):
        items = self._items[self._skip :]
        if self._limit is not None:
            items = items[: self._limit]
        return items


class _FakeDB:
    def __init__(self, mapping):
        self._mapping = mapping

    def query(self, model):
        return _FakeQuery(self._mapping[model])


def test_import_history_returns_paginated_payload() -> None:
    batches = [
        SimpleNamespace(
            id=index,
            batch_no=f'BATCH-{index}',
            import_type='production_shift',
            template_code=None,
            mapping_template_code=None,
            source_type=None,
            file_name=f'file-{index}.xlsx',
            file_size=1024,
            file_path=f'/tmp/file-{index}.xlsx',
            total_rows=10,
            success_rows=10,
            failed_rows=0,
            skipped_rows=0,
            status='completed',
            quality_status=None,
            parsed_successfully=True,
            error_summary=None,
            imported_by=1,
            created_at='2026-03-28T10:00:00Z',
            completed_at='2026-03-28T10:05:00Z',
        )
        for index in range(1, 4)
    ]

    def fake_get_db():
        yield _FakeDB({ImportBatch: batches})

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    client = TestClient(app)
    response = client.get('/api/v1/imports/history?skip=1&limit=1')

    assert response.status_code == 200
    payload = response.json()
    assert payload['total'] == 3
    assert payload['skip'] == 1
    assert payload['limit'] == 1
    assert len(payload['items']) == 1
    assert payload['items'][0]['batch_no'] == 'BATCH-2'

    app.dependency_overrides.clear()
