from __future__ import annotations

import hashlib
import math
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.core.redaction import redact_secret_text
from app.models.rag import RagChunk, RagDocument, RagEmbedding


class RagEmbeddingError(RuntimeError):
    pass


def embedding_provider() -> str:
    return settings.rag_embedding_provider_normalized


def embedding_model() -> str | None:
    return str(settings.RAG_EMBEDDING_MODEL or '').strip() or None


def embedding_enabled() -> bool:
    return embedding_provider() in {'local_tei', 'hf_endpoint'}


def embed_text(text: str) -> list[float] | None:
    if not embedding_enabled():
        return None
    clean_text = str(text or '').strip()
    if not clean_text:
        return None
    if settings.RAG_EMBEDDING_API_BASE:
        return _remote_embedding(clean_text)
    return _stable_local_embedding(clean_text)


def index_document_embeddings(db: Session, document: RagDocument) -> int:
    if not embedding_enabled():
        return 0
    chunks = (
        db.query(RagChunk)
        .filter(RagChunk.document_id == document.id)
        .order_by(RagChunk.chunk_index.asc())
        .all()
    )
    indexed = 0
    for chunk in chunks:
        vector = embed_text(chunk.content)
        existing = db.query(RagEmbedding).filter(RagEmbedding.chunk_id == chunk.id).first()
        if vector is None:
            if existing is not None:
                existing.status = 'skipped'
                existing.error_message = 'embedding_unavailable'
            continue
        if existing is None:
            existing = RagEmbedding(
                document_id=document.id,
                chunk_id=chunk.id,
                provider=embedding_provider(),
                model=embedding_model(),
            )
            db.add(existing)
        existing.provider = embedding_provider()
        existing.model = embedding_model()
        existing.vector_payload = vector
        existing.status = 'ready'
        existing.error_message = None
        indexed += 1
    db.flush()
    return indexed


def rebuild_embeddings(db: Session) -> int:
    documents = db.query(RagDocument).filter(RagDocument.status == 'active').all()
    return sum(index_document_embeddings(db, document) for document in documents)


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(a) * float(a) for a in left))
    right_norm = math.sqrt(sum(float(b) * float(b) for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _remote_embedding(text: str) -> list[float]:
    url = str(settings.RAG_EMBEDDING_API_BASE or '').rstrip('/')
    if not url:
        raise RagEmbeddingError('embedding_api_base_required')
    headers = {}
    if settings.RAG_EMBEDDING_API_KEY:
        headers['Authorization'] = f'Bearer {settings.RAG_EMBEDDING_API_KEY}'
    payload = {'inputs': text}
    if embedding_model():
        payload['model'] = embedding_model()
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data: Any = response.json()
    except Exception as exc:
        raise RagEmbeddingError(redact_secret_text(str(exc))) from exc
    vector = _extract_vector(data)
    if vector is None:
        raise RagEmbeddingError('embedding_response_invalid')
    return vector


def _extract_vector(data: Any) -> list[float] | None:
    if isinstance(data, list) and data and all(isinstance(item, (int, float)) for item in data):
        return [float(item) for item in data]
    if isinstance(data, list) and data and isinstance(data[0], list):
        return [float(item) for item in data[0]]
    if isinstance(data, dict):
        for key in ('embedding', 'embeddings', 'data'):
            vector = _extract_vector(data.get(key))
            if vector:
                return vector
    return None


def _stable_local_embedding(text: str, *, dims: int = 64) -> list[float]:
    buckets = [0.0] * dims
    for token in _tokenize_for_embedding(text):
        digest = hashlib.sha256(token.encode('utf-8')).digest()
        index = digest[0] % dims
        sign = 1.0 if digest[1] % 2 == 0 else -1.0
        buckets[index] += sign
    norm = math.sqrt(sum(item * item for item in buckets)) or 1.0
    return [round(item / norm, 8) for item in buckets]


def _tokenize_for_embedding(text: str) -> list[str]:
    clean = ''.join(char if char.isalnum() or '\u4e00' <= char <= '\u9fff' else ' ' for char in text.lower())
    parts = [item for item in clean.split() if item]
    cjk = ''.join(char for char in text if '\u4e00' <= char <= '\u9fff')
    parts.extend(cjk[index : index + 2] for index in range(max(0, len(cjk) - 1)))
    return parts or [text[:32]]
