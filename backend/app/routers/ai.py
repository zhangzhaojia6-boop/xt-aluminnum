from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.models.system import User

router = APIRouter(tags=['ai'])


class ChatRequest(BaseModel):
    conversation_id: str
    message: str = Field(min_length=1)


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=80)


conversations_db: dict[str, dict] = {}


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
