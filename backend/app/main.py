from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover
    BackgroundScheduler = None

from app.adapters import MesAdapter, NullMesAdapter, set_mes_adapter
from app.agents.aggregator import aggregator_agent
from app.agents.reporter import reporter_agent
from app.agents.reminder import reminder_agent
from app.config import settings
from app.core import event_bus as event_bus_service
from app.core import health as health_service
from app.core.exceptions import BusinessException, business_exception_handler, http_exception_handler
from app.routers import ai, assistant, attendance, auth, command, dashboard, dingtalk, energy, export, imports, master, mes, mobile, notifications, ocr, production, quality, realtime, reconciliation, reports, search, templates, users, work_orders
from app.services import dingtalk_service

scheduler = BackgroundScheduler(timezone=settings.DEFAULT_TIMEZONE) if BackgroundScheduler else None
logger = logging.getLogger(__name__)


def create_mes_adapter() -> MesAdapter:
    adapter_name = (settings.MES_ADAPTER or 'null').strip().lower()
    if adapter_name == 'null':
        return NullMesAdapter()
    if adapter_name == 'rest_api':
        from app.adapters.rest_api_mes_adapter import RestApiMesAdapter

        return RestApiMesAdapter(
            base_url=str(settings.MES_API_BASE or '').strip(),
            api_key=settings.MES_API_KEY,
            timeout_seconds=settings.MES_API_TIMEOUT_SECONDS,
            tracking_card_info_path=settings.mes_api_tracking_card_info_path_normalized,
            coil_snapshots_path=settings.mes_api_coil_snapshots_path_normalized,
        )
    raise RuntimeError(f'Unsupported MES_ADAPTER: {settings.MES_ADAPTER}')


set_mes_adapter(create_mes_adapter())


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime_settings()
    uploads_dir = settings.upload_dir_path
    uploads_dir.mkdir(parents=True, exist_ok=True)
    if scheduler and not scheduler.running:
        dingtalk_service.register_jobs(scheduler)
        event_bus_service.register_jobs(scheduler)
        # 注册确定性编排任务
        from app.database import get_sessionmaker

        session_factory = get_sessionmaker()

        def _pipeline_ready(*, target_date):
            if not settings.AUTO_PIPELINE_REQUIRE_READY:
                return True
            gate = health_service.inspect_pipeline_readiness(target_date=target_date)
            if gate.get('hard_gate_passed'):
                return True
            logger.warning(
                'Deterministic pipeline skipped for %s due to readiness hard gate: %s',
                target_date.isoformat(),
                gate.get('hard_issues', []),
            )
            return False

        def _run_orchestration_pipeline():
            """按顺序执行自动汇总与自动发布主链路。"""

            target_date = health_service.current_business_date()
            try:
                if not _pipeline_ready(target_date=target_date):
                    return
            except Exception:
                    logger.exception('Deterministic pipeline readiness check failed')
                    return

            with session_factory() as session:
                try:
                    aggregator_agent.execute(db=session, target_date=target_date)
                    session.commit()
                except Exception:
                    session.rollback()
                    aggregator_agent.logger.exception('Aggregator failed')
                    return

            with session_factory() as session:
                try:
                    reporter_agent.execute(db=session, target_date=target_date)
                    session.commit()
                except Exception:
                    session.rollback()
                    reporter_agent.logger.exception('Reporter failed')

        def _run_reminder_sweep():
            """每30分钟检查未提交的班次"""
            with session_factory() as session:
                try:
                    reminder_agent.execute(db=session, target_date=health_service.current_business_date())
                    session.commit()
                except Exception:
                    session.rollback()
                    reminder_agent.logger.exception('Reminder failed')

        def _run_mes_sync():
            from app.services import mes_sync_service

            with session_factory() as session:
                try:
                    mes_sync_service.sync_coil_snapshots(db=session)
                    session.commit()
                except Exception:
                    session.rollback()
                    logger.exception('MES sync failed')

        scheduler.add_job(
            _run_orchestration_pipeline,
            'interval',
            hours=1,
            id='deterministic_pipeline',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        if (settings.MES_ADAPTER or 'null').strip().lower() != 'null':
            scheduler.add_job(
                _run_mes_sync,
                'interval',
                minutes=settings.MES_SYNC_POLL_MINUTES,
                id='mes_sync',
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
        scheduler.add_job(
            _run_reminder_sweep,
            'interval',
            minutes=30,
            id='reminder_sweep',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
    yield
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.APP_NAME,
    description='鑫泰铝业生产管理接口',
    version='0.4.0',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.add_exception_handler(BusinessException, business_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

uploads_dir = settings.upload_dir_path
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=str(uploads_dir)), name='uploads')

app.include_router(auth.router, prefix=f'{settings.API_V1_PREFIX}/auth')
app.include_router(users.router, prefix=f'{settings.API_V1_PREFIX}/users')
app.include_router(master.router, prefix=f'{settings.API_V1_PREFIX}/master')
app.include_router(imports.router, prefix=f'{settings.API_V1_PREFIX}/imports')
app.include_router(assistant.router, prefix=f'{settings.API_V1_PREFIX}/assistant')
app.include_router(command.router, prefix=f'{settings.API_V1_PREFIX}/command')
app.include_router(command.admin_router, prefix=f'{settings.API_V1_PREFIX}/admin')
app.include_router(dashboard.router, prefix=f'{settings.API_V1_PREFIX}/dashboard')
app.include_router(attendance.router, prefix=f'{settings.API_V1_PREFIX}/attendance')
app.include_router(production.router, prefix=f'{settings.API_V1_PREFIX}/production')
app.include_router(mobile.router, prefix=f'{settings.API_V1_PREFIX}/mobile')
app.include_router(ocr.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(reports.router, prefix=f'{settings.API_V1_PREFIX}/reports')
app.include_router(mes.router, prefix=f'{settings.API_V1_PREFIX}/mes')
app.include_router(reconciliation.router, prefix=f'{settings.API_V1_PREFIX}/reconciliation')
app.include_router(energy.router, prefix=f'{settings.API_V1_PREFIX}/energy')
app.include_router(quality.router, prefix=f'{settings.API_V1_PREFIX}/quality')
app.include_router(realtime.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(templates.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(dingtalk.router, prefix=f'{settings.API_V1_PREFIX}/dingtalk')
app.include_router(work_orders.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(ai.router, prefix=f'{settings.API_V1_PREFIX}/ai')
app.include_router(search.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(export.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(notifications.router, prefix=f'{settings.API_V1_PREFIX}/notifications')


@app.get('/')
def root() -> dict[str, str]:
    return {'message': settings.APP_NAME, 'docs': '/docs'}


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/healthz')
def healthz() -> dict:
    return health_service.build_liveness_payload()


@app.get('/readyz')
def readyz() -> JSONResponse:
    ready, payload = health_service.build_readiness_payload()
    return JSONResponse(content=payload, status_code=200 if ready else 503)
