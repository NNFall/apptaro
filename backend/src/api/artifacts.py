from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from src.repositories.artifacts import get_artifact


router = APIRouter(prefix='/v1/artifacts', tags=['artifacts'])


def build_artifact_response(artifact_id: str) -> FileResponse:
    artifact = get_artifact(artifact_id)
    if artifact is None or not artifact.path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Artifact not found',
        )
    return FileResponse(
        path=artifact.path,
        media_type=artifact.media_type,
        filename=artifact.filename,
    )


@router.get('/{artifact_id}')
async def download_artifact(artifact_id: str) -> FileResponse:
    return build_artifact_response(artifact_id)
