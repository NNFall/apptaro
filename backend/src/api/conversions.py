from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Thread

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from src.api.artifacts import build_artifact_response
from src.core.dependencies import get_admin_notifier, get_conversion_service, get_known_client_id
from src.domain.conversion_service import ConversionService
from src.integrations.admin_notifier import AdminNotifier
from src.repositories.jobs import (
    attach_task,
    create_job,
    get_job,
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
)
from src.schemas.jobs import JobResponse


router = APIRouter(prefix='/v1/conversions', tags=['conversions'])


@router.post('/jobs', response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_conversion_job(
    file: UploadFile = File(...),
    target_format: str = Form(...),
    service: ConversionService = Depends(get_conversion_service),
    client_id: str = Depends(get_known_client_id),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> JobResponse:
    filename = file.filename or 'file'
    job = create_job(
        'file_conversion',
        input_data={
            'filename': filename,
            'target_format': target_format.lower(),
            'client_id': client_id,
        },
    )

    input_dir = service.temp_dir / 'uploads' / job.job_id
    input_dir.mkdir(parents=True, exist_ok=True)
    source_name = Path(filename).name or 'file'
    input_path = input_dir / source_name
    input_path.write_bytes(await file.read())
    await file.close()

    task = Thread(
        target=_run_conversion_job_sync,
        kwargs={
            'job_id': job.job_id,
            'service': service,
            'input_path': input_path,
            'original_filename': filename,
            'target_format': target_format,
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
async def get_conversion_job(job_id: str) -> JobResponse:
    job = _get_conversion_job_or_404(job_id)
    return _job_response(job)


@router.get('/jobs/{job_id}/download')
async def download_conversion_result(job_id: str) -> FileResponse:
    artifact_id = _get_conversion_artifact_id(job_id)
    return build_artifact_response(artifact_id)


async def _run_conversion_job(
    job_id: str,
    service: ConversionService,
    input_path: Path,
    original_filename: str,
    target_format: str,
    client_id: str,
    notifier: AdminNotifier,
) -> None:
    mark_job_running(job_id)
    source_format = input_path.suffix.lower().lstrip('.').upper() or 'FILE'
    target_label = target_format.lower().lstrip('.').upper() or 'FILE'
    try:
        result = await service.convert(
            input_path=input_path,
            target_format=target_format,
            original_filename=original_filename,
        )
    except Exception as exc:
        mark_job_failed(job_id, str(exc))
        await notifier.notify_conversion_failed(client_id, source_format, target_label, str(exc))
        return

    mark_job_succeeded(
        job_id,
        {
            'conversion_id': result.conversion_id,
            'source_filename': result.source_filename,
            'source_format': result.source_format,
            'target_format': result.target_format,
            'artifact': {
                'artifact_id': result.artifact.artifact_id,
                'kind': result.artifact.kind,
                'filename': result.artifact.filename,
                'media_type': result.artifact.media_type,
                'download_url': f'/v1/artifacts/{result.artifact.artifact_id}',
            },
        },
    )
    await notifier.notify_conversion_success(client_id, source_format, target_label)


def _run_conversion_job_sync(
    job_id: str,
    service: ConversionService,
    input_path: Path,
    original_filename: str,
    target_format: str,
    client_id: str,
    notifier: AdminNotifier,
) -> None:
    asyncio.run(
        _run_conversion_job(
            job_id=job_id,
            service=service,
            input_path=input_path,
            original_filename=original_filename,
            target_format=target_format,
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


def _get_conversion_job_or_404(job_id: str):
    job = get_job(job_id)
    if job is None or job.job_type != 'file_conversion':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job not found')
    return job


def _get_conversion_artifact_id(job_id: str) -> str:
    job = _get_conversion_job_or_404(job_id)
    if job.status != 'succeeded' or not job.result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'Job is not ready for download: {job.status}',
        )

    artifact = job.result.get('artifact') or {}
    artifact_id = artifact.get('artifact_id')
    if artifact_id:
        return str(artifact_id)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail='Artifact not found for this job',
    )
