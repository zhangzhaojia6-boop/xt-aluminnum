from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base
from app.models.master import Workshop
from app.models.rag import RagChunk, RagDocument, RagEmbedding, RagQueryLog
from app.models.system import User
from app.services import rag_embedding_service
from app.services.rag_service import create_document_from_bytes, query_knowledge


RAG_EMBEDDING_TABLES = [
    User.__table__,
    Workshop.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
    RagEmbedding.__table__,
]


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rag-embedding.db'}", future=True)
    Base.metadata.create_all(engine, tables=RAG_EMBEDDING_TABLES)
    return Session(engine)


def test_rag_embedding_disabled_keeps_keyword_search_available(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, 'RAG_EMBEDDING_PROVIDER', 'null', raising=False)
    db = _session(tmp_path)
    try:
        create_document_from_bytes(
            db,
            filename='日报口径.md',
            content='包装产量来自 WMS_InStock 表头 TotalNetWeight。'.encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
        )
        payload = query_knowledge(db, query='包装产量 WMS_InStock', limit=3)
        assert payload['items']
        assert db.query(RagEmbedding).count() == 0
    finally:
        db.close()


def test_rag_embedding_indexes_chunks_and_query_uses_vectors(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, 'RAG_EMBEDDING_PROVIDER', 'local_tei', raising=False)
    monkeypatch.setattr(settings, 'RAG_EMBEDDING_API_BASE', None, raising=False)
    db = _session(tmp_path)
    try:
        document = create_document_from_bytes(
            db,
            filename='mes路线.md',
            content='包装产量 总产量 成品入库 主口径 WMS_InStock InStockDate TotalNetWeight。'.encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
        )
        assert rag_embedding_service.index_document_embeddings(db, document) >= 1
        payload = query_knowledge(db, query='包装产量来源', limit=3)
        assert payload['items']
        assert payload['items'][0]['score'] > 0
        assert db.query(RagEmbedding).count() >= 1
    finally:
        db.close()
