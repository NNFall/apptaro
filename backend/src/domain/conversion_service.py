from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from src.jobs.file_converter import convert_file
from src.repositories.artifacts import StoredArtifact, register_artifact


@dataclass(frozen=True)
class ConvertedFile:
    conversion_id: str
    source_filename: str
    source_format: str
    target_format: str
    artifact: StoredArtifact


class ConversionService:
    def __init__(self, temp_dir: Path, libreoffice_path: str) -> None:
        self._temp_dir = temp_dir
        self._libreoffice_path = libreoffice_path

    @property
    def temp_dir(self) -> Path:
        return self._temp_dir

    async def convert(
        self,
        input_path: Path,
        target_format: str,
        original_filename: str | None = None,
    ) -> ConvertedFile:
        source_format = input_path.suffix.lower().lstrip('.')
        target = target_format.lower().lstrip('.')
        self._validate_formats(source_format, target)

        conversion_id = uuid4().hex
        job_dir = self._temp_dir / 'conversions' / conversion_id
        job_dir.mkdir(parents=True, exist_ok=True)

        source_filename = original_filename or input_path.name
        base_name = _safe_filename(Path(source_filename).stem)
        source_path = job_dir / f'{base_name}.{source_format}'
        if input_path.resolve() != source_path.resolve():
            source_path.write_bytes(input_path.read_bytes())

        output_path = await asyncio.to_thread(
            convert_file,
            str(source_path),
            target,
            self._libreoffice_path,
            str(job_dir),
        )
        if not output_path:
            raise RuntimeError('Conversion failed')

        artifact = register_artifact(
            output_path,
            kind=target if target in {'pdf', 'docx'} else 'other',
            media_type=_media_type_for(target),
        )
        return ConvertedFile(
            conversion_id=conversion_id,
            source_filename=source_filename,
            source_format=source_format,
            target_format=target,
            artifact=artifact,
        )

    @staticmethod
    def _validate_formats(source_format: str, target_format: str) -> None:
        allowed = {
            ('pdf', 'docx'),
            ('docx', 'pdf'),
            ('pptx', 'pdf'),
        }
        if (source_format, target_format) not in allowed:
            raise ValueError(f'Unsupported conversion: {source_format} -> {target_format}')


def _safe_filename(value: str) -> str:
    base = value.strip()
    base = re.sub(r'[^A-Za-z0-9 _.-]+', ' ', base)
    base = re.sub(r'\s+', ' ', base).strip()
    return base or 'file'


def _media_type_for(ext: str) -> str:
    if ext == 'pdf':
        return 'application/pdf'
    if ext == 'docx':
        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return 'application/octet-stream'
