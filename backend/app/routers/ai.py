from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary
from app.models.assistant import AiBriefingEvent, AiConversation, AiMessage, AiWatchlistItem
from app.models.system import User
from app.schemas.ai_assistant import (
    AiAskIn,
    AiBriefingGenerateIn,
    AiBriefingOut,
    AiAnswerOut,
    AiConversationCreateIn,
    AiConversationMessageResponseOut,
    AiConversationOut,
    AiMessageCreateIn,
    AiMessageOut,
    AiWatchlistCreateIn,
    AiWatchlistOut,
    AiWatchlistPatchIn,
)
from app.services import ai_briefing_service, ai_context_service

router = APIRouter(tags=['ai'])


class ChatRequest(BaseModel):
    conversation_id: str
    message: str = Field(min_length=1)


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=80)


conversations_db: dict[str, dict] = {}
briefings_db: list[dict] = []
watchlist_db: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uses_ai_database(db: Session) -> bool:
    return callable(getattr(db, 'query', None)) and callable(getattr(db, 'add', None))


def _commit_if_possible(db: Session) -> None:
    commit = getattr(db, 'commit', None)
    if callable(commit):
        commit()


def _iso(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else _now()


def _ensure_factory_ai_access(user: User) -> None:
    summary = build_scope_summary(user)
    if not bool(summary.is_admin or summary.is_manager or summary.is_reviewer):
        raise HTTPException(status_code=403, detail='AI factory context access denied')


def _public_conversation(conversation: dict) -> dict:
    return {
        'id': conversation['id'],
        'title': conversation['title'],
        'created_at': conversation['created_at'],
        'updated_at': conversation['updated_at'],
    }


def _conversation_out(entity: AiConversation) -> dict:
    return {
        'id': entity.public_id,
        'title': entity.title,
        'created_at': _iso(entity.created_at),
        'updated_at': _iso(entity.updated_at),
    }


def _message_out(entity: AiMessage) -> dict:
    payload = entity.payload or {}
    return {
        'role': entity.role,
        'content': entity.content,
        'timestamp': str(payload.get('timestamp') or _iso(entity.created_at)),
        'payload': payload or None,
    }


def _briefing_out(entity: AiBriefingEvent) -> dict:
    return {
        'id': entity.public_id,
        'briefing_type': entity.briefing_type,
        'severity': entity.severity,
        'title': entity.title,
        'payload': entity.payload,
        'read': entity.read,
        'follow_up_status': entity.follow_up_status,
        'scope_key': entity.scope_key,
        'delivery_suppressed': entity.delivery_suppressed,
    }


def _watchlist_out(entity: AiWatchlistItem) -> dict:
    return {
        'id': entity.public_id,
        'watch_type': entity.watch_type,
        'scope_key': entity.scope_key,
        'trigger_rules': entity.trigger_rules or [],
        'quiet_hours': entity.quiet_hours,
        'frequency': entity.frequency,
        'channels': entity.channels or [],
        'active': entity.active,
    }


def _find_db_conversation(db: Session, *, conversation_id: str, current_user: User) -> AiConversation | None:
    query = db.query(AiConversation).filter(AiConversation.public_id == conversation_id)
    owner_id = getattr(current_user, 'id', None)
    if owner_id is not None:
        query = query.filter(AiConversation.owner_user_id == owner_id)
    return query.first()


def _find_owned_db_briefing(db: Session, *, briefing_id: str, current_user: User) -> AiBriefingEvent | None:
    return (
        db.query(AiBriefingEvent)
        .filter(
            AiBriefingEvent.public_id == briefing_id,
            AiBriefingEvent.owner_user_id == getattr(current_user, 'id', None),
        )
        .first()
    )


def _find_db_watchlist_item(db: Session, *, watch_id: str, current_user: User) -> AiWatchlistItem | None:
    query = db.query(AiWatchlistItem).filter(AiWatchlistItem.public_id == watch_id)
    owner_id = getattr(current_user, 'id', None)
    if owner_id is not None:
        query = query.filter(AiWatchlistItem.owner_user_id == owner_id)
    return query.first()


@router.get('/conversations')
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        query = db.query(AiConversation)
        owner_id = getattr(current_user, 'id', None)
        if owner_id is not None:
            query = query.filter(AiConversation.owner_user_id == owner_id)
        return [_conversation_out(row) for row in query.order_by(AiConversation.updated_at.desc(), AiConversation.id.desc()).all()]
    return [
        _public_conversation(conversation)
        for conversation in sorted(conversations_db.values(), key=lambda item: item['updated_at'], reverse=True)
    ]


@router.post('/conversations')
def create_conversation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        timestamp = datetime.now(timezone.utc)
        conversation = AiConversation(
            public_id=str(uuid4()),
            owner_user_id=getattr(current_user, 'id', None),
            title='新的对话',
            scope_payload={},
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(conversation)
        _commit_if_possible(db)
        return _conversation_out(conversation)

    timestamp = _now()
    conversation_id = str(uuid4())
    conversation = {
        'id': conversation_id,
        'title': '新的对话',
        'messages': [],
        'created_at': timestamp,
        'updated_at': timestamp,
        'owner_id': current_user.id,
    }
    conversations_db[conversation_id] = conversation
    return _public_conversation(conversation)


@router.get('/conversations/{conversation_id}')
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        conversation = _find_db_conversation(db, conversation_id=conversation_id, current_user=current_user)
        if conversation is None:
            raise HTTPException(status_code=404, detail='Conversation not found')
        messages = (
            db.query(AiMessage)
            .filter(AiMessage.conversation_public_id == conversation.public_id)
            .order_by(AiMessage.created_at.asc(), AiMessage.id.asc())
            .all()
        )
        return {
            **_conversation_out(conversation),
            'messages': [_message_out(row) for row in messages],
        }

    conversation = conversations_db.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail='Conversation not found')
    return conversation


@router.patch('/conversations/{conversation_id}')
def rename_conversation(
    conversation_id: str,
    body: ConversationRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        conversation = _find_db_conversation(db, conversation_id=conversation_id, current_user=current_user)
        if conversation is None:
            raise HTTPException(status_code=404, detail='Conversation not found')
        conversation.title = body.title.strip()
        conversation.updated_at = datetime.now(timezone.utc)
        _commit_if_possible(db)
        return _conversation_out(conversation)

    conversation = conversations_db.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail='Conversation not found')
    conversation['title'] = body.title.strip()
    conversation['updated_at'] = _now()
    return _public_conversation(conversation)


@router.delete('/conversations/{conversation_id}')
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        conversation = _find_db_conversation(db, conversation_id=conversation_id, current_user=current_user)
        if conversation is not None:
            for message in db.query(AiMessage).filter(AiMessage.conversation_public_id == conversation.public_id).all():
                db.delete(message)
            db.delete(conversation)
            _commit_if_possible(db)
        return {'ok': True}

    conversations_db.pop(conversation_id, None)
    return {'ok': True}


@router.post('/chat')
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    _ensure_factory_ai_access(current_user)
    db_conversation = _find_db_conversation(db, conversation_id=body.conversation_id, current_user=current_user) if _uses_ai_database(db) else None
    if db_conversation is not None:
        timestamp = _now()
        db.add(
            AiMessage(
                conversation_id=db_conversation.id,
                conversation_public_id=db_conversation.public_id,
                role='user',
                content=body.message,
                payload={'timestamp': timestamp},
            )
        )
        db_conversation.updated_at = datetime.now(timezone.utc)
        _commit_if_possible(db)

        async def generate_db():
            response_text = f'收到：{body.message}'
            for char in response_text:
                yield f"data: {json.dumps({'type': 'text', 'content': char}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)
            db.add(
                AiMessage(
                    conversation_id=db_conversation.id,
                    conversation_public_id=db_conversation.public_id,
                    role='assistant',
                    content=response_text,
                    payload={'timestamp': _now()},
                )
            )
            db_conversation.updated_at = datetime.now(timezone.utc)
            _commit_if_possible(db)
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        return StreamingResponse(generate_db(), media_type='text/event-stream')

    conversation = conversations_db.get(body.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail='Conversation not found')

    timestamp = _now()
    conversation['messages'].append({'role': 'user', 'content': body.message, 'timestamp': timestamp})
    conversation['updated_at'] = timestamp

    async def generate():
        response_text = f'收到：{body.message}'
        for char in response_text:
            yield f"data: {json.dumps({'type': 'text', 'content': char}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)
        conversation['messages'].append({'role': 'assistant', 'content': response_text, 'timestamp': _now()})
        conversation['updated_at'] = _now()
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type='text/event-stream')


@router.post('/conversations/{conversation_id}/stop')
def stop_generation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        if _find_db_conversation(db, conversation_id=conversation_id, current_user=current_user) is None:
            raise HTTPException(status_code=404, detail='Conversation not found')
        return {'ok': True}

    if conversation_id not in conversations_db:
        raise HTTPException(status_code=404, detail='Conversation not found')
    return {'ok': True}


@router.get('/assistant/conversations', response_model=list[AiConversationOut])
def list_assistant_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        query = db.query(AiConversation)
        owner_id = getattr(current_user, 'id', None)
        if owner_id is not None:
            query = query.filter(AiConversation.owner_user_id == owner_id)
        rows = query.order_by(AiConversation.updated_at.desc(), AiConversation.id.desc()).all()
        return [_conversation_out(row) for row in rows]
    return list_conversations(db, current_user)


@router.post('/assistant/conversations', response_model=AiConversationOut)
def create_assistant_conversation(
    body: AiConversationCreateIn | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        timestamp = datetime.now(timezone.utc)
        conversation = AiConversation(
            public_id=str(uuid4()),
            owner_user_id=getattr(current_user, 'id', None),
            title=(body.title.strip() if body and body.title else '新的对话'),
            scope_payload=body.scope if body else {},
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(conversation)
        _commit_if_possible(db)
        return _conversation_out(conversation)

    conversation = create_conversation(db, current_user)
    if body and body.title:
        stored = conversations_db[conversation['id']]
        stored['title'] = body.title.strip() or stored['title']
        stored['scope'] = body.scope or {}
        stored['updated_at'] = _now()
        return _public_conversation(stored)
    return conversation


@router.get('/assistant/conversations/{conversation_id}/messages', response_model=list[AiMessageOut])
def list_assistant_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        conversation = _find_db_conversation(db, conversation_id=conversation_id, current_user=current_user)
        if conversation is None:
            raise HTTPException(status_code=404, detail='Conversation not found')
        rows = (
            db.query(AiMessage)
            .filter(AiMessage.conversation_public_id == conversation.public_id)
            .order_by(AiMessage.created_at.asc(), AiMessage.id.asc())
            .all()
        )
        return [_message_out(row) for row in rows]

    conversation = conversations_db.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail='Conversation not found')
    return conversation.get('messages', [])


@router.post('/assistant/conversations/{conversation_id}/messages', response_model=AiConversationMessageResponseOut)
def create_assistant_message(
    conversation_id: str,
    body: AiMessageCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)

    timestamp = _now()
    user_message = {'role': 'user', 'content': body.content, 'timestamp': timestamp, 'payload': {'scope': body.scope or {}}}
    answer = ai_context_service.answer_from_context(
        db,
        user=current_user,
        question=body.content,
        intent=body.intent,
        scope=body.scope or {},
    )
    assistant_message = {
        'role': 'assistant',
        'content': answer['answer'],
        'timestamp': _now(),
        'payload': {'answer': answer},
    }
    if _uses_ai_database(db):
        conversation = _find_db_conversation(db, conversation_id=conversation_id, current_user=current_user)
        if conversation is None:
            raise HTTPException(status_code=404, detail='Conversation not found')
        db.add(
            AiMessage(
                conversation_id=conversation.id,
                conversation_public_id=conversation.public_id,
                role='user',
                content=body.content,
                payload=user_message['payload'] | {'timestamp': timestamp},
            )
        )
        db.add(
            AiMessage(
                conversation_id=conversation.id,
                conversation_public_id=conversation.public_id,
                role='assistant',
                content=answer['answer'],
                payload=assistant_message['payload'] | {'timestamp': assistant_message['timestamp']},
            )
        )
        conversation.updated_at = datetime.now(timezone.utc)
        _commit_if_possible(db)
        return {
            'user_message': user_message,
            'assistant_message': assistant_message,
            'answer': answer,
        }

    conversation = conversations_db.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail='Conversation not found')
    conversation.setdefault('messages', []).extend([user_message, assistant_message])
    conversation['updated_at'] = assistant_message['timestamp']
    return {
        'user_message': user_message,
        'assistant_message': assistant_message,
        'answer': answer,
    }


@router.post('/assistant/ask', response_model=AiAnswerOut)
def ask_assistant(
    body: AiAskIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)
    return ai_context_service.answer_from_context(
        db,
        user=current_user,
        question=body.question,
        intent=body.intent,
        scope=body.scope or {},
    )


@router.get('/briefings', response_model=list[AiBriefingOut])
def list_briefings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        rows = (
            db.query(AiBriefingEvent)
            .filter(AiBriefingEvent.owner_user_id == getattr(current_user, 'id', None))
            .order_by(AiBriefingEvent.created_at.desc(), AiBriefingEvent.id.desc())
            .all()
        )
        return [_briefing_out(row) for row in rows]
    return briefings_db


@router.post('/briefings/generate-now', response_model=AiBriefingOut)
def generate_briefing_now(
    body: AiBriefingGenerateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)
    event = ai_briefing_service.generate_briefing(
        db,
        briefing_type=body.briefing_type,
        hide_normal=body.hide_normal,
        owner_user_id=getattr(current_user, 'id', None),
        scope=build_scope_summary(current_user),
    )
    if _uses_ai_database(db):
        _commit_if_possible(db)
        return event
    briefings_db.insert(0, event)
    return event


@router.post('/briefings/{briefing_id}/read', response_model=AiBriefingOut)
def mark_briefing_read(
    briefing_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        entity = _find_owned_db_briefing(db, briefing_id=briefing_id, current_user=current_user)
        if entity is None:
            raise HTTPException(status_code=404, detail='Briefing not found')
        entity.read = True
        _commit_if_possible(db)
        return _briefing_out(entity)

    event = _find_briefing(briefing_id)
    event['read'] = True
    return event


@router.post('/briefings/{briefing_id}/follow-up', response_model=AiBriefingOut)
def mark_briefing_follow_up(
    briefing_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        entity = _find_owned_db_briefing(db, briefing_id=briefing_id, current_user=current_user)
        if entity is None:
            raise HTTPException(status_code=404, detail='Briefing not found')
        entity.follow_up_status = 'followed'
        _commit_if_possible(db)
        return _briefing_out(entity)

    event = _find_briefing(briefing_id)
    event['follow_up_status'] = 'followed'
    return event


@router.get('/watchlist', response_model=list[AiWatchlistOut])
def list_watchlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        query = db.query(AiWatchlistItem)
        owner_id = getattr(current_user, 'id', None)
        if owner_id is not None:
            query = query.filter(AiWatchlistItem.owner_user_id == owner_id)
        return [_watchlist_out(row) for row in query.order_by(AiWatchlistItem.created_at.desc(), AiWatchlistItem.id.desc()).all()]
    return list(watchlist_db.values())


@router.post('/watchlist', response_model=AiWatchlistOut)
def create_watchlist_item(
    body: AiWatchlistCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        item = AiWatchlistItem(
            public_id=f'watch-{uuid4().hex[:12]}',
            owner_user_id=getattr(current_user, 'id', None),
            watch_type=body.watch_type,
            scope_key=body.scope_key,
            trigger_rules=body.trigger_rules,
            quiet_hours=body.quiet_hours,
            frequency=body.frequency,
            channels=body.channels,
            active=body.active,
        )
        db.add(item)
        _commit_if_possible(db)
        return _watchlist_out(item)

    item_id = f'watch-{uuid4().hex[:12]}'
    item = {
        'id': item_id,
        'watch_type': body.watch_type,
        'scope_key': body.scope_key,
        'trigger_rules': body.trigger_rules,
        'quiet_hours': body.quiet_hours,
        'frequency': body.frequency,
        'channels': body.channels,
        'active': body.active,
        'owner_user_id': getattr(current_user, 'id', None),
    }
    watchlist_db[item_id] = item
    return item


@router.patch('/watchlist/{watch_id}', response_model=AiWatchlistOut)
def update_watchlist_item(
    watch_id: str,
    body: AiWatchlistPatchIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        entity = _find_db_watchlist_item(db, watch_id=watch_id, current_user=current_user)
        if entity is None:
            raise HTTPException(status_code=404, detail='Watchlist item not found')
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(entity, key, value)
        _commit_if_possible(db)
        return _watchlist_out(entity)

    item = watchlist_db.get(watch_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Watchlist item not found')
    for key, value in body.model_dump(exclude_unset=True).items():
        item[key] = value
    return item


@router.delete('/watchlist/{watch_id}')
def delete_watchlist_item(
    watch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    _ensure_factory_ai_access(current_user)
    if _uses_ai_database(db):
        entity = _find_db_watchlist_item(db, watch_id=watch_id, current_user=current_user)
        if entity is not None:
            db.delete(entity)
            _commit_if_possible(db)
        return {'ok': True}

    watchlist_db.pop(watch_id, None)
    return {'ok': True}


def _find_briefing(briefing_id: str) -> dict:
    for event in briefings_db:
        if event.get('id') == briefing_id:
            return event
    raise HTTPException(status_code=404, detail='Briefing not found')
