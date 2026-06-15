from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.scope import can_request_workshop_scope
from app.core.redaction import redact_secret_text
from app.models.rag import RagChunk, RagDocument, RagQueryLog
from app.models.system import User


ALLOWED_EXTENSIONS = {'.txt', '.md', '.csv', '.json', '.log'}
BLOCKED_EXTENSIONS = {'.exe', '.cmd', '.bat', '.ps1', '.sh', '.dll', '.msi', '.scr'}
EXECUTABLE_SIGNATURES = (
    b'MZ',
    b'\x7fELF',
    b'\xfe\xed\xfa\xce',
    b'\xfe\xed\xfa\xcf',
    b'\xca\xfe\xba\xbe',
)
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
SECRET_PATTERN = re.compile(
    r'((password|passwd|secret|token|api[_-]?key|app[_-]?secret|database[_-]?password|数据库密码|密钥)\s*[:=]'
    r'|authorization\s*[:=]\s*bearer\s+\S+'
    r'|-----begin [a-z0-9 ]*private key-----)',
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
    source_name: str | None = None,
    metadata: dict[str, Any] | None = None,
    scope: dict[str, Any] | None = None,
) -> RagDocument:
    clean_name = _clean_filename(filename)
    clean_source_name = _clean_source_name(source_name, fallback=clean_name)
    public_metadata = _clean_payload(metadata)
    decoded = validate_and_decode_upload(clean_name, content)
    chunks = split_text(decoded.text)

    document = RagDocument(
        filename=clean_name,
        source_name=clean_source_name,
        content_type=content_type,
        encoding=decoded.encoding,
        status='active',
        file_size=len(content),
        chunk_count=len(chunks),
        uploaded_by_id=getattr(uploaded_by, 'id', None),
        scope_payload=_clean_payload(scope),
        metadata_payload={'parser': 'plain_text_fallback', **public_metadata},
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
                metadata_payload={'filename': clean_name, 'source_name': clean_source_name},
            )
        )
    db.flush()
    return document


def list_documents(db: Session) -> list[RagDocument]:
    return (
        db.query(RagDocument)
        .filter(RagDocument.status == 'active')
        .order_by(RagDocument.created_at.desc(), RagDocument.id.desc())
        .all()
    )


def get_document_detail(db: Session, document_id: int) -> dict[str, Any] | None:
    document = db.query(RagDocument).filter(RagDocument.id == document_id, RagDocument.status == 'active').first()
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
    document = db.query(RagDocument).filter(RagDocument.id == document_id, RagDocument.status == 'active').first()
    if not document:
        return False
    document.status = 'deleted'
    db.flush()
    return True


def query_knowledge(
    db: Session,
    *,
    query: str,
    limit: int,
    user: User | None = None,
    workshop: str | None = None,
    machine_code: str | None = None,
) -> dict[str, Any]:
    clean_query = str(query or '').strip()
    if not clean_query:
        answer = '数据不足，问题为空，无法检索知识库。'
        citations: list[dict[str, Any]] = []
        _write_query_log(db, query_text=clean_query, answer=answer, citations=citations, user=user)
        return {'answer': answer, 'citations': citations, 'items': []}

    tokens = _query_tokens(clean_query)
    metadata_filters = _clean_payload({'workshop': workshop, 'machine_code': machine_code})
    query_filter = or_(*(RagChunk.content.ilike(f'%{token}%') for token in tokens))
    chunks = (
        db.query(RagChunk, RagDocument)
        .join(RagDocument, RagDocument.id == RagChunk.document_id)
        .filter(RagDocument.status == 'active')
        .filter(query_filter)
        .all()
    )
    if metadata_filters:
        chunks = [
            (chunk, document)
            for chunk, document in chunks
            if _document_matches_metadata(document, metadata_filters)
        ]
    chunks = [
        (chunk, document)
        for chunk, document in chunks
        if _document_visible_to_user(db, document, user)
    ]
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
                'source_name': item['source_name'],
                'chunk_index': item['chunk_index'],
                'source_ref': item['source_ref'],
                'metadata': item['metadata'],
            }
            for item in items
        ]
        snippets = '；'.join(item['snippet'] for item in items[:3])
        source_text = '、'.join(item['source_ref'] for item in items[:3])
        answer = f'根据知识库资料：{snippets}\n来源：{source_text}'

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
    if _looks_executable(content):
        raise RagValidationError('不支持可执行文件')
    if _looks_binary(content):
        raise RagValidationError('不支持二进制文件')

    decoded = _decode_text(content)
    if suffix == '.json':
        _validate_json_text(decoded.text)
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
        'scope_payload': document.scope_payload or {},
        'metadata_payload': _public_metadata(document.metadata_payload),
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


def _clean_source_name(source_name: str | None, *, fallback: str) -> str:
    clean_name = redact_secret_text(str(source_name or '').strip())
    return clean_name or fallback


def _clean_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    clean_payload: dict[str, Any] = {}
    for key, value in (payload or {}).items():
        clean_value = redact_secret_text(str(value or '').strip())
        if clean_value:
            clean_payload[str(key)] = clean_value
    return clean_payload


def _public_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    return {
        key: value
        for key, value in (payload or {}).items()
        if key != 'parser'
    }


def _document_matches_metadata(document: RagDocument, metadata_filters: dict[str, Any]) -> bool:
    public_metadata = _public_metadata(document.metadata_payload)
    for key, expected in metadata_filters.items():
        actual = str(public_metadata.get(key) or '').strip()
        if actual.casefold() != str(expected).strip().casefold():
            return False
    return True


def _document_visible_to_user(db: Session, document: RagDocument, user: User | None) -> bool:
    if user is None:
        return True
    public_metadata = _public_metadata(document.metadata_payload)
    workshop = str(public_metadata.get('workshop') or '').strip()
    if not workshop:
        return True
    return can_request_workshop_scope(user, db, workshop)


def _looks_binary(content: bytes) -> bool:
    if b'\x00' in content:
        return True
    sample = content[:1024]
    control_count = sum(1 for value in sample if value < 9 or (13 < value < 32))
    return bool(sample) and control_count / len(sample) > 0.2


def _looks_executable(content: bytes) -> bool:
    return any(content.startswith(signature) for signature in EXECUTABLE_SIGNATURES)


def _validate_json_text(text: str) -> None:
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        raise RagValidationError('JSON 文件格式不正确') from exc


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
    snippet = redact_secret_text(chunk.content[:220])
    return {
        'document_id': document.id,
        'filename': document.filename,
        'source_name': document.source_name,
        'chunk_index': chunk.chunk_index,
        'source_ref': chunk.source_ref,
        'metadata': _public_metadata(document.metadata_payload),
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
            query_text=redact_secret_text(query_text),
            answer=redact_secret_text(answer),
            result_count=len(citations),
            citations=citations,
            user_id=getattr(user, 'id', None),
        )
    )
    db.flush()
