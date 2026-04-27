from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from src.integrations.text_generation import PresentationGenerationClient
from src.jobs.file_converter import convert_file
from src.jobs.pptx_builder import build_presentation
from src.repositories.artifacts import StoredArtifact, register_artifact


@dataclass(frozen=True)
class RenderedPresentation:
    presentation_id: str
    title: str
    design_id: int
    slides_total: int
    content_slides: int
    artifacts: list[StoredArtifact]


class PresentationRenderService:
    def __init__(
        self,
        generation_client: PresentationGenerationClient,
        temp_dir: Path,
        templates_dir: Path,
        libreoffice_path: str,
        image_concurrency: int = 5,
    ) -> None:
        self._generation_client = generation_client
        self._temp_dir = temp_dir
        self._templates_dir = templates_dir
        self._libreoffice_path = libreoffice_path
        self._image_concurrency = max(1, image_concurrency)

    async def render(
        self,
        topic: str,
        title: str,
        outline: list[str],
        design_id: int,
        generate_pdf: bool = True,
    ) -> RenderedPresentation:
        template_path = self._templates_dir / f'design_{design_id}.pptx'
        if not template_path.exists():
            raise FileNotFoundError(f'Template design_{design_id}.pptx not found')

        presentation_id = uuid4().hex
        job_dir = self._temp_dir / 'presentations' / presentation_id
        images_dir = job_dir / 'images'
        job_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

        content_slides = len(outline)
        slide_contents = await asyncio.to_thread(
            self._generation_client.generate_slide_contents,
            topic,
            outline,
        )

        semaphore = asyncio.Semaphore(self._image_concurrency)

        async def build_payload(index: int, slide: dict[str, str]) -> dict[str, str]:
            async with semaphore:
                image_path = images_dir / f'{index:02d}_{uuid4().hex}.png'
                generated_image = await asyncio.to_thread(
                    self._generation_client.generate_image,
                    slide.get('image_prompt', ''),
                    str(image_path),
                )
            return {
                'title': slide.get('title', f'Слайд {index}'),
                'text': slide.get('text', ''),
                'image_path': generated_image,
            }

        content_payloads = await asyncio.gather(
            *(build_payload(index, slide) for index, slide in enumerate(slide_contents, start=1))
        )

        slides_payload: list[dict[str, str | None]] = [{'title': title, 'text': '', 'image_path': None}]
        slides_payload.extend(content_payloads)

        base_name = _safe_filename(title) or 'presentation'
        pptx_path = job_dir / f'{base_name}.pptx'
        await asyncio.to_thread(
            build_presentation,
            str(template_path),
            slides_payload,
            str(pptx_path),
        )

        artifacts: list[StoredArtifact] = [
            register_artifact(
                pptx_path,
                kind='pptx',
                media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            )
        ]

        if generate_pdf:
            pdf_path = await asyncio.to_thread(
                convert_file,
                str(pptx_path),
                'pdf',
                self._libreoffice_path,
                str(job_dir),
            )
            if pdf_path:
                artifacts.append(
                    register_artifact(
                        pdf_path,
                        kind='pdf',
                        media_type='application/pdf',
                    )
                )

        return RenderedPresentation(
            presentation_id=presentation_id,
            title=title,
            design_id=design_id,
            slides_total=content_slides + 1,
            content_slides=content_slides,
            artifacts=artifacts,
        )


def _safe_filename(value: str) -> str:
    base = value.strip()
    base = re.sub(r'[^A-Za-zА-Яа-я0-9 _-]+', ' ', base)
    base = re.sub(r'\s+', ' ', base).strip()
    if not base:
        return 'presentation'
    if len(base) > 60:
        base = base[:57].rstrip() + '...'
    return base
