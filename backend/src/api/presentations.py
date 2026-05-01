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


@router.post('/outline', response_model=OutlineResponse)
async def generate_outline(
    payload: OutlineGenerateRequest,
    service: PresentationOutlineService = Depends(get_outline_service),
    client_id: str = Depends(get_known_client_id),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> OutlineResponse:
    try:
        result = await service.generate(payload.topic, payload.slides_total)
    except TextGenerationError as exc:
        await notifier.notify_text_error(client_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    await notifier.notify_outline_created(client_id, payload.topic, result.content_slides)
    return OutlineResponse(
        title=result.title,
        outline=result.outline,
        slides_total=result.slides_total,
        content_slides=result.content_slides,
    )


@router.post('/outline/revise', response_model=OutlineResponse)
async def revise_outline(
    payload: OutlineReviseRequest,
    service: PresentationOutlineService = Depends(get_outline_service),
    client_id: str = Depends(get_known_client_id),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> OutlineResponse:
    try:
        result = await service.revise(
            topic=payload.topic,
            slides_total=payload.slides_total,
            outline=payload.outline,
            comment=payload.comment,
            title=payload.title,
        )
    except TextGenerationError as exc:
        await notifier.notify_text_error(client_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    await notifier.notify_outline_updated(client_id, payload.topic, result.content_slides)
    return OutlineResponse(
        title=result.title,
        outline=result.outline,
        slides_total=result.slides_total,
        content_slides=result.content_slides,
    )


@router.post('/render', response_model=PresentationRenderResponse)
async def render_presentation(
    payload: PresentationRenderRequest,
    service: PresentationRenderService = Depends(get_render_service),
    billing_service: BillingService = Depends(get_billing_service),
    client_id: str = Depends(get_known_client_id),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> PresentationRenderResponse:
    if not await billing_service.can_start_generation(client_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail='Лимит генераций исчерпан. Оформите подписку через YooKassa.',
        )

    try:
        result = await service.render(
            topic=payload.topic,
            title=payload.title,
            outline=payload.outline,
            design_id=payload.design_id,
            generate_pdf=payload.generate_pdf,
        )
    except FileNotFoundError as exc:
        await notifier.notify_generation_failed(client_id, str(exc))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TextGenerationError as exc:
        await notifier.notify_generation_failed(client_id, str(exc))
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        await notifier.notify_generation_failed(client_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to render presentation: {exc}',
        ) from exc

    if not await billing_service.consume_generation(client_id):
        error_text = 'Не удалось списать генерацию после успешного рендера.'
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
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> JobResponse:
    if not await billing_service.can_start_generation(client_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail='Лимит генераций исчерпан. Оформите подписку через YooKassa.',
        )

    job = create_job(
        'presentation_render',
        input_data={
            'topic': payload.topic,
            'title': payload.title,
            'outline': payload.outline,
            'design_id': payload.design_id,
            'generate_pdf': payload.generate_pdf,
            'client_id': client_id,
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


async def _run_presentation_job(
    job_id: str,
    service: PresentationRenderService,
    payload: PresentationRenderRequest,
    billing_service: BillingService,
    client_id: str,
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
        )
    except Exception as exc:
        mark_job_failed(job_id, str(exc))
        await notifier.notify_generation_failed(client_id, str(exc))
        return

    if not await billing_service.consume_generation(client_id):
        error_text = 'Не удалось списать генерацию после успешного рендера.'
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
    notifier: AdminNotifier,
) -> None:
    asyncio.run(
        _run_presentation_job(
            job_id=job_id,
            service=service,
            payload=payload,
            billing_service=billing_service,
            client_id=client_id,
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
