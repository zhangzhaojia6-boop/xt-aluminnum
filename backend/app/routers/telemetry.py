import logging

from fastapi import APIRouter

from app.schemas.telemetry import ErrorReport, PerfReport

router = APIRouter(prefix='/telemetry', tags=['telemetry'])
logger = logging.getLogger(__name__)


@router.post('/errors')
async def receive_error(payload: ErrorReport) -> dict:
    logger.warning(
        'frontend_error: %s at %s',
        payload.message,
        payload.url,
        extra={'stack': payload.stack, 'info': payload.info},
    )
    return {'received': True}


@router.post('/perf')
async def receive_perf(payload: PerfReport) -> dict:
    logger.info(
        'frontend_perf: %s %s=%s',
        payload.route,
        payload.metric,
        payload.value,
    )
    return {'received': True}
