from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw

from src.core.logging import get_logger
from src.domain.presentation_prompts import (
    outline_comment_prompt,
    outline_prompt,
    slides_prompt,
    title_prompt,
)


class TextGenerationError(RuntimeError):
    """Raised when the AI provider cannot produce a valid result."""


class ReplicateClient:
    def __init__(
        self,
        api_token: str,
        base_url: str,
        model: str,
        wait_seconds: int = 60,
        poll_interval: float = 1.5,
        timeout_seconds: int = 120,
        default_input: dict[str, Any] | None = None,
    ) -> None:
        self.api_token = api_token
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.wait_seconds = wait_seconds
        self.poll_interval = poll_interval
        self.timeout_seconds = timeout_seconds
        self.default_input = default_input or {}
        self.logger = get_logger('appslides.backend.replicate.image')

    def _headers(self, wait: bool = True) -> dict[str, str]:
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }
        if wait and self.wait_seconds > 0:
            wait_value = max(1, min(60, int(self.wait_seconds)))
            headers['Prefer'] = f'wait={wait_value}'
        return headers

    def generate_image(self, prompt: str) -> str:
        url = f'{self.base_url}/v1/models/{self.model}/predictions'
        payload = {
            'input': {
                **self.default_input,
                'prompt': prompt,
            }
        }
        self.logger.info('Replicate image request: model=%s', self.model)
        response = self._post_with_retry(url, payload)
        data = response.json()
        status = data.get('status')
        if status == 'succeeded':
            return _extract_output_url(data.get('output'))
        if status == 'failed':
            raise TextGenerationError(data.get('error') or 'Replicate prediction failed')

        prediction_url = data.get('urls', {}).get('get') or data.get('id')
        if prediction_url and not prediction_url.startswith('http'):
            prediction_url = f'{self.base_url}/v1/predictions/{prediction_url}'
        if not prediction_url:
            raise TextGenerationError('Replicate prediction URL not found')

        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            data = self._poll(prediction_url)
            status = data.get('status')
            if status == 'succeeded':
                return _extract_output_url(data.get('output'))
            if status == 'failed':
                raise TextGenerationError(data.get('error') or 'Replicate prediction failed')
            time.sleep(self.poll_interval)
        raise TimeoutError('Replicate prediction timed out')

    def _poll(self, url: str) -> dict[str, Any]:
        response = self._get_with_retry(url)
        return response.json()

    def _post_with_retry(self, url: str, payload: dict[str, Any]) -> requests.Response:
        delay = 2.0
        for attempt in range(3):
            response = requests.post(url, json=payload, headers=self._headers(), timeout=120)
            if response.status_code != 429:
                response.raise_for_status()
                return response
            retry_after = response.headers.get('Retry-After')
            wait = int(retry_after) if retry_after and retry_after.isdigit() else delay
            self.logger.warning('Replicate image rate limit, retry in %ss (attempt %s)', wait, attempt + 1)
            time.sleep(wait)
            delay = min(delay * 2, 20)
        response.raise_for_status()
        return response

    def _get_with_retry(self, url: str) -> requests.Response:
        delay = 2.0
        for attempt in range(3):
            response = requests.get(url, headers=self._headers(wait=False), timeout=60)
            if response.status_code != 429:
                response.raise_for_status()
                return response
            retry_after = response.headers.get('Retry-After')
            wait = int(retry_after) if retry_after and retry_after.isdigit() else delay
            self.logger.warning('Replicate image rate limit (poll), retry in %ss (attempt %s)', wait, attempt + 1)
            time.sleep(wait)
            delay = min(delay * 2, 20)
        response.raise_for_status()
        return response


class ReplicateTextClient:
    def __init__(
        self,
        api_token: str,
        base_url: str,
        model: str,
        prompt_field: str = 'prompt',
        wait_seconds: int = 60,
        poll_interval: float = 1.5,
        timeout_seconds: int = 120,
        default_input: dict[str, Any] | None = None,
    ) -> None:
        self.api_token = api_token
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.prompt_field = prompt_field or 'prompt'
        self.wait_seconds = wait_seconds
        self.poll_interval = poll_interval
        self.timeout_seconds = timeout_seconds
        self.default_input = default_input or {}
        self.logger = get_logger('appslides.backend.replicate.text')

    def _headers(self, wait: bool = True) -> dict[str, str]:
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }
        if wait and self.wait_seconds > 0:
            wait_value = max(1, min(60, int(self.wait_seconds)))
            headers['Prefer'] = f'wait={wait_value}'
        return headers

    def generate_text(self, prompt: str) -> str:
        url = f'{self.base_url}/v1/models/{self.model}/predictions'
        payload = {
            'input': {
                **self.default_input,
                self.prompt_field: prompt,
            }
        }
        self.logger.info('Replicate text request: model=%s', self.model)
        response = self._post_with_retry(url, payload)
        data = response.json()
        status = data.get('status')
        if status == 'succeeded':
            return _extract_output_text(data.get('output'))
        if status == 'failed':
            raise TextGenerationError(data.get('error') or 'Replicate prediction failed')

        prediction_url = data.get('urls', {}).get('get') or data.get('id')
        if prediction_url and not prediction_url.startswith('http'):
            prediction_url = f'{self.base_url}/v1/predictions/{prediction_url}'
        if not prediction_url:
            raise TextGenerationError('Replicate prediction URL not found')

        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            data = self._poll(prediction_url)
            status = data.get('status')
            if status == 'succeeded':
                return _extract_output_text(data.get('output'))
            if status == 'failed':
                raise TextGenerationError(data.get('error') or 'Replicate prediction failed')
            time.sleep(self.poll_interval)
        raise TimeoutError('Replicate prediction timed out')

    def _poll(self, url: str) -> dict[str, Any]:
        response = self._get_with_retry(url)
        return response.json()

    def _post_with_retry(self, url: str, payload: dict[str, Any]) -> requests.Response:
        delay = 2.0
        for attempt in range(3):
            response = requests.post(url, json=payload, headers=self._headers(), timeout=120)
            if response.status_code != 429:
                response.raise_for_status()
                return response
            retry_after = response.headers.get('Retry-After')
            wait = int(retry_after) if retry_after and retry_after.isdigit() else delay
            self.logger.warning('Replicate text rate limit, retry in %ss (attempt %s)', wait, attempt + 1)
            time.sleep(wait)
            delay = min(delay * 2, 20)
        response.raise_for_status()
        return response

    def _get_with_retry(self, url: str) -> requests.Response:
        delay = 2.0
        for attempt in range(3):
            response = requests.get(url, headers=self._headers(wait=False), timeout=60)
            if response.status_code != 429:
                response.raise_for_status()
                return response
            retry_after = response.headers.get('Retry-After')
            wait = int(retry_after) if retry_after and retry_after.isdigit() else delay
            self.logger.warning('Replicate text rate limit (poll), retry in %ss (attempt %s)', wait, attempt + 1)
            time.sleep(wait)
            delay = min(delay * 2, 20)
        response.raise_for_status()
        return response


class PresentationGenerationClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        text_model: str,
        image_model: str,
        text_endpoint: str = '',
        image_endpoint: str = '',
        text_fallback_models: list[str] | None = None,
        replicate_api_token: str = '',
        replicate_base_url: str = '',
        replicate_model: str = '',
        replicate_default_input: dict[str, Any] | None = None,
        replicate_text_model: str = '',
        replicate_text_prompt_field: str = 'prompt',
        replicate_wait_seconds: int = 60,
        replicate_poll_interval: float = 1.5,
        replicate_timeout_seconds: int = 120,
        replicate_text_default_input: dict[str, Any] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.text_model = text_model
        self.image_model = image_model
        self.text_endpoint = text_endpoint or ''
        self.image_endpoint = image_endpoint or ''
        self._text_endpoint_explicit = bool(self.text_endpoint)
        if not self.text_endpoint and self.base_url and self.text_model:
            self.text_endpoint = f'{self.base_url}/{self.text_model}/v1/chat/completions'
        self.text_fallback_models = text_fallback_models or []
        self.replicate_client = None
        if replicate_api_token and replicate_base_url and replicate_model:
            self.replicate_client = ReplicateClient(
                api_token=replicate_api_token,
                base_url=replicate_base_url,
                model=replicate_model,
                wait_seconds=replicate_wait_seconds,
                poll_interval=replicate_poll_interval,
                timeout_seconds=replicate_timeout_seconds,
                default_input=replicate_default_input,
            )
        self.replicate_text_client = None
        if replicate_api_token and replicate_base_url and replicate_text_model:
            self.replicate_text_client = ReplicateTextClient(
                api_token=replicate_api_token,
                base_url=replicate_base_url,
                model=replicate_text_model,
                prompt_field=replicate_text_prompt_field,
                wait_seconds=replicate_wait_seconds,
                poll_interval=replicate_poll_interval,
                timeout_seconds=replicate_timeout_seconds,
                default_input=replicate_text_default_input,
            )
        self.logger = get_logger('appslides.backend.ai')

    def generate_title(self, topic: str) -> str:
        if not self.api_key or not self.text_endpoint:
            return _fallback_title(topic)

        prompt = title_prompt(topic)
        payload = {'messages': [_build_text_message(prompt)], 'temperature': 0.6}
        try:
            data = self._post(self.text_endpoint, payload)
        except Exception:
            self.logger.exception('Primary title generation failed')
            replicate = self._try_replicate_title(prompt)
            if replicate:
                return replicate
            return _fallback_title(topic)

        content = _extract_content(data)
        err = _error_from_text(content)
        if err:
            self.logger.warning('Title generation returned provider error: %s', err)
            replicate = self._try_replicate_title(prompt)
            if replicate:
                return replicate
            return _fallback_title(topic)

        title = _clean_title(content)
        return title or _fallback_title(topic)

    def generate_outline(self, topic: str, slides: int) -> list[str]:
        if not self.api_key or not self.text_endpoint:
            return [f'Слайд {index}: {topic}' for index in range(1, slides + 1)]

        prompt = outline_prompt(topic, slides)
        payload = {'messages': [_build_text_message(prompt)], 'temperature': 0.6}
        return self._generate_lines(prompt, payload, slides)

    def revise_outline(self, topic: str, slides: int, outline: list[str], comment: str) -> list[str]:
        if not self.api_key or not self.text_endpoint:
            return outline[:slides]

        prompt = outline_comment_prompt(topic, slides, outline, comment)
        payload = {'messages': [_build_text_message(prompt)], 'temperature': 0.6}
        return self._generate_lines(prompt, payload, slides)

    def generate_slide_contents(self, topic: str, outline: list[str]) -> list[dict[str, str]]:
        if not self.api_key or not self.text_endpoint:
            return [
                {
                    'title': title,
                    'text': f'Краткий текст по теме: {topic}.',
                    'image_prompt': f'Иллюстрация: {title}.',
                }
                for title in outline
            ]

        prompt = slides_prompt(topic, outline)
        payload = {'messages': [_build_text_message(prompt)], 'temperature': 0.6}
        try:
            data = self._post(self.text_endpoint, payload)
        except Exception:
            self.logger.exception('Primary slide content generation failed')
            replicate = self._try_replicate_slides(prompt)
            if replicate is not None:
                return replicate
            fallback = self._fallback_slides(topic, outline)
            return fallback

        content = _extract_content(data)
        err = _error_from_text(content)
        if err:
            self.logger.warning('Slides generation returned provider error: %s', err)
            replicate = self._try_replicate_slides(prompt)
            if replicate is not None:
                return replicate
            return self._fallback_slides(topic, outline)

        slides = _parse_json_list(content)
        if slides:
            return slides

        replicate = self._try_replicate_slides(prompt)
        if replicate is not None:
            return replicate
        return self._fallback_slides(topic, outline)

    def generate_image(self, prompt: str, out_path: str) -> str:
        output_path = Path(out_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.replicate_client:
            try:
                image_url = self.replicate_client.generate_image(prompt)
                _download_file(image_url, output_path)
                return str(output_path)
            except Exception:
                self.logger.exception('Replicate image generation failed')
                _placeholder_image(prompt, output_path)
                return str(output_path)

        if not self.api_key or not self.image_endpoint:
            _placeholder_image(prompt, output_path)
            return str(output_path)

        payload = {
            'model': self.image_model,
            'prompt': prompt,
            'size': '1024x1024',
        }
        try:
            data = self._post(self.image_endpoint, payload)
        except Exception:
            self.logger.exception('Primary image generation failed')
            _placeholder_image(prompt, output_path)
            return str(output_path)

        image_url = _extract_image_url(data)
        if image_url:
            _download_file(image_url, output_path)
            return str(output_path)

        image_b64 = _extract_image_b64(data)
        if image_b64:
            output_path.write_bytes(base64.b64decode(image_b64))
            return str(output_path)

        _placeholder_image(prompt, output_path)
        return str(output_path)

    def _generate_lines(self, prompt: str, payload: dict[str, Any], slides: int) -> list[str]:
        try:
            data = self._post(self.text_endpoint, payload)
        except Exception as exc:
            self.logger.exception('Primary outline generation failed')
            replicate = self._try_replicate_outline(prompt, slides)
            if replicate is not None:
                return replicate
            fallback = self._try_fallback_outline(payload, slides)
            if fallback is not None:
                return fallback
            raise TextGenerationError('Сервис временно недоступен, попробуйте позже.') from exc

        content = _extract_content(data)
        err = _error_from_text(content)
        if err:
            self.logger.warning('Outline generation returned provider error: %s', err)
            replicate = self._try_replicate_outline(prompt, slides)
            if replicate is not None:
                return replicate
            fallback = self._try_fallback_outline(payload, slides)
            if fallback is not None:
                return fallback
            raise TextGenerationError(err)

        lines = _split_lines(content)
        if lines:
            return lines[:slides]

        replicate = self._try_replicate_outline(prompt, slides)
        if replicate is not None:
            return replicate
        fallback = self._try_fallback_outline(payload, slides)
        if fallback is not None:
            return fallback
        raise TextGenerationError('Пустой ответ от сервиса. Попробуйте еще раз.')

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def _text_endpoint_for(self, model: str) -> str:
        if self._text_endpoint_explicit:
            return self.text_endpoint
        return f'{self.base_url}/{model}/v1/chat/completions'

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(url, json=payload, headers=self._headers(), timeout=120)
        response.raise_for_status()
        data = response.json()
        error = _extract_error(data)
        if error:
            raise TextGenerationError(error)
        return data

    def _try_replicate_outline(self, prompt: str, slides: int) -> list[str] | None:
        if not self.replicate_text_client:
            return None
        try:
            text = self.replicate_text_client.generate_text(prompt)
        except Exception:
            self.logger.exception('Replicate outline fallback failed')
            return None
        lines = _split_lines(text)
        if not lines:
            return None
        return lines[:slides]

    def _try_replicate_title(self, prompt: str) -> str | None:
        if not self.replicate_text_client:
            return None
        try:
            text = self.replicate_text_client.generate_text(prompt)
        except Exception:
            self.logger.exception('Replicate title fallback failed')
            return None
        title = _clean_title(text)
        return title or None

    def _try_replicate_slides(self, prompt: str) -> list[dict[str, str]] | None:
        if not self.replicate_text_client:
            return None
        try:
            text = self.replicate_text_client.generate_text(prompt)
        except Exception:
            self.logger.exception('Replicate slides fallback failed')
            return None
        slides = _parse_json_list(text)
        return slides or None

    def _try_fallback_outline(self, payload: dict[str, Any], slides: int) -> list[str] | None:
        if not self.text_fallback_models or self._text_endpoint_explicit:
            return None
        for model in self.text_fallback_models:
            if model == self.text_model:
                continue
            endpoint = self._text_endpoint_for(model)
            self.logger.info('Trying KIE outline fallback model=%s', model)
            try:
                data = self._post(endpoint, payload)
            except Exception:
                continue
            content = _extract_content(data)
            err = _error_from_text(content)
            if err:
                continue
            lines = _split_lines(content)
            if not lines:
                continue
            self.text_model = model
            self.text_endpoint = endpoint
            return lines[:slides]
        return None

    def _fallback_slides(self, topic: str, outline: list[str]) -> list[dict[str, str]]:
        return [
            {
                'title': title,
                'text': f'Краткий текст по теме: {topic}.',
                'image_prompt': f'Иллюстрация: {title}.',
            }
            for title in outline
        ]


def _extract_output_url(output: Any) -> str:
    if isinstance(output, list) and output:
        item = output[0]
        return item if isinstance(item, str) else item.get('url', '')
    if isinstance(output, str):
        return output
    if isinstance(output, dict) and 'url' in output:
        return output['url']
    raise TextGenerationError('Replicate output URL not found')


def _extract_output_text(output: Any) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        if all(isinstance(item, str) for item in output):
            return ''.join(output)
        item = output[0]
        if isinstance(item, str):
            return item
        if isinstance(item, dict) and 'text' in item:
            return str(item['text'])
    if isinstance(output, dict):
        if 'text' in output:
            return str(output['text'])
        if 'content' in output:
            return str(output['content'])
    return str(output or '')


def _extract_content(data: dict[str, Any]) -> str:
    if 'outline' in data:
        value = data['outline']
        return '\n'.join(value) if isinstance(value, list) else str(value)
    if 'choices' in data and data['choices']:
        choice = data['choices'][0]
        if 'message' in choice and 'content' in choice['message']:
            return choice['message']['content']
        if 'text' in choice:
            return choice['text']
    return json.dumps(data, ensure_ascii=False)


def _extract_error(data: dict[str, Any]) -> str:
    if isinstance(data, dict) and 'code' in data and data.get('code') not in (0, '0', None):
        return str(data.get('msg') or data.get('message') or data.get('error') or 'Ошибка сервиса')
    if isinstance(data, dict) and 'error' in data:
        return str(data.get('error') or 'Ошибка сервиса')
    return ''


def _error_from_text(text: str) -> str:
    if not text:
        return ''
    raw = text.strip()
    if raw.startswith('{') and raw.endswith('}'):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return ''
        return _extract_error(payload)
    if 'server exception' in raw.lower():
        return 'Сервис временно недоступен, попробуйте позже.'
    return ''


def _build_text_message(prompt: str) -> dict[str, Any]:
    return {'role': 'user', 'content': [{'type': 'text', 'text': prompt}]}


def _split_lines(text: str) -> list[str]:
    lines = [re.sub(r'^\d+\.?\s*', '', line).strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _parse_json_list(text: str) -> list[dict[str, str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'(\[.*\])', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                return []
        else:
            return []
    return data if isinstance(data, list) else []


def _extract_image_url(data: dict[str, Any]) -> str:
    if 'data' in data and data['data']:
        item = data['data'][0]
        return item.get('url', '')
    return data.get('image_url', '')


def _extract_image_b64(data: dict[str, Any]) -> str:
    if 'data' in data and data['data']:
        item = data['data'][0]
        return item.get('b64_json', '')
    return data.get('image_base64', '')


def _clean_title(text: str) -> str:
    if not text:
        return ''
    value = text.strip().splitlines()[0]
    value = value.strip('"“”«»')
    value = re.sub(r'\s+', ' ', value).strip()
    value = re.sub(r'[.!?]+$', '', value).strip()
    if len(value) > 80:
        value = value[:77].rstrip() + '...'
    return value


def _fallback_title(topic: str) -> str:
    if not topic:
        return 'Презентация'
    value = topic.strip()
    if not value:
        return 'Презентация'
    lines = [line for line in value.splitlines() if line.strip()]
    value = lines[0] if lines else value
    value = re.sub(r'\s+', ' ', value).strip()
    if not value:
        return 'Презентация'
    if len(value) > 80:
        value = value[:77].rstrip() + '...'
    return value


def _placeholder_image(text: str, out_path: Path) -> None:
    image = Image.new('RGB', (1024, 768), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.text((40, 40), text[:200], fill=(30, 30, 30))
    image.save(out_path)


def _download_file(url: str, out_path: Path) -> None:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    out_path.write_bytes(response.content)
