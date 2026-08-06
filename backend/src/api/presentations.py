from __future__ import annotations

import asyncio
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from src.api.artifacts import build_artifact_response
from src.core.dependencies import (
    get_admin_notifier,
    get_billing_service,
    get_known_client_id,
    get_outline_service,
    get_request_language,
    get_render_service,
)
from src.domain.billing_service import BillingService
from src.domain.presentation_outline_service import PresentationOutlineService
from src.domain.presentation_render_service import PresentationRenderService
from src.integrations.admin_notifier import AdminNotifier
from src.integrations.text_generation import TextGenerationError
from src.repositories.jobs import (
    attach_task,
    create_job,
    get_job,
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
)
from src.schemas.artifacts import ArtifactItem
from src.schemas.jobs import JobResponse
from src.schemas.presentation import (
    OutlineGenerateRequest,
    OutlineResponse,
    OutlineReviseRequest,
    PresentationRenderRequest,
    PresentationRenderResponse,
)


router = APIRouter(prefix='/v1/presentations', tags=['presentations'])


def _localized(language: str, *, en: str, ru: str) -> str:
    return ru if language == 'ru' else en


def _reading_limit_error(language: str) -> str:
    return _localized(
        language,
        en='Your reading limit is over. Choose a subscription to continue.',
        ru='Лимит раскладов исчерпан. Выберите подписку, чтобы продолжить.',
    )


def _charge_error(language: str) -> str:
    return _localized(
        language,
        en='Failed to charge one reading after successful generation.',
        ru='Не удалось списать один расклад после успешной генерации.',
    )


def _missing_render_asset_error(language: str) -> str:
    return _localized(
        language,
        en='Required tarot reading files were not found. Please try again later.',
        ru='\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043d\u0430\u0439\u0442\u0438 \u043d\u0443\u0436\u043d\u044b\u0435 \u0444\u0430\u0439\u043b\u044b \u0434\u043b\u044f \u0440\u0430\u0441\u043a\u043b\u0430\u0434\u0430. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u043e\u0437\u0436\u0435.',
    )


def _text_generation_error(language: str) -> str:
    return _localized(
        language,
        en='Failed to generate the tarot reading. Please try again.',
        ru='\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u0433\u0435\u043d\u0435\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0440\u0430\u0441\u043a\u043b\u0430\u0434. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0451 \u0440\u0430\u0437.',
    )


def _render_error(language: str) -> str:
    return _localized(
        language,
        en='Failed to render the tarot reading. Please try again.',
        ru='\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0431\u0440\u0430\u0442\u044c \u0440\u0430\u0441\u043a\u043b\u0430\u0434. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0451 \u0440\u0430\u0437.',
    )


def _safe_render_error(language: str, exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return _missing_render_asset_error(language)
    if isinstance(exc, TextGenerationError):
        return _text_generation_error(language)
    return _render_error(language)


@router.post('/outline', response_model=OutlineResponse)
async def generate_outline(
    payload: OutlineGenerateRequest,
    service: PresentationOutlineService = Depends(get_outline_service),
    render_service: PresentationRenderService = Depends(get_render_service),
    billing_service: BillingService = Depends(get_billing_service),
    client_id: str = Depends(get_known_client_id),
    language: str = Depends(get_request_language),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> OutlineResponse:
    teaser_mode = await billing_service.should_show_trial_teaser(client_id)
    if not teaser_mode and not await billing_service.can_start_generation(client_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=_reading_limit_error(language),
        )
    cards_count = 1 if teaser_mode else 3
    try:
        result = await service.generate(
            payload.topic,
            payload.slides_total,
            cards_count=cards_count,
            language=language,
        )
    except TextGenerationError as exc:
        await notifier.notify_text_error(client_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    teaser_text: str | None = None
    teaser_artifacts: list[ArtifactItem] = []
    if teaser_mode:
        try:
            teaser = await render_service.render_teaser(
                topic=payload.topic,
                title=result.title,
                outline=result.outline,
                language=language,
            )
            teaser_text = teaser.text
            teaser_artifacts = [
                ArtifactItem(
                    artifact_id=teaser.image_artifact.artifact_id,
                    kind=teaser.image_artifact.kind,
                    filename=teaser.image_artifact.filename,
                    media_type=teaser.image_artifact.media_type,
                    download_url=f'/v1/artifacts/{teaser.image_artifact.artifact_id}',
                )
            ]
        except Exception as exc:  # noqa: BLE001
            await notifier.notify_generation_failed(client_id, f'teaser image error: {exc}')
        finally:
            billing_service.mark_trial_teaser_used(client_id)

    await notifier.notify_outline_created(client_id, payload.topic, result.content_slides)
    return OutlineResponse(
        title=result.title,
        outline=result.outline,
        slides_total=result.slides_total,
        content_slides=result.content_slides,
        teaser_mode=teaser_mode,
        teaser_text=teaser_text,
        teaser_artifacts=teaser_artifacts,
    )


@router.post('/outline/revise', response_model=OutlineResponse)
async def revise_outline(
    payload: OutlineReviseRequest,
    service: PresentationOutlineService = Depends(get_outline_service),
    render_service: PresentationRenderService = Depends(get_render_service),
    billing_service: BillingService = Depends(get_billing_service),
    client_id: str = Depends(get_known_client_id),
    language: str = Depends(get_request_language),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> OutlineResponse:
    if not await billing_service.can_start_generation(client_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=_reading_limit_error(language),
        )
    teaser_mode = False
    cards_count = 3
    try:
        result = await service.revise(
            topic=payload.topic,
            slides_total=payload.slides_total,
            outline=payload.outline,
            comment=payload.comment,
            title=payload.title,
            cards_count=cards_count,
            language=language,
        )
    except TextGenerationError as exc:
        await notifier.notify_text_error(client_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    teaser_text: str | None = None
    teaser_artifacts: list[ArtifactItem] = []
    if teaser_mode:
        try:
            teaser = await render_service.render_teaser(
                topic=payload.topic,
                title=result.title,
                outline=result.outline,
                language=language,
            )
            teaser_text = teaser.text
            teaser_artifacts = [
                ArtifactItem(
                    artifact_id=teaser.image_artifact.artifact_id,
                    kind=teaser.image_artifact.kind,
                    filename=teaser.image_artifact.filename,
                    media_type=teaser.image_artifact.media_type,
                    download_url=f'/v1/artifacts/{teaser.image_artifact.artifact_id}',
                )
            ]
        except Exception as exc:  # noqa: BLE001
            await notifier.notify_generation_failed(client_id, f'teaser image error: {exc}')

    await notifier.notify_outline_updated(client_id, payload.topic, result.content_slides)
    return OutlineResponse(
        title=result.title,
        outline=result.outline,
        slides_total=result.slides_total,
        content_slides=result.content_slides,
        teaser_mode=teaser_mode,
        teaser_text=teaser_text,
        teaser_artifacts=teaser_artifacts,
    )


@router.post('/render', response_model=PresentationRenderResponse)
async def render_presentation(
    payload: PresentationRenderRequest,
    service: PresentationRenderService = Depends(get_render_service),
    billing_service: BillingService = Depends(get_billing_service),
    client_id: str = Depends(get_known_client_id),
    language: str = Depends(get_request_language),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> PresentationRenderResponse:
    if not await billing_service.can_start_generation(client_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=_reading_limit_error(language),
        )

    try:
        result = await service.render(
            topic=payload.topic,
            title=payload.title,
            outline=payload.outline,
            design_id=payload.design_id,
            generate_pdf=payload.generate_pdf,
            teaser_first_text=payload.teaser_first_text,
            language=language,
        )
    except FileNotFoundError as exc:
        await notifier.notify_generation_failed(client_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_missing_render_asset_error(language),
        ) from exc
    except TextGenerationError as exc:
        await notifier.notify_generation_failed(client_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_text_generation_error(language),
        ) from exc
    except Exception as exc:
        await notifier.notify_generation_failed(client_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_render_error(language),
        ) from exc

    if not await billing_service.consume_generation(client_id):
        error_text = _charge_error(language)
        await notifier.notify_generation_failed(client_id, error_text)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_text,
        )

    await notifier.notify_generation_success(client_id)
    artifacts = [
        ArtifactItem(
            artifact_id=artifact.artifact_id,
            kind=artifact.kind,
            filename=artifact.filename,
            media_type=artifact.media_type,
            download_url=f'/v1/artifacts/{artifact.artifact_id}',
        )
        for artifact in result.artifacts
    ]
    return PresentationRenderResponse(
        presentation_id=result.presentation_id,
        title=result.title,
        design_id=result.design_id,
        slides_total=result.slides_total,
        content_slides=result.content_slides,
        artifacts=artifacts,
    )


@router.post('/jobs', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_presentation_job(
    payload: PresentationRenderRequest,
    service: PresentationRenderService = Depends(get_render_service),
    billing_service: BillingService = Depends(get_billing_service),
    client_id: str = Depends(get_known_client_id),
    language: str = Depends(get_request_language),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> JobResponse:
    if not await billing_service.can_start_generation(client_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=_reading_limit_error(language),
        )

    job = create_job(
        'presentation_render',
        input_data={
            'topic': payload.topic,
            'title': payload.title,
            'outline': payload.outline,
            'design_id': payload.design_id,
            'generate_pdf': payload.generate_pdf,
            'teaser_first_text': payload.teaser_first_text,
            'client_id': client_id,
            'language': language,
        },
    )
    task = Thread(
        target=_run_presentation_job_sync,
        kwargs={
            'job_id': job.job_id,
            'service': service,
            'payload': payload,
            'billing_service': billing_service,
            'client_id': client_id,
            'language': language,
            'notifier': notifier,
        },
        daemon=True,
    )
    task.start()
    attach_task(job.job_id, task)
    stored = get_job(job.job_id)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Failed to create job')
    return _job_response(stored)


@router.get('/jobs/{job_id}', response_model=JobResponse)
async def get_presentation_job(job_id: str) -> JobResponse:
    job = _get_presentation_job_or_404(job_id)
    return _job_response(job)


@router.get('/jobs/{job_id}/download/pptx')
async def download_presentation_pptx(job_id: str) -> FileResponse:
    artifact_id = _get_presentation_artifact_id(job_id, 'pptx')
    return build_artifact_response(artifact_id)


@router.get('/jobs/{job_id}/download/pdf')
async def download_presentation_pdf(job_id: str) -> FileResponse:
    artifact_id = _get_presentation_artifact_id(job_id, 'pdf')
    return build_artifact_response(artifact_id)


@router.get('/jobs/{job_id}/download/image')
async def download_presentation_image(job_id: str) -> FileResponse:
    artifact_id = _get_presentation_artifact_id(job_id, 'image')
    return build_artifact_response(artifact_id)


@router.get('/jobs/{job_id}/download/txt')
async def download_presentation_txt(job_id: str) -> FileResponse:
    artifact_id = _get_presentation_artifact_id(job_id, 'txt')
    return build_artifact_response(artifact_id)


async def _run_presentation_job(
    job_id: str,
    service: PresentationRenderService,
    payload: PresentationRenderRequest,
    billing_service: BillingService,
    client_id: str,
    language: str,
    notifier: AdminNotifier,
) -> None:
    mark_job_running(job_id)
    try:
        result = await service.render(
            topic=payload.topic,
            title=payload.title,
            outline=payload.outline,
            design_id=payload.design_id,
            generate_pdf=payload.generate_pdf,
            teaser_first_text=payload.teaser_first_text,
            language=language,
        )
    except Exception as exc:
        mark_job_failed(job_id, _safe_render_error(language, exc))
        await notifier.notify_generation_failed(client_id, str(exc))
        return

    if not await billing_service.consume_generation(client_id):
        error_text = _charge_error(language)
        mark_job_failed(job_id, error_text)
        await notifier.notify_generation_failed(client_id, error_text)
        return

    artifacts = [
        {
            'artifact_id': artifact.artifact_id,
            'kind': artifact.kind,
            'filename': artifact.filename,
            'media_type': artifact.media_type,
            'download_url': f'/v1/artifacts/{artifact.artifact_id}',
        }
        for artifact in result.artifacts
    ]
    mark_job_succeeded(
        job_id,
        {
            'presentation_id': result.presentation_id,
            'title': result.title,
            'design_id': result.design_id,
            'slides_total': result.slides_total,
            'content_slides': result.content_slides,
            'reading_text': result.reading_text,
            'artifacts': artifacts,
        },
    )
    await notifier.notify_generation_success(client_id)


def _run_presentation_job_sync(
    job_id: str,
    service: PresentationRenderService,
    payload: PresentationRenderRequest,
    billing_service: BillingService,
    client_id: str,
    language: str,
    notifier: AdminNotifier,
) -> None:
    asyncio.run(
        _run_presentation_job(
            job_id=job_id,
            service=service,
            payload=payload,
            billing_service=billing_service,
            client_id=client_id,
            language=language,
            notifier=notifier,
        )
    )


def _job_response(job) -> JobResponse:
    return JobResponse(
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error=job.error,
        result=job.result,
    )


def _get_presentation_job_or_404(job_id: str):
    job = get_job(job_id)
    if job is None or job.job_type != 'presentation_render':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job not found')
    return job


def _get_presentation_artifact_id(job_id: str, artifact_kind: str) -> str:
    job = _get_presentation_job_or_404(job_id)
    if job.status != 'succeeded' or not job.result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'Job is not ready for download: {job.status}',
        )

    for artifact in job.result.get('artifacts', []):
        if artifact.get('kind') == artifact_kind and artifact.get('artifact_id'):
            return str(artifact['artifact_id'])

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f'{artifact_kind.upper()} artifact not found for this job',
    )
