from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.master import Workshop
from app.models.rag import RagChunk, RagDocument, RagEmbedding, RagQueryLog, RagSourceIngestion
from app.models.system import User
from app.services import hermes_rag_service
from app.services.rag_service import query_knowledge


TABLES = [
    User.__table__,
    Workshop.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
    RagEmbedding.__table__,
    RagSourceIngestion.__table__,
]


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rag-mes-route.db'}", future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    return Session(engine)


def test_ingest_mes_route_catalog_answers_packaging_source(tmp_path) -> None:
    db = _session(tmp_path)
    try:
        document = hermes_rag_service.ingest_mes_route_catalog(db)
        assert document.status == 'active'
        assert db.query(RagSourceIngestion).one().source_type == 'mes_schema'

        payload = query_knowledge(db, query='包装产量来自哪里 WMS_InStock InStockDate', limit=5)
        answer = payload['answer']
        assert 'WMS_InStock' in answer
        assert 'InStockDate' in answer
        assert 'mes-sql-route-catalog.md' in answer
    finally:
        db.close()


def test_ingest_mes_page_knowledge_is_limited_to_mes_host(tmp_path) -> None:
    db = _session(tmp_path)
    try:
        document = hermes_rag_service.ingest_mes_page_knowledge(
            db,
            url='https://mes.xintaily.com/#/today',
            page_title='MES 首页',
            fields=['包装入库', '发货'],
        )
        assert document.status == 'active'
        assert 'mes.xintaily.com' in document.metadata_payload['source_url']
    finally:
        db.close()


def test_ingest_mes_page_rejects_non_mes_host(tmp_path) -> None:
    db = _session(tmp_path)
    try:
        try:
            hermes_rag_service.ingest_mes_page_knowledge(db, url='https://example.com')
        except hermes_rag_service.HermesRagError as exc:
            assert str(exc) == 'mes_page_url_not_allowed'
        else:
            raise AssertionError('expected mes page host rejection')
    finally:
        db.close()
