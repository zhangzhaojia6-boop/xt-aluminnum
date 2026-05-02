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


def _public_conversation(conversation: dict) -> dict:
    return {
        'id': conversation['id'],
        'title': conversation['title'],
        'created_at': conversation['created_at'],
        'updated_at': conversation['updated_at'],
    }


@router.get('/conversations')
def list_conversations(current_user: User = Depends(get_current_user)) -> list[dict]:
    _ = current_user
    return [
        _public_conversation(conversation)
        for conversation in sorted(conversations_db.values(), key=lambda item: item['updated_at'], reverse=True)
    ]


@router.post('/conversations')
def create_conversation(current_user: User = Depends(get_current_user)) -> dict:
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
def get_conversation(conversation_id: str, current_user: User = Depends(get_current_user)) -> dict:
    _ = current_user
    conversation = conversations_db.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail='Conversation not found')
    return conversation


@router.patch('/conversations/{conversation_id}')
def rename_conversation(
    conversation_id: str,
    body: ConversationRename,
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    conversation = conversations_db.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail='Conversation not found')
    conversation['title'] = body.title.strip()
    conversation['updated_at'] = _now()
    return _public_conversation(conversation)


@router.delete('/conversations/{conversation_id}')
def delete_conversation(conversation_id: str, current_user: User = Depends(get_current_user)) -> dict[str, bool]:
    _ = current_user
    conversations_db.pop(conversation_id, None)
    return {'ok': True}


@router.post('/chat')
def chat(body: ChatRequest, current_user: User = Depends(get_current_user)) -> StreamingResponse:
    _ = current_user
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
def stop_generation(conversation_id: str, current_user: User = Depends(get_current_user)) -> dict[str, bool]:
    _ = current_user
    if conversation_id not in conversations_db:
        raise HTTPException(status_code=404, detail='Conversation not found')
    return {'ok': True}


@router.get('/assistant/conversations', response_model=list[AiConversationOut])
def list_assistant_conversations(current_user: User = Depends(get_current_user)) -> list[dict]:
    _ = current_user
    return list_conversations(current_user)


@router.post('/assistant/conversations', response_model=AiConversationOut)
def create_assistant_conversation(
    body: AiConversationCreateIn | None = None,
    current_user: User = Depends(get_current_user),
) -> dict:
    conversation = create_conversation(current_user)
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
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    _ = current_user
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
    conversation = conversations_db.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail='Conversation not found')

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
    return ai_context_service.answer_from_context(
        db,
        user=current_user,
        question=body.question,
        intent=body.intent,
        scope=body.scope or {},
    )


@router.get('/briefings', response_model=list[AiBriefingOut])
def list_briefings(current_user: User = Depends(get_current_user)) -> list[dict]:
    _ = current_user
    return briefings_db


@router.post('/briefings/generate-now', response_model=AiBriefingOut)
def generate_briefing_now(
    body: AiBriefingGenerateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    event = ai_briefing_service.generate_briefing(
        db,
        briefing_type=body.briefing_type,
        hide_normal=body.hide_normal,
    )
    briefings_db.insert(0, event)
    return event


@router.post('/briefings/{briefing_id}/read', response_model=AiBriefingOut)
def mark_briefing_read(briefing_id: str, current_user: User = Depends(get_current_user)) -> dict:
    _ = current_user
    event = _find_briefing(briefing_id)
    event['read'] = True
    return event


@router.post('/briefings/{briefing_id}/follow-up', response_model=AiBriefingOut)
def mark_briefing_follow_up(briefing_id: str, current_user: User = Depends(get_current_user)) -> dict:
    _ = current_user
    event = _find_briefing(briefing_id)
    event['follow_up_status'] = 'followed'
    return event


@router.get('/watchlist', response_model=list[AiWatchlistOut])
def list_watchlist(current_user: User = Depends(get_current_user)) -> list[dict]:
    _ = current_user
    return list(watchlist_db.values())


@router.post('/watchlist', response_model=AiWatchlistOut)
def create_watchlist_item(
    body: AiWatchlistCreateIn,
    current_user: User = Depends(get_current_user),
) -> dict:
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
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    item = watchlist_db.get(watch_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Watchlist item not found')
    for key, value in body.model_dump(exclude_unset=True).items():
        item[key] = value
    return item


@router.delete('/watchlist/{watch_id}')
def delete_watchlist_item(watch_id: str, current_user: User = Depends(get_current_user)) -> dict[str, bool]:
    _ = current_user
    watchlist_db.pop(watch_id, None)
    return {'ok': True}


def _find_briefing(briefing_id: str) -> dict:
    for event in briefings_db:
        if event.get('id') == briefing_id:
            return event
    raise HTTPException(status_code=404, detail='Briefing not found')
