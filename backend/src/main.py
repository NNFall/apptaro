from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import api_router
from src.core.dependencies import (
    get_admin_notifier,
    get_app_store_billing_service,
    get_billing_service,
)
from src.core.logging import configure_logging, get_logger
from src.core.settings import get_settings
from src.repositories.jobs import fail_incomplete_jobs
from src.repositories.storage import configure_database_path, init_storage


APP_STORE_OUTBOX_SHUTDOWN_TIMEOUT_SECONDS = 15.0


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
    app_store_billing_service = get_app_store_billing_service()
    admin_notifier = get_admin_notifier()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        auto_renew_task: asyncio.Task[None] | None = None
        outbox_stop_event = asyncio.Event()
        outbox_task = asyncio.create_task(
            _app_store_outbox_loop(
                app_store_billing_service,
                admin_notifier,
                logger,
                stop_event=outbox_stop_event,
            )
        )

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
        try:
            yield
        finally:
            outbox_stop_event.set()
            try:
                await asyncio.wait_for(
                    outbox_task,
                    timeout=APP_STORE_OUTBOX_SHUTDOWN_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                outbox_task.cancel()
                try:
                    await outbox_task
                except asyncio.CancelledError:
                    pass
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


async def _wait_for_outbox_stop(stop_event: asyncio.Event, delay: float) -> bool:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=max(0.01, delay))
    except TimeoutError:
        return False
    return True


async def _app_store_outbox_loop(
    service,
    notifier,
    logger,
    *,
    stop_event: asyncio.Event,
    base_delay: float = 5.0,
    max_delay: float = 60.0,
    wait_for_stop=_wait_for_outbox_stop,
) -> None:
    delay = max(0.01, base_delay)
    maximum = max(delay, max_delay)
    while not stop_event.is_set():
        try:
            await service.deliver_admin_events(notifier)
            delay = max(0.01, base_delay)
            wait_delay = delay
        except Exception:  # noqa: BLE001 - durable outbox retries transient delivery failures
            logger.exception('App Store admin outbox delivery failed')
            wait_delay = delay
            delay = min(maximum, delay * 2)
        if await wait_for_stop(stop_event, wait_delay):
            break
