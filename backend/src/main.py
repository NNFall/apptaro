from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import api_router
from src.core.dependencies import get_billing_service
from src.core.logging import configure_logging, get_logger
from src.core.settings import get_settings
from src.repositories.jobs import fail_incomplete_jobs
from src.repositories.storage import configure_database_path, init_storage


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    configure_database_path(settings.database_path)
    init_storage(settings.database_path)
    recovered_jobs = fail_incomplete_jobs()
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    settings.templates_dir.mkdir(parents=True, exist_ok=True)
    logger = get_logger('appslides.backend.app')
    billing_service = get_billing_service()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        auto_renew_task: asyncio.Task[None] | None = None

        logger.info(
            'Backend starting: env=%s data_dir=%s database_path=%s temp_dir=%s templates_dir=%s',
            settings.app_env,
            settings.data_dir,
            settings.database_path,
            settings.temp_dir,
            settings.templates_dir,
        )
        if recovered_jobs:
            logger.warning('Marked %s incomplete jobs as failed after restart', recovered_jobs)
        if billing_service.is_configured:
            auto_renew_task = asyncio.create_task(_auto_renew_loop(billing_service, settings.auto_renew_interval, logger))
        yield
        if auto_renew_task is not None:
            auto_renew_task.cancel()
            try:
                await auto_renew_task
            except asyncio.CancelledError:
                pass

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url='/docs',
        redoc_url='/redoc',
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.include_router(api_router)

    @app.get('/', tags=['system'])
    async def root() -> dict[str, str]:
        return {
            'service': settings.app_name,
            'version': settings.app_version,
            'environment': settings.app_env,
        }

    return app


app = create_app()


async def _auto_renew_loop(service, interval_seconds: int, logger) -> None:
    while True:
        try:
            processed = await service.process_due_auto_renewals_once()
            if processed:
                logger.info('Processed %s subscription auto-renew checks', processed)
        except Exception:  # noqa: BLE001
            logger.exception('Auto-renew loop failed')
        await asyncio.sleep(max(10, interval_seconds))
