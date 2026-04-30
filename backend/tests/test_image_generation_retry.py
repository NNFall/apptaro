from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.integrations import text_generation as text_generation_module  # noqa: E402
from src.integrations.text_generation import PresentationGenerationClient  # noqa: E402


class _RetrySuccessReplicateClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_image(self, prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError('temporary failure')
        return 'https://example.invalid/image.png'


class _AlwaysFailReplicateClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_image(self, prompt: str) -> str:
        self.calls += 1
        raise RuntimeError('still failing')


class ImageGenerationRetryTests(unittest.TestCase):
    def test_retries_replicate_before_fallback(self) -> None:
        client = PresentationGenerationClient(
            api_key='',
            base_url='',
            text_model='',
            image_model='',
            image_generation_retries=2,
            image_generation_retry_delay_seconds=0,
        )
        replicate = _RetrySuccessReplicateClient()
        client.replicate_client = replicate

        original_download = text_generation_module._download_file
        original_placeholder = text_generation_module._placeholder_image
        placeholder_calls: list[str] = []

        def _fake_download(url: str, output_path: Path) -> None:
            Path(output_path).write_bytes(b'image-bytes')

        def _fake_placeholder(prompt: str, output_path: Path) -> None:
            placeholder_calls.append(prompt)
            Path(output_path).write_bytes(b'placeholder')

        text_generation_module._download_file = _fake_download
        text_generation_module._placeholder_image = _fake_placeholder
        try:
            with tempfile.TemporaryDirectory() as td:
                out_path = Path(td) / 'image.png'
                result = client.generate_image('prompt', str(out_path))
                self.assertEqual(result, str(out_path))
                self.assertEqual(out_path.read_bytes(), b'image-bytes')
        finally:
            text_generation_module._download_file = original_download
            text_generation_module._placeholder_image = original_placeholder

        self.assertEqual(replicate.calls, 2)
        self.assertEqual(placeholder_calls, [])

    def test_falls_back_after_all_attempts_fail(self) -> None:
        client = PresentationGenerationClient(
            api_key='',
            base_url='',
            text_model='',
            image_model='',
            image_generation_retries=2,
            image_generation_retry_delay_seconds=0,
        )
        replicate = _AlwaysFailReplicateClient()
        client.replicate_client = replicate

        original_placeholder = text_generation_module._placeholder_image
        placeholder_calls: list[str] = []

        def _fake_placeholder(prompt: str, output_path: Path) -> None:
            placeholder_calls.append(prompt)
            Path(output_path).write_bytes(b'placeholder')

        text_generation_module._placeholder_image = _fake_placeholder
        try:
            with tempfile.TemporaryDirectory() as td:
                out_path = Path(td) / 'image.png'
                result = client.generate_image('prompt', str(out_path))
                self.assertEqual(result, str(out_path))
                self.assertEqual(out_path.read_bytes(), b'placeholder')
        finally:
            text_generation_module._placeholder_image = original_placeholder

        self.assertEqual(replicate.calls, 3)
        self.assertEqual(placeholder_calls, ['prompt'])


if __name__ == '__main__':
    unittest.main()
