import asyncio
import base64
import json
import os
import re
import time
from typing import List, Dict, Any, Optional

import requests
from PIL import Image, ImageDraw

from services.logger import get_logger
from services.prompts import outline_prompt, outline_comment_prompt, slides_prompt, title_prompt
from services.replicate_api import ReplicateClient, ReplicateTextClient


class KieError(RuntimeError):
    pass


class KieClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        text_model: str,
        image_model: str,
        text_endpoint: str = '',
        text_fallback_models: Optional[List[str]] = None,
        replicate_api_token: str = '',
        replicate_base_url: str = '',
        replicate_model: str = '',
        replicate_wait_seconds: int = 60,
        replicate_poll_interval: float = 1.5,
        replicate_timeout_seconds: int = 120,
        replicate_default_input: Optional[Dict[str, Any]] = None,
        replicate_text_model: str = '',
        replicate_text_prompt_field: str = 'prompt',
        replicate_text_default_input: Optional[Dict[str, Any]] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.text_model = text_model
        self.image_model = image_model
        self.text_endpoint = text_endpoint or os.getenv('KIE_TEXT_ENDPOINT', '')
        self._text_endpoint_explicit = bool(self.text_endpoint)
        if not self.text_endpoint and self.base_url and self.text_model:
            self.text_endpoint = f'{self.base_url}/{self.text_model}/v1/chat/completions'
        self.text_fallback_models = text_fallback_models or []
        self.image_endpoint = os.getenv('KIE_IMAGE_ENDPOINT', '')
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
        self.logger = get_logger()

    def _headers(self) -> dict:
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

    def _post(self, url: str, payload: dict) -> Dict[str, Any]:
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=120)
        resp.raise_for_status()
        data = resp.json()
        error = _extract_error(data)
        if error:
            raise KieError(error)
        return data

    async def generate_outline(self, topic: str, slides: int) -> List[str]:
        if not self.api_key or not self.text_endpoint:
            return [f'Слайд {i}: {topic}' for i in range(1, slides + 1)]

        prompt = outline_prompt(topic, slides)
        payload = {
            'messages': [_build_text_message(prompt)],
            'temperature': 0.6,
        }
        self.logger.info('KIE text request: outline slides=%s model=%s', slides, self.text_model)
        start = time.time()
        try:
            data = await asyncio.to_thread(self._post, self.text_endpoint, payload)
        except KieError as exc:
            self.logger.exception('KIE outline failed')
            replicate = await self._try_replicate_outline(prompt, slides)
            if replicate is not None:
                return replicate
            fallback = await self._try_fallback_text(payload, slides)
            if fallback is not None:
                return fallback
            raise KieError('Сервис временно недоступен, попробуйте позже.') from exc
        except Exception as exc:  # noqa: BLE001
            self.logger.exception('KIE outline failed')
            replicate = await self._try_replicate_outline(prompt, slides)
            if replicate is not None:
                return replicate
            fallback = await self._try_fallback_text(payload, slides)
            if fallback is not None:
                return fallback
            raise KieError('Сервис временно недоступен, попробуйте позже.') from exc
        self.logger.info('KIE text response: outline elapsed=%.2fs', time.time() - start)
        content = _extract_content(data)
        err = _error_from_text(content)
        if err:
            replicate = await self._try_replicate_outline(prompt, slides)
            if replicate is not None:
                return replicate
            fallback = await self._try_fallback_text(payload, slides)
            if fallback is not None:
                return fallback
            raise KieError(err)
        items = _split_lines(content)
        if not items:
            fallback = await self._try_fallback_text(payload, slides)
            if fallback is not None:
                return fallback
            raise KieError('Пустой ответ от сервиса. Попробуйте перегенерировать.')
        return items[:slides]

    async def generate_outline_with_comment(
        self,
        topic: str,
        slides: int,
        outline: List[str],
        comment: str,
    ) -> List[str]:
        if not self.api_key or not self.text_endpoint:
            return outline[:slides]

        prompt = outline_comment_prompt(topic, slides, outline, comment)
        payload = {
            'messages': [_build_text_message(prompt)],
            'temperature': 0.6,
        }
        self.logger.info('KIE text request: outline_comment slides=%s model=%s', slides, self.text_model)
        start = time.time()
        try:
            data = await asyncio.to_thread(self._post, self.text_endpoint, payload)
        except KieError as exc:
            self.logger.exception('KIE outline comment failed')
            replicate = await self._try_replicate_outline(prompt, slides)
            if replicate is not None:
                return replicate
            fallback = await self._try_fallback_text(payload, slides)
            if fallback is not None:
                return fallback
            raise KieError('Сервис временно недоступен, попробуйте позже.') from exc
        except Exception as exc:  # noqa: BLE001
            self.logger.exception('KIE outline comment failed')
            replicate = await self._try_replicate_outline(prompt, slides)
            if replicate is not None:
                return replicate
            fallback = await self._try_fallback_text(payload, slides)
            if fallback is not None:
                return fallback
            raise KieError('Сервис временно недоступен, попробуйте позже.') from exc
        self.logger.info('KIE text response: outline_comment elapsed=%.2fs', time.time() - start)
        content = _extract_content(data)
        err = _error_from_text(content)
        if err:
            replicate = await self._try_replicate_outline(prompt, slides)
            if replicate is not None:
                return replicate
            fallback = await self._try_fallback_text(payload, slides)
            if fallback is not None:
                return fallback
            raise KieError(err)
        items = _split_lines(content)
        if not items:
            fallback = await self._try_fallback_text(payload, slides)
            if fallback is not None:
                return fallback
            raise KieError('Пустой ответ от сервиса. Попробуйте перегенерировать.')
        return items[:slides]

    async def generate_title(self, topic: str) -> str:
        if not self.api_key or not self.text_endpoint:
            return _fallback_title(topic)

        prompt = title_prompt(topic)
        payload = {
            'messages': [_build_text_message(prompt)],
            'temperature': 0.6,
        }
        self.logger.info('KIE text request: title model=%s', self.text_model)
        start = time.time()
        try:
            data = await asyncio.to_thread(self._post, self.text_endpoint, payload)
        except KieError as exc:
            self.logger.exception('KIE title failed')
            replicate = await self._try_replicate_title(prompt)
            if replicate:
                return replicate
            return _fallback_title(topic)
        except Exception:  # noqa: BLE001
            self.logger.exception('KIE title failed')
            replicate = await self._try_replicate_title(prompt)
            if replicate:
                return replicate
            return _fallback_title(topic)
        self.logger.info('KIE text response: title elapsed=%.2fs', time.time() - start)
        content = _extract_content(data)
        err = _error_from_text(content)
        if err:
            replicate = await self._try_replicate_title(prompt)
            if replicate:
                return replicate
            return _fallback_title(topic)
        title = _clean_title(content)
        return title or _fallback_title(topic)

    async def generate_slide_contents(self, topic: str, outline: List[str]) -> List[Dict[str, str]]:
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
        payload = {
            'messages': [_build_text_message(prompt)],
            'temperature': 0.6,
        }
        self.logger.info('KIE text request: slides=%s model=%s', len(outline), self.text_model)
        start = time.time()
        try:
            data = await asyncio.to_thread(self._post, self.text_endpoint, payload)
        except KieError as exc:
            self.logger.exception('KIE slides failed')
            replicate = await self._try_replicate_slides(prompt, topic, outline)
            if replicate is not None:
                return replicate
            fallback = await self._try_fallback_slides(payload, topic, outline)
            if fallback is not None:
                return fallback
            return [
                {
                    'title': title,
                    'text': f'Краткий текст по теме: {topic}.',
                    'image_prompt': f'Иллюстрация: {title}.',
                }
                for title in outline
            ]
        except Exception:  # noqa: BLE001
            self.logger.exception('KIE slides failed')
            replicate = await self._try_replicate_slides(prompt, topic, outline)
            if replicate is not None:
                return replicate
            fallback = await self._try_fallback_slides(payload, topic, outline)
            if fallback is not None:
                return fallback
            return [
                {
                    'title': title,
                    'text': f'Краткий текст по теме: {topic}.',
                    'image_prompt': f'Иллюстрация: {title}.',
                }
                for title in outline
            ]
        self.logger.info('KIE text response: slides elapsed=%.2fs', time.time() - start)
        content = _extract_content(data)
        err = _error_from_text(content)
        if err:
            self.logger.error('KIE slides error: %s', err)
            replicate = await self._try_replicate_slides(prompt, topic, outline)
            if replicate is not None:
                return replicate
            fallback = await self._try_fallback_slides(payload, topic, outline)
            if fallback is not None:
                return fallback
            return [
                {
                    'title': title,
                    'text': f'Краткий текст по теме: {topic}.',
                    'image_prompt': f'Иллюстрация: {title}.',
                }
                for title in outline
            ]
        slides = _parse_json_list(content)
        if not slides:
            fallback = await self._try_fallback_slides(payload, topic, outline)
            if fallback is not None:
                return fallback
            return [
                {
                    'title': title,
                    'text': f'Краткий текст по теме: {topic}.',
                    'image_prompt': f'Иллюстрация: {title}.',
                }
                for title in outline
            ]
        return slides

    async def _try_replicate_outline(self, prompt: str, slides: int) -> Optional[List[str]]:
        if not self.replicate_text_client:
            self.logger.warning('Replicate text fallback not configured (outline)')
            return None
        self.logger.info('Replicate text fallback: outline model=%s', self.replicate_text_client.model)
        try:
            text = await asyncio.to_thread(self.replicate_text_client.generate_text, prompt)
        except Exception:  # noqa: BLE001
            self.logger.exception('Replicate text failed: outline')
            return None
        items = _split_lines(text)
        if not items:
            return None
        return items[:slides]

    async def _try_replicate_title(self, prompt: str) -> Optional[str]:
        if not self.replicate_text_client:
            self.logger.warning('Replicate text fallback not configured (title)')
            return None
        self.logger.info('Replicate text fallback: title model=%s', self.replicate_text_client.model)
        try:
            text = await asyncio.to_thread(self.replicate_text_client.generate_text, prompt)
        except Exception:  # noqa: BLE001
            self.logger.exception('Replicate text failed: title')
            return None
        title = _clean_title(text)
        return title or None

    async def _try_replicate_slides(
        self,
        prompt: str,
        topic: str,
        outline: List[str],
    ) -> Optional[List[Dict[str, str]]]:
        if not self.replicate_text_client:
            self.logger.warning('Replicate text fallback not configured (slides)')
            return None
        self.logger.info('Replicate text fallback: slides model=%s', self.replicate_text_client.model)
        try:
            text = await asyncio.to_thread(self.replicate_text_client.generate_text, prompt)
        except Exception:  # noqa: BLE001
            self.logger.exception('Replicate text failed: slides')
            return None
        slides = _parse_json_list(text)
        if not slides:
            return None
        return slides

    async def _try_fallback_text(self, payload: dict, slides: int) -> Optional[List[str]]:
        if not self.text_fallback_models or self._text_endpoint_explicit:
            return None
        for model in self.text_fallback_models:
            if model == self.text_model:
                continue
            endpoint = self._text_endpoint_for(model)
            self.logger.info('KIE text fallback: model=%s', model)
            try:
                data = await asyncio.to_thread(self._post, endpoint, payload)
            except Exception:  # noqa: BLE001
                continue
            content = _extract_content(data)
            err = _error_from_text(content)
            if err:
                continue
            items = _split_lines(content)
            if not items:
                continue
            self.text_model = model
            self.text_endpoint = endpoint
            return items[:slides]
        return None

    async def _try_fallback_slides(
        self,
        payload: dict,
        topic: str,
        outline: List[str],
    ) -> Optional[List[Dict[str, str]]]:
        if not self.text_fallback_models or self._text_endpoint_explicit:
            return None
        for model in self.text_fallback_models:
            if model == self.text_model:
                continue
            endpoint = self._text_endpoint_for(model)
            self.logger.info('KIE slides fallback: model=%s', model)
            try:
                data = await asyncio.to_thread(self._post, endpoint, payload)
            except Exception:  # noqa: BLE001
                continue
            content = _extract_content(data)
            err = _error_from_text(content)
            if err:
                continue
            slides = _parse_json_list(content)
            if not slides:
                continue
            self.text_model = model
            self.text_endpoint = endpoint
            return slides
        return None

    async def generate_image(self, prompt: str, out_path: str) -> str:
        if self.replicate_client:
            self.logger.info('Replicate image request')
            try:
                image_url = await asyncio.to_thread(self.replicate_client.generate_image, prompt)
                self.logger.info('Replicate image response')
                await asyncio.to_thread(_download_file, image_url, out_path)
                return out_path
            except Exception as exc:  # noqa: BLE001
                self.logger.warning('Replicate image failed: %s', exc)
                _placeholder_image(prompt, out_path)
                return out_path
        if not self.api_key or not self.image_endpoint:
            _placeholder_image(prompt, out_path)
            return out_path

        payload = {
            'model': self.image_model,
            'prompt': prompt,
            'size': '1024x1024',
        }
        self.logger.info('KIE image request: model=%s', self.image_model or 'default')
        start = time.time()
        try:
            data = await asyncio.to_thread(self._post, self.image_endpoint, payload)
        except Exception:  # noqa: BLE001
            self.logger.exception('KIE image failed')
            _placeholder_image(prompt, out_path)
            return out_path
        self.logger.info('KIE image response: elapsed=%.2fs', time.time() - start)
        image_url = _extract_image_url(data)
        if image_url:
            await asyncio.to_thread(_download_file, image_url, out_path)
            return out_path
        image_b64 = _extract_image_b64(data)
        if image_b64:
            with open(out_path, 'wb') as f:
                f.write(base64.b64decode(image_b64))
            return out_path
        _placeholder_image(prompt, out_path)
        return out_path


def _extract_content(data: Dict[str, Any]) -> str:
    if 'outline' in data:
        return '\n'.join(data['outline']) if isinstance(data['outline'], list) else str(data['outline'])
    if 'choices' in data:
        choice = data['choices'][0]
        if 'message' in choice and 'content' in choice['message']:
            return choice['message']['content']
        if 'text' in choice:
            return choice['text']
    return json.dumps(data, ensure_ascii=False)


def _extract_error(data: Dict[str, Any]) -> str:
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


def _is_server_exception(message: str) -> bool:
    if not message:
        return False
    value = message.lower()
    return 'server exception' in value or 'сервис временно недоступен' in value


def _build_text_message(prompt: str) -> Dict[str, Any]:
    return {'role': 'user', 'content': [{'type': 'text', 'text': prompt}]}


def _split_lines(text: str) -> List[str]:
    lines = [re.sub(r'^\d+\.?\s*', '', line).strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _parse_json_list(text: str) -> List[Dict[str, str]]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'(\[.*\])', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return []
    return []


def _extract_image_url(data: Dict[str, Any]) -> str:
    if 'data' in data and data['data']:
        item = data['data'][0]
        return item.get('url', '')
    return data.get('image_url', '')


def _extract_image_b64(data: Dict[str, Any]) -> str:
    if 'data' in data and data['data']:
        item = data['data'][0]
        return item.get('b64_json', '')
    return data.get('image_base64', '')


def _clean_title(text: str) -> str:
    if not text:
        return ''
    value = text.strip().splitlines()[0]
    value = value.strip('\"“”«»')
    value = re.sub(r'[\\s]+', ' ', value).strip()
    value = re.sub(r'[\\.!?]+$', '', value).strip()
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
    value = re.sub(r'[\\s]+', ' ', value).strip()
    if not value:
        return 'Презентация'
    if len(value) > 80:
        value = value[:77].rstrip() + '...'
    return value


def _placeholder_image(text: str, out_path: str) -> None:
    img = Image.new('RGB', (1024, 768), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), text[:200], fill=(30, 30, 30))
    img.save(out_path)


def _download_file(url: str, out_path: str) -> None:
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with open(out_path, 'wb') as f:
        f.write(resp.content)
