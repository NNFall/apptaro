from __future__ import annotations

import asyncio
import json
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Literal
from uuid import uuid4

from src.repositories.storage import connect


JobStatus = Literal['queued', 'running', 'succeeded', 'failed']
JobType = Literal['presentation_render', 'file_conversion']


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StoredJob:
    job_id: str
    job_type: JobType
    status: JobStatus
    input_data: dict[str, Any]
    created_at: str
    updated_at: str
    error: str | None = None
    result: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)


_TASKS: dict[str, Any] = {}
_LOCK = RLock()


def create_job(job_type: JobType, input_data: dict[str, Any], meta: dict[str, Any] | None = None) -> StoredJob:
    job = StoredJob(
        job_id=uuid4().hex,
        job_type=job_type,
        status='queued',
        input_data=input_data,
        created_at=_now(),
        updated_at=_now(),
        meta=meta or {},
    )
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                INSERT INTO jobs (
                    job_id,
                    job_type,
                    status,
                    input_data,
                    created_at,
                    updated_at,
                    error,
                    result,
                    meta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    job.job_id,
                    job.job_type,
                    job.status,
                    json.dumps(job.input_data, ensure_ascii=False),
                    job.created_at,
                    job.updated_at,
                    job.error,
                    None,
                    json.dumps(job.meta, ensure_ascii=False),
                ),
            )
            conn.commit()
    return job


def get_job(job_id: str) -> StoredJob | None:
    with _LOCK:
        with closing(connect()) as conn:
            row = conn.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,)).fetchone()
    return _row_to_job(row)


def mark_job_running(job_id: str) -> StoredJob | None:
    with _LOCK:
        with closing(connect()) as conn:
            cursor = conn.execute(
                'UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?',
                ('running', _now(), job_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
    return get_job(job_id)


def mark_job_succeeded(job_id: str, result: dict[str, Any]) -> StoredJob | None:
    with _LOCK:
        with closing(connect()) as conn:
            cursor = conn.execute(
                'UPDATE jobs SET status = ?, result = ?, error = ?, updated_at = ? WHERE job_id = ?',
                ('succeeded', json.dumps(result, ensure_ascii=False), None, _now(), job_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
    return get_job(job_id)


def mark_job_failed(job_id: str, error: str) -> StoredJob | None:
    with _LOCK:
        with closing(connect()) as conn:
            cursor = conn.execute(
                'UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE job_id = ?',
                ('failed', error, _now(), job_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
    return get_job(job_id)


def attach_task(job_id: str, task: Any) -> None:
    with _LOCK:
        _TASKS[job_id] = task

    if hasattr(task, 'add_done_callback'):
        def _cleanup(_task: asyncio.Task[Any]) -> None:
            with _LOCK:
                _TASKS.pop(job_id, None)

        task.add_done_callback(_cleanup)


def fail_incomplete_jobs(reason: str = 'Backend restarted before job completed') -> int:
    with _LOCK:
        with closing(connect()) as conn:
            cursor = conn.execute(
                '''
                UPDATE jobs
                SET status = ?, error = ?, updated_at = ?
                WHERE status IN ('queued', 'running')
                ''',
                ('failed', reason, _now()),
            )
            conn.commit()
            return max(cursor.rowcount, 0)


def _row_to_job(row) -> StoredJob | None:
    if row is None:
        return None
    return StoredJob(
        job_id=str(row['job_id']),
        job_type=str(row['job_type']),
        status=str(row['status']),
        input_data=_load_json_object(row['input_data']),
        created_at=str(row['created_at']),
        updated_at=str(row['updated_at']),
        error=row['error'],
        result=_load_json_object(row['result']) if row['result'] else None,
        meta=_load_json_object(row['meta']),
    )


def _load_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
