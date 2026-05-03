from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from src.repositories.storage import connect


ArtifactKind = Literal['pptx', 'pdf', 'docx', 'image', 'txt', 'other']


@dataclass(frozen=True)
class StoredArtifact:
    artifact_id: str
    kind: ArtifactKind
    filename: str
    media_type: str
    path: Path


_LOCK = RLock()


def register_artifact(path: str | Path, kind: ArtifactKind, media_type: str) -> StoredArtifact:
    file_path = Path(path).resolve()
    artifact = StoredArtifact(
        artifact_id=uuid4().hex,
        kind=kind,
        filename=file_path.name,
        media_type=media_type,
        path=file_path,
    )
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                INSERT INTO artifacts (
                    artifact_id,
                    kind,
                    filename,
                    media_type,
                    path,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    artifact.artifact_id,
                    artifact.kind,
                    artifact.filename,
                    artifact.media_type,
                    str(artifact.path),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
    return artifact


def get_artifact(artifact_id: str) -> StoredArtifact | None:
    with _LOCK:
        with closing(connect()) as conn:
            row = conn.execute('SELECT * FROM artifacts WHERE artifact_id = ?', (artifact_id,)).fetchone()
    if row is None:
        return None
    return StoredArtifact(
        artifact_id=str(row['artifact_id']),
        kind=str(row['kind']),
        filename=str(row['filename']),
        media_type=str(row['media_type']),
        path=Path(str(row['path'])).resolve(),
    )
