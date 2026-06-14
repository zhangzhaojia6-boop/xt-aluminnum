from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.rag import RagChunk, RagDocument, RagQueryLog
from app.models.system import User


ALLOWED_EXTENSIONS = {'.txt', '.md', '.csv', '.json', '.log'}
BLOCKED_EXTENSIONS = {'.exe', '.cmd', '.bat', '.ps1', '.sh', '.dll', '.msi', '.scr'}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
SECRET_PATTERN = re.compile(
    r'(password|passwd|secret|token|api[_-]?key|app[_-]?secret|database[_-]?password|数据库密码|密钥)\s*[:=]',
    re.IGNORECASE,
)


class RagValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DecodedText:
    text: str
    encoding: str


def create_document_from_bytes(
    db: Session,
    *,
    filename: str,
    content: bytes,
    content_type: str | None,
    uploaded_by: User | None,
) -> RagDocument:
    clean_name = _clean_filename(filename)
    decoded = validate_and_decode_upload(clean_name, content)
    chunks = split_text(decoded.text)

    document = RagDocument(
        filename=clean_name,
        source_name=clean_name,
        content_type=content_type,
        encoding=decoded.encoding,
        status='active',
        file_size=len(content),
        chunk_count=len(chunks),
        uploaded_by_id=getattr(uploaded_by, 'id', None),
        metadata_payload={'parser': 'plain_text_fallback'},
    )
    db.add(document)
    db.flush()

    for index, item in enumerate(chunks):
        db.add(
            RagChunk(
                document_id=document.id,
                chunk_index=index,
                content=item['content'],
                char_start=item['char_start'],
                char_end=item['char_end'],
                source_ref=f'{clean_name}#chunk-{index + 1}',
                metadata_payload={'filename': clean_name},
            )
        )
    db.flush()
    return document


def list_documents(db: Session) -> list[RagDocument]:
    return db.query(RagDocument).order_by(RagDocument.created_at.desc(), RagDocument.id.desc()).all()


def get_document_detail(db: Session, document_id: int) -> dict[str, Any] | None:
    document = db.query(RagDocument).filter(RagDocument.id == document_id).first()
    if not document:
        return None
    chunks = (
        db.query(RagChunk)
        .filter(RagChunk.document_id == document.id)
        .order_by(RagChunk.chunk_index.asc())
        .all()
    )
    return {'document': document, 'chunks': chunks}


def delete_document(db: Session, document_id: int) -> bool:
    document = db.query(RagDocument).filter(RagDocument.id == document_id).first()
    if not document:
        return False
    db.query(RagChunk).filter(RagChunk.document_id == document.id).delete(synchronize_session=False)
    db.delete(document)
    db.flush()
    return True


def query_knowledge(db: Session, *, query: str, limit: int, user: User | None = None) -> dict[str, Any]:
    clean_query = str(query or '').strip()
    if not clean_query:
        answer = '数据不足，问题为空，无法检索知识库。'
        citations: list[dict[str, Any]] = []
        _write_query_log(db, query_text=clean_query, answer=answer, citations=citations, user=user)
        return {'answer': answer, 'citations': citations, 'items': []}

    tokens = _query_tokens(clean_query)
    query_filter = or_(*(RagChunk.content.ilike(f'%{token}%') for token in tokens))
    chunks = db.query(RagChunk, RagDocument).join(RagDocument, RagDocument.id == RagChunk.document_id).filter(query_filter).all()
    ranked = sorted(
        ((chunk, document, _score_chunk(clean_query, tokens, chunk.content)) for chunk, document in chunks),
        key=lambda item: (-item[2], item[0].document_id, item[0].chunk_index),
    )[: max(1, min(limit, 10))]

    if not ranked:
        answer = '数据不足，知识库没有找到可靠来源。'
        citations = []
        items = []
    else:
        items = [_chunk_item(chunk, document, score=score) for chunk, document, score in ranked]
        citations = [
            {
                'document_id': item['document_id'],
                'filename': item['filename'],
                'chunk_index': item['chunk_index'],
                'source_ref': item['source_ref'],
            }
            for item in items
        ]
        snippets = '；'.join(item['snippet'] for item in items[:3])
        answer = f'根据知识库资料：{snippets}'

    _write_query_log(db, query_text=clean_query, answer=answer, citations=citations, user=user)
    return {'answer': answer, 'citations': citations, 'items': items}


def validate_and_decode_upload(filename: str, content: bytes) -> DecodedText:
    suffix = Path(filename).suffix.lower()
    if suffix in BLOCKED_EXTENSIONS or suffix not in ALLOWED_EXTENSIONS:
        raise RagValidationError('不支持该文件类型')
    if len(content) > MAX_UPLOAD_BYTES:
        raise RagValidationError('文件过大')
    if not content:
        raise RagValidationError('文件为空')
    if _looks_binary(content):
        raise RagValidationError('不支持二进制文件')

    decoded = _decode_text(content)
    if SECRET_PATTERN.search(decoded.text):
        raise RagValidationError('文件疑似包含敏感密钥，已拒绝入库')
    return decoded


def split_text(text: str) -> list[dict[str, Any]]:
    clean_text = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not clean_text:
        raise RagValidationError('文件没有可入库文本')

    chunks: list[dict[str, Any]] = []
    start = 0
    while start < len(clean_text):
        end = min(start + CHUNK_SIZE, len(clean_text))
        chunk_text = clean_text[start:end].strip()
        if chunk_text:
            chunks.append({'content': chunk_text, 'char_start': start, 'char_end': end})
        if end >= len(clean_text):
            break
        start = max(0, end - CHUNK_OVERLAP)
    return chunks


def serialize_document(document: RagDocument) -> dict[str, Any]:
    return {
        'id': document.id,
        'filename': document.filename,
        'source_name': document.source_name,
        'content_type': document.content_type,
        'encoding': document.encoding,
        'status': document.status,
        'file_size': document.file_size,
        'chunk_count': document.chunk_count,
        'uploaded_by_id': document.uploaded_by_id,
        'created_at': document.created_at.isoformat() if document.created_at else None,
        'updated_at': document.updated_at.isoformat() if document.updated_at else None,
    }


def serialize_chunk(chunk: RagChunk) -> dict[str, Any]:
    return {
        'id': chunk.id,
        'document_id': chunk.document_id,
        'chunk_index': chunk.chunk_index,
        'content': chunk.content,
        'char_start': chunk.char_start,
        'char_end': chunk.char_end,
        'source_ref': chunk.source_ref,
    }


def _clean_filename(filename: str) -> str:
    clean_name = Path(str(filename or '')).name.strip()
    if not clean_name:
        raise RagValidationError('文件名不能为空')
    return clean_name


def _looks_binary(content: bytes) -> bool:
    if b'\x00' in content:
        return True
    sample = content[:1024]
    control_count = sum(1 for value in sample if value < 9 or (13 < value < 32))
    return bool(sample) and control_count / len(sample) > 0.2


def _decode_text(content: bytes) -> DecodedText:
    for encoding in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            continue
        normalized = 'utf-8' if encoding in {'utf-8-sig', 'utf-8'} else encoding
        return DecodedText(text=text, encoding=normalized)
    raise RagValidationError('仅支持 UTF-8 或 GBK 文本')


def _query_tokens(query: str) -> list[str]:
    parts = re.split(r'[\s,，。；;：:/\\|+-]+', query)
    tokens: list[str] = []
    for part in parts:
        clean_part = part.strip()
        if len(clean_part) < 2:
            continue
        tokens.append(clean_part)
        if _contains_cjk(clean_part) and len(clean_part) > 4:
            tokens.extend(clean_part[index : index + 4] for index in range(0, len(clean_part) - 3))
    return tokens or [query]


def _contains_cjk(value: str) -> bool:
    return any('\u4e00' <= char <= '\u9fff' for char in value)


def _score_chunk(query: str, tokens: list[str], content: str) -> int:
    score = 0
    if query in content:
        score += 5
    for token in tokens:
        if token in content:
            score += 2
    return score


def _chunk_item(chunk: RagChunk, document: RagDocument, *, score: int) -> dict[str, Any]:
    snippet = chunk.content[:220]
    return {
        'document_id': document.id,
        'filename': document.filename,
        'chunk_index': chunk.chunk_index,
        'source_ref': chunk.source_ref,
        'score': score,
        'snippet': snippet,
    }


def _write_query_log(
    db: Session,
    *,
    query_text: str,
    answer: str,
    citations: list[dict[str, Any]],
    user: User | None,
) -> None:
    db.add(
        RagQueryLog(
            query_text=query_text,
            answer=answer,
            result_count=len(citations),
            citations=citations,
            user_id=getattr(user, 'id', None),
        )
    )
    db.flush()
