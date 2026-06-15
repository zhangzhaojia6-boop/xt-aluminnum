from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.rag import RagChunk, RagDocument, RagQueryLog
from app.models.system import User


RAG_TABLES = [
    User.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
]


def _install_overrides(*, role: str = 'admin'):
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=RAG_TABLES)
    db = Session(engine)

    def fake_get_db():
        yield db

    def fake_get_user() -> User:
        return User(id=1, username=role, password_hash='x', name='User', role=role, is_active=True)

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    return db, previous_overrides


def _restore_overrides(previous_overrides, db: Session) -> None:
    db.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def test_rag_upload_chunks_and_query_returns_sources() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/rag/documents/upload',
            files={'file': ('工艺规则.md', BytesIO(('冷轧1650 工艺规则。' * 80).encode('utf-8')), 'text/markdown')},
        )
        assert response.status_code == 200
        uploaded = response.json()
        assert uploaded['filename'] == '工艺规则.md'
        assert uploaded['encoding'] == 'utf-8'
        assert uploaded['chunk_count'] >= 2

        list_response = client.get('/api/v1/rag/documents')
        assert list_response.status_code == 200
        assert list_response.json()['items'][0]['filename'] == '工艺规则.md'

        query_response = client.post('/api/v1/rag/query', json={'query': '冷轧1650 工艺规则', 'limit': 3})
        assert query_response.status_code == 200
        payload = query_response.json()
        assert payload['answer'].startswith('根据知识库资料')
        assert '来源：工艺规则.md#chunk-' in payload['answer']
        assert payload['citations'][0]['document_id'] == uploaded['id']
        assert payload['citations'][0]['filename'] == '工艺规则.md'
    finally:
        _restore_overrides(previous_overrides, db)


def test_rag_upload_accepts_gbk_text() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/rag/documents/upload',
            files={'file': ('设备说明.txt', BytesIO('退火炉 点检标准'.encode('gbk')), 'text/plain')},
        )
        assert response.status_code == 200
        assert response.json()['encoding'] == 'gbk'
    finally:
        _restore_overrides(previous_overrides, db)


def test_rag_upload_rejects_executable_and_secret_like_files() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        executable_response = client.post(
            '/api/v1/rag/documents/upload',
            files={'file': ('tool.exe', BytesIO(b'MZ\x00\x00'), 'application/octet-stream')},
        )
        assert executable_response.status_code == 400
        assert '不支持' in executable_response.json()['detail']

        secret_response = client.post(
            '/api/v1/rag/documents/upload',
            files={'file': ('secret.log', BytesIO(b'DATABASE_PASSWORD=plain-text'), 'text/plain')},
        )
        assert secret_response.status_code == 400
        assert '敏感' in secret_response.json()['detail']
    finally:
        _restore_overrides(previous_overrides, db)


def test_rag_routes_require_manage_permission() -> None:
    db, previous_overrides = _install_overrides(role='machine_operator')

    try:
        client = TestClient(app)
        response = client.get('/api/v1/rag/documents')
        assert response.status_code == 403
        assert response.json()['detail'] == 'RAG access denied'
    finally:
        _restore_overrides(previous_overrides, db)
