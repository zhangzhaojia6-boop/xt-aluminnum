from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.permissions import get_current_manager_user
from app.core.rate_limit import enforce_request_rate_limit
from app.models.system import User
from app.schemas.assistant import (
    AssistantCapabilitiesResponseOut,
    AssistantImageRequestIn,
    AssistantImageResponseOut,
    AssistantLiveProbeResponseOut,
    AssistantQueryRequestIn,
    AssistantQueryResponseOut,
)
from app.services import assistant_service

router = APIRouter(tags=['assistant'])


@router.get('/capabilities', response_model=AssistantCapabilitiesResponseOut)
def get_assistant_capabilities(
    request: Request,
    current_user: User = Depends(get_current_manager_user),
) -> AssistantCapabilitiesResponseOut:
    enforce_request_rate_limit(request, current_user, scope='assistant', limit=60, window_seconds=60)
    return assistant_service.build_assistant_capabilities()


@router.post('/query', response_model=AssistantQueryResponseOut)
def query_assistant(
    payload: AssistantQueryRequestIn,
    request: Request,
    current_user: User = Depends(get_current_manager_user),
) -> AssistantQueryResponseOut:
    enforce_request_rate_limit(request, current_user, scope='assistant', limit=60, window_seconds=60)
    return assistant_service.run_assistant_query(payload)


@router.post('/generate-image', response_model=AssistantImageResponseOut)
def generate_assistant_image(
    payload: AssistantImageRequestIn,
    request: Request,
    current_user: User = Depends(get_current_manager_user),
) -> AssistantImageResponseOut:
    enforce_request_rate_limit(request, current_user, scope='assistant', limit=60, window_seconds=60)
    return assistant_service.build_assistant_image(payload)


@router.get('/live-probe', response_model=AssistantLiveProbeResponseOut)
def assistant_live_probe(
    request: Request,
    current_user: User = Depends(get_current_manager_user),
) -> AssistantLiveProbeResponseOut:
    enforce_request_rate_limit(request, current_user, scope='assistant_probe', limit=12, window_seconds=60)
    return assistant_service.run_assistant_live_probe()
