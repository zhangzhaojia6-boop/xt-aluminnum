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


def test_rag_upload_rejects_malformed_json_file() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/rag/documents/upload',
            files={
                'file': (
                    '字段映射.json',
                    BytesIO('{"workshop": "冷轧1650",'.encode('utf-8')),
                    'application/json',
                )
            },
        )

        assert response.status_code == 400
        assert 'JSON' in response.json()['detail']
        assert db.query(RagDocument).count() == 0
        assert db.query(RagChunk).count() == 0
    finally:
        _restore_overrides(previous_overrides, db)


def test_rag_delete_soft_disables_document_and_excludes_it_from_query() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/rag/documents/upload',
            files={'file': ('停机规则.txt', BytesIO(('停机规则 维修闭环。' * 80).encode('utf-8')), 'text/plain')},
        )
        assert response.status_code == 200
        document_id = response.json()['id']

        delete_response = client.delete(f'/api/v1/rag/documents/{document_id}')
        assert delete_response.status_code == 200
        assert delete_response.json() == {'deleted': True, 'id': document_id}

        stored_document = db.get(RagDocument, document_id)
        assert stored_document is not None
        assert stored_document.status == 'deleted'
        assert db.query(RagChunk).filter(RagChunk.document_id == document_id).count() > 0

        list_response = client.get('/api/v1/rag/documents')
        assert list_response.status_code == 200
        assert list_response.json()['total'] == 0

        detail_response = client.get(f'/api/v1/rag/documents/{document_id}')
        assert detail_response.status_code == 404

        query_response = client.post('/api/v1/rag/query', json={'query': '停机规则 维修闭环', 'limit': 3})
        assert query_response.status_code == 200
        query_payload = query_response.json()
        assert query_payload['items'] == []
        assert query_payload['citations'] == []
        assert query_payload['answer'].startswith('数据不足')
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


def test_rag_upload_rejects_renamed_executable_content() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/rag/documents/upload',
            files={
                'file': (
                    'tool.txt',
                    BytesIO(b'MZ' + b'This looks like text but keeps a Windows executable header.' * 20),
                    'text/plain',
                )
            },
        )

        assert response.status_code == 400
        assert '可执行' in response.json()['detail']
        assert db.query(RagDocument).count() == 0
        assert db.query(RagChunk).count() == 0
    finally:
        _restore_overrides(previous_overrides, db)


def test_rag_upload_rejects_authorization_bearer_text() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/rag/documents/upload',
            files={
                'file': (
                    '接口调试记录.md',
                    BytesIO('调用头：Authorization: Bearer fake-token-0012'.encode('utf-8')),
                    'text/markdown',
                )
            },
        )

        assert response.status_code == 400
        assert '敏感' in response.json()['detail']
        assert db.query(RagDocument).count() == 0
        assert db.query(RagChunk).count() == 0
    finally:
        _restore_overrides(previous_overrides, db)


def test_rag_upload_rejects_pem_private_key_text() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/rag/documents/upload',
            files={
                'file': (
                    'private-key.txt',
                    BytesIO(
                        (
                            '-----BEGIN PRIVATE KEY-----\n'
                            'fake-private-key-body\n'
                            '-----END PRIVATE KEY-----\n'
                        ).encode('utf-8')
                    ),
                    'text/plain',
                )
            },
        )

        assert response.status_code == 400
        assert '敏感' in response.json()['detail']
        assert db.query(RagDocument).count() == 0
        assert db.query(RagChunk).count() == 0
    finally:
        _restore_overrides(previous_overrides, db)


def test_rag_query_log_redacts_secret_style_query_text() -> None:
    db, previous_overrides = _install_overrides()

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/rag/query',
            json={'query': 'server=db;uid=readonly;password=secret-pass;token=abc123', 'limit': 3},
        )

        assert response.status_code == 200
        log = db.query(RagQueryLog).one()
        assert 'readonly' not in log.query_text
        assert 'secret-pass' not in log.query_text
        assert 'abc123' not in log.query_text
        assert 'uid=<redacted>' in log.query_text
        assert 'password=<redacted>' in log.query_text
        assert 'token=<redacted>' in log.query_text
    finally:
        _restore_overrides(previous_overrides, db)


def test_rag_query_redacts_sensitive_text_from_returned_answer() -> None:
    db, previous_overrides = _install_overrides()

    try:
        document = RagDocument(
            filename='历史脏资料.md',
            source_name='历史脏资料.md',
            content_type='text/markdown',
            encoding='utf-8',
            status='active',
            file_size=80,
            chunk_count=1,
        )
        db.add(document)
        db.flush()
        db.add(
            RagChunk(
                document_id=document.id,
                chunk_index=0,
                content='维修资料：server=db;uid=readonly;password=dirty-pass;token=dirty-token',
                char_start=0,
                char_end=80,
                source_ref='历史脏资料.md#chunk-1',
            )
        )
        db.commit()

        client = TestClient(app)
        response = client.post('/api/v1/rag/query', json={'query': '维修资料', 'limit': 3})

        assert response.status_code == 200
        payload = response.json()
        assert 'dirty-pass' not in payload['answer']
        assert 'dirty-token' not in payload['answer']
        assert 'password=<redacted>' in payload['answer']
        assert 'token=<redacted>' in payload['answer']
        assert 'dirty-pass' not in payload['items'][0]['snippet']
        assert 'dirty-token' not in payload['items'][0]['snippet']
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
