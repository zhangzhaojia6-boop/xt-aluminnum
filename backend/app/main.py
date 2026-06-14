from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.adapters import set_mes_adapter
from app.adapters.factory import create_mes_adapter
from app.agents.aggregator import aggregator_agent
from app.agents.aluminum_price_fetcher import aluminum_price_fetcher_agent
from app.agents.cost_aggregator import cost_aggregator_agent
from app.agents.profit_snapshot import profit_snapshot_agent
from app.agents.reporter import reporter_agent
from app.agents.reminder import reminder_agent
from app.config import settings
from app.core import event_bus as event_bus_service
from app.core import health as health_service
from app.core.exceptions import BusinessException, business_exception_handler, http_exception_handler
from app.core.logging import configure_json_logging
from app.core.scheduler import scheduler, setup_scheduler, try_acquire_scheduler_leader, release_scheduler_leader
from app.routers.config import router as config_router
from app.routers import ai, agent_management, assistant, assistant_actions, attendance, auth, command, consumables, contracts, dashboard, dingtalk, energy, executive, export, factory_command, imports, inventory, mapping_reconciliation, master, mes, mobile, notifications, ocr, production, quality, rag, realtime, reconciliation, reports, rule_configs, search, telemetry, templates, user_preferences, users, work_orders
from app.services import dingtalk_service

logger = logging.getLogger(__name__)
configure_json_logging()


set_mes_adapter(create_mes_adapter())


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime_settings()
    uploads_dir = settings.upload_dir_path
    uploads_dir.mkdir(parents=True, exist_ok=True)
    if scheduler and not scheduler.running and try_acquire_scheduler_leader():
        setup_scheduler(scheduler)
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

        def _run_schedule_seed():
            from app.services.pilot_schedule_seed import seed_default_pilot_schedule

            with session_factory() as session:
                try:
                    seed_default_pilot_schedule(session)
                except Exception:
                    session.rollback()
                    logger.exception('Default pilot schedule seed failed')

        def _run_ai_briefing():
            from app.services import ai_briefing_service

            with session_factory() as session:
                try:
                    ai_briefing_service.generate_briefing(session, briefing_type='hourly_inspection', hide_normal=True)
                    session.commit()
                except Exception:
                    session.rollback()
                    logger.exception('AI briefing generation failed')

        def _ensure_master_data():
            from app.services.bootstrap import seed_shift_configs
            from app.services.real_master_data import seed_real_master_data

            with session_factory() as session:
                try:
                    seed_shift_configs(session)
                    seed_real_master_data(session)
                except Exception:
                    session.rollback()
                    logger.exception('Master data seed failed')

        _ensure_master_data()
        _run_schedule_seed()
        scheduler.add_job(
            _run_schedule_seed,
            'cron',
            hour=0,
            minute=5,
            id='default_schedule_seed',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            _run_orchestration_pipeline,
            'interval',
            hours=1,
            id='deterministic_pipeline',
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
        scheduler.add_job(
            _run_ai_briefing,
            'interval',
            hours=1,
            id='ai_hourly_briefing',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

        def _run_aluminum_price_fetch():
            from datetime import date as _date
            with session_factory() as session:
                try:
                    aluminum_price_fetcher_agent.execute(db=session, target_date=_date.today())
                    session.commit()
                except Exception:
                    session.rollback()
                    aluminum_price_fetcher_agent.logger.exception('Aluminum price fetch failed')

        def _run_executive_daily_snapshot():
            from app.core.business_time import last_completed_production_business_date

            target = last_completed_production_business_date()
            with session_factory() as session:
                try:
                    cost_aggregator_agent.execute(db=session, target_date=target)
                    session.flush()
                    profit_snapshot_agent.execute(db=session, target_date=target)
                    session.commit()
                except Exception:
                    session.rollback()
                    cost_aggregator_agent.logger.exception('Executive daily snapshot failed')

        scheduler.add_job(
            _run_aluminum_price_fetch,
            'cron',
            day_of_week='mon-fri',
            hour=10,
            minute=30,
            id='aluminum_price_daily',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            _run_executive_daily_snapshot,
            'cron',
            hour=8,
            minute=20,
            id='executive_daily_snapshot',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
    yield
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
    release_scheduler_leader()


app = FastAPI(
    title=settings.APP_NAME,
    description='鑫泰铝业生产管理接口',
    version='0.4.1',
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
app.include_router(user_preferences.router, prefix=f'{settings.API_V1_PREFIX}/user')
app.include_router(master.router, prefix=f'{settings.API_V1_PREFIX}/master')
app.include_router(imports.router, prefix=f'{settings.API_V1_PREFIX}/imports')
app.include_router(assistant.router, prefix=f'{settings.API_V1_PREFIX}/assistant')
app.include_router(assistant_actions.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(command.router, prefix=f'{settings.API_V1_PREFIX}/command')
app.include_router(command.admin_router, prefix=f'{settings.API_V1_PREFIX}/admin')
app.include_router(dashboard.router, prefix=f'{settings.API_V1_PREFIX}/dashboard')
app.include_router(attendance.router, prefix=f'{settings.API_V1_PREFIX}/attendance')
app.include_router(production.router, prefix=f'{settings.API_V1_PREFIX}/production')
app.include_router(mobile.router, prefix=f'{settings.API_V1_PREFIX}/mobile')
app.include_router(ocr.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(reports.router, prefix=f'{settings.API_V1_PREFIX}/reports')
app.include_router(rule_configs.router, prefix=f'{settings.API_V1_PREFIX}/rule-configs')
app.include_router(mes.router, prefix=f'{settings.API_V1_PREFIX}/mes')
app.include_router(factory_command.router, prefix=f'{settings.API_V1_PREFIX}/factory-command')
app.include_router(agent_management.router, prefix=f'{settings.API_V1_PREFIX}/agent-management')
app.include_router(executive.router, prefix=f'{settings.API_V1_PREFIX}/executive')
app.include_router(reconciliation.router, prefix=f'{settings.API_V1_PREFIX}/reconciliation')
app.include_router(mapping_reconciliation.router, prefix=f'{settings.API_V1_PREFIX}/mapping-reconciliation')
app.include_router(rag.router, prefix=f'{settings.API_V1_PREFIX}/rag')
app.include_router(energy.router, prefix=f'{settings.API_V1_PREFIX}/energy')
app.include_router(inventory.router, prefix=f'{settings.API_V1_PREFIX}/inventory')
app.include_router(contracts.router, prefix=f'{settings.API_V1_PREFIX}/contracts')
app.include_router(consumables.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(quality.router, prefix=f'{settings.API_V1_PREFIX}/quality')
app.include_router(realtime.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(templates.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(dingtalk.router, prefix=f'{settings.API_V1_PREFIX}/dingtalk')
app.include_router(work_orders.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(ai.router, prefix=f'{settings.API_V1_PREFIX}/ai')
app.include_router(search.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(export.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(notifications.router, prefix=f'{settings.API_V1_PREFIX}/notifications')
app.include_router(telemetry.router, prefix=f'{settings.API_V1_PREFIX}')
app.include_router(config_router)


@app.get('/')
def root() -> dict[str, str]:
    return {'message': settings.APP_NAME, 'docs': '/docs'}


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'version': settings.APP_VERSION}


@app.get('/healthz')
def healthz() -> dict:
    return health_service.build_liveness_payload()


@app.get(f'{settings.API_V1_PREFIX}/healthz')
def api_healthz() -> dict:
    return health_service.build_liveness_payload()


@app.get('/readyz')
def readyz() -> JSONResponse:
    ready, payload = health_service.build_readiness_payload()
    return JSONResponse(content=payload, status_code=200 if ready else 503)


@app.get(f'{settings.API_V1_PREFIX}/readyz')
def api_readyz() -> JSONResponse:
    ready, payload = health_service.build_readiness_payload()
    return JSONResponse(content=payload, status_code=200 if ready else 503)
