from __future__ import annotations

import base64
import sys
import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.dependencies import (  # noqa: E402
    get_billing_service,
    get_conversion_service,
    get_outline_service,
    get_render_service,
)
from src.domain.conversion_service import ConversionService, ConvertedFile  # noqa: E402
from src.domain.presentation_outline_service import PresentationOutlineService  # noqa: E402
from src.domain.presentation_render_service import PresentationRenderService  # noqa: E402
from src.main import create_app  # noqa: E402
from src.repositories.artifacts import register_artifact  # noqa: E402


PNG_1X1 = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8BvYcAAAAASUVORK5CYII='
)


class StubGenerationClient:
    def generate_title(self, topic: str) -> str:
        return f'Презентация: {topic[:40]}'

    def generate_outline(self, topic: str, slides: int) -> list[str]:
        return [f'Раздел {index}: {topic}' for index in range(1, slides + 1)]

    def revise_outline(self, topic: str, slides: int, outline: list[str], comment: str) -> list[str]:
        revised = outline[:slides]
        if revised:
            revised[0] = f'{revised[0]} ({comment})'
        return revised

    def generate_slide_contents(self, topic: str, outline: list[str]) -> list[dict[str, str]]:
        return [
            {
                'title': item,
                'text': f'Краткий текст по теме "{topic}" для блока "{item}".',
                'image_prompt': f'Иллюстрация для {item}',
            }
            for item in outline
        ]

    def generate_image(self, prompt: str, out_path: str) -> str:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG_1X1)
        return str(path)


class StubConversionService(ConversionService):
    def __init__(self, temp_dir: Path) -> None:
        super().__init__(temp_dir=temp_dir, libreoffice_path='soffice')

    async def convert(
        self,
        input_path: Path,
        target_format: str,
        original_filename: str | None = None,
    ) -> ConvertedFile:
        target = target_format.lower().lstrip('.')
        conversion_id = uuid4().hex
        job_dir = self.temp_dir / 'conversions' / conversion_id
        job_dir.mkdir(parents=True, exist_ok=True)

        source_filename = original_filename or input_path.name
        source_format = input_path.suffix.lower().lstrip('.')
        output_path = job_dir / f'{Path(source_filename).stem}.{target}'
        output_path.write_bytes(b'%PDF-1.4\n% stub conversion artifact\n')

        artifact = register_artifact(
            output_path,
            kind='pdf' if target == 'pdf' else 'other',
            media_type='application/pdf' if target == 'pdf' else 'application/octet-stream',
        )
        return ConvertedFile(
            conversion_id=conversion_id,
            source_filename=source_filename,
            source_format=source_format,
            target_format=target,
            artifact=artifact,
        )


class StubBillingService:
    async def can_start_generation(self, client_id: str) -> bool:
        return True

    async def consume_generation(self, client_id: str) -> bool:
        return True


class BackendApiSmokeTests(unittest.TestCase):
    client_headers = {
        'X-AppSlides-Client-Id': 'appslides_test_client',
    }

    def setUp(self) -> None:
        self.temp_dir_context = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temp_dir_context.name)
        self.templates_dir = BACKEND_DIR.parent / 'telegrambot' / 'media' / 'templates'
        self.stub_generation_client = StubGenerationClient()

        app = create_app()
        app.dependency_overrides[get_outline_service] = lambda: PresentationOutlineService(self.stub_generation_client)
        app.dependency_overrides[get_render_service] = lambda: PresentationRenderService(
            generation_client=self.stub_generation_client,
            temp_dir=self.temp_dir,
            templates_dir=self.templates_dir,
            libreoffice_path='soffice',
            image_concurrency=2,
        )
        app.dependency_overrides[get_conversion_service] = lambda: StubConversionService(self.temp_dir)
        app.dependency_overrides[get_billing_service] = lambda: StubBillingService()

        self.app = app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        self.temp_dir_context.cleanup()

    def test_health_and_templates(self) -> None:
        health = self.client.get('/v1/health')
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()['status'], 'ok')

        templates = self.client.get('/v1/templates/presentation')
        self.assertEqual(templates.status_code, 200)
        payload = templates.json()
        self.assertGreaterEqual(len(payload['templates']), 4)
        self.assertTrue(any(item['template_available'] for item in payload['templates']))

    def test_outline_generation(self) -> None:
        response = self.client.post(
            '/v1/presentations/outline',
            json={
                'topic': 'Тестовая тема',
                'slides_total': 6,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['title'], 'Презентация: Тестовая тема')
        self.assertEqual(payload['slides_total'], 6)
        self.assertEqual(payload['content_slides'], 5)
        self.assertEqual(len(payload['outline']), 5)

    def test_presentation_job_download_routes(self) -> None:
        create_response = self.client.post(
            '/v1/presentations/jobs',
            json={
                'topic': 'Тема презентации',
                'title': 'Готовый файл',
                'outline': ['Вступление', 'Основная часть', 'Выводы'],
                'design_id': 1,
                'generate_pdf': False,
            },
            headers=self.client_headers,
        )
        self.assertEqual(create_response.status_code, 202)
        job_id = create_response.json()['job_id']

        job = self._wait_for_job(f'/v1/presentations/jobs/{job_id}')
        self.assertEqual(job['status'], 'succeeded')

        pptx = self.client.get(f'/v1/presentations/jobs/{job_id}/download/pptx')
        self.assertEqual(pptx.status_code, 200)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            pptx.headers.get('content-type', ''),
        )
        self.assertGreater(len(pptx.content), 0)

        pdf = self.client.get(f'/v1/presentations/jobs/{job_id}/download/pdf')
        self.assertEqual(pdf.status_code, 404)

    def test_conversion_job_download_route(self) -> None:
        source_path = self.templates_dir / 'design_1.pptx'
        with source_path.open('rb') as source_file:
            create_response = self.client.post(
                '/v1/conversions/jobs',
                files={
                    'file': (
                        'design_1.pptx',
                        source_file,
                        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    )
                },
                data={'target_format': 'pdf'},
            )

        self.assertEqual(create_response.status_code, 202)
        job_id = create_response.json()['job_id']

        job = self._wait_for_job(f'/v1/conversions/jobs/{job_id}')
        self.assertEqual(job['status'], 'succeeded')

        download = self.client.get(f'/v1/conversions/jobs/{job_id}/download')
        self.assertEqual(download.status_code, 200)
        self.assertIn('application/pdf', download.headers.get('content-type', ''))
        self.assertGreater(len(download.content), 0)

    def _wait_for_job(self, path: str) -> dict[str, object]:
        deadline = time.time() + 30
        while time.time() < deadline:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            if payload['status'] in {'succeeded', 'failed'}:
                return payload
            time.sleep(0.1)
        self.fail(f'Job did not finish in time: {path}')


if __name__ == '__main__':
    unittest.main()
