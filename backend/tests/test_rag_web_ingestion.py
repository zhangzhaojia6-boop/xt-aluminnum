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


class _Response:
    text = '<html><body>铝加工冷轧缺陷：辊印、划伤需要结合轧辊和张力排查。</body></html>'

    def raise_for_status(self) -> None:
        return None


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rag-web.db'}", future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    return Session(engine)


def test_ingest_web_source_requires_allowlist_and_stays_pending_review(tmp_path, monkeypatch) -> None:
    db = _session(tmp_path)
    monkeypatch.setattr('app.services.hermes_rag_service.httpx.get', lambda *_args, **_kwargs: _Response())
    try:
        document = hermes_rag_service.ingest_web_source(
            db,
            url='https://www.aluminum.org/rolling-aluminum-mine-mill',
        )
        assert document.status == 'pending_review'
        assert document.metadata_payload['source_type'] == 'external_industry_knowledge'

        payload = query_knowledge(db, query='冷轧缺陷 辊印', limit=3)
        assert payload['items'] == []
        assert db.query(RagSourceIngestion).one().status == 'pending_review'
    finally:
        db.close()


def test_ingest_web_source_rejects_unknown_host(tmp_path) -> None:
    db = _session(tmp_path)
    try:
        try:
            hermes_rag_service.ingest_web_source(db, url='https://unknown.example.com/aluminum')
        except hermes_rag_service.HermesRagError as exc:
            assert str(exc) == 'web_url_not_allowed'
        else:
            raise AssertionError('expected web allowlist rejection')
    finally:
        db.close()
