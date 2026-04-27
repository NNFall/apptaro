import time
from typing import Dict, Any, Optional

import requests

from services.logger import get_logger


class ReplicateClient:
    def __init__(
        self,
        api_token: str,
        base_url: str,
        model: str,
        wait_seconds: int = 60,
        poll_interval: float = 1.5,
        timeout_seconds: int = 120,
        default_input: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.api_token = api_token
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.wait_seconds = wait_seconds
        self.poll_interval = poll_interval
        self.timeout_seconds = timeout_seconds
        self.default_input = default_input or {}
        self.logger = get_logger()

    def _headers(self, wait: bool = True) -> Dict[str, str]:
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
        self.logger.info('Replicate request: model=%s', self.model)
        resp = self._post_with_retry(url, payload)
        data = resp.json()
        status = data.get('status')
        if status == 'succeeded':
            self.logger.info('Replicate immediate success')
            return _extract_output_url(data.get('output'))
        if status == 'failed':
            raise RuntimeError(data.get('error') or 'Replicate prediction failed')

        prediction_url = data.get('urls', {}).get('get') or data.get('id')
        if prediction_url and not prediction_url.startswith('http'):
            prediction_url = f'{self.base_url}/v1/predictions/{prediction_url}'

        if not prediction_url:
            raise RuntimeError('Replicate prediction URL not found')

        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            data = self._poll(prediction_url)
            status = data.get('status')
            if status == 'succeeded':
                self.logger.info('Replicate success')
                return _extract_output_url(data.get('output'))
            if status == 'failed':
                raise RuntimeError(data.get('error') or 'Replicate prediction failed')
            time.sleep(self.poll_interval)

        raise TimeoutError('Replicate prediction timed out')

    def _poll(self, url: str) -> Dict[str, Any]:
        resp = self._get_with_retry(url)
        return resp.json()

    def _post_with_retry(self, url: str, payload: Dict[str, Any]) -> requests.Response:
        delay = 2.0
        for attempt in range(3):
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=120)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            retry_after = resp.headers.get('Retry-After')
            wait = int(retry_after) if retry_after and retry_after.isdigit() else delay
            self.logger.warning('Replicate rate limit, retry in %ss (attempt %s)', wait, attempt + 1)
            time.sleep(wait)
            delay = min(delay * 2, 20)
        resp.raise_for_status()
        return resp

    def _get_with_retry(self, url: str) -> requests.Response:
        delay = 2.0
        for attempt in range(3):
            resp = requests.get(url, headers=self._headers(wait=False), timeout=60)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            retry_after = resp.headers.get('Retry-After')
            wait = int(retry_after) if retry_after and retry_after.isdigit() else delay
            self.logger.warning('Replicate rate limit (poll), retry in %ss (attempt %s)', wait, attempt + 1)
            time.sleep(wait)
            delay = min(delay * 2, 20)
        resp.raise_for_status()
        return resp


def _extract_output_url(output: Any) -> str:
    if isinstance(output, list) and output:
        item = output[0]
        return item if isinstance(item, str) else item.get('url', '')
    if isinstance(output, str):
        return output
    if isinstance(output, dict) and 'url' in output:
        return output['url']
    raise RuntimeError('Replicate output URL not found')


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
        default_input: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.api_token = api_token
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.prompt_field = prompt_field or 'prompt'
        self.wait_seconds = wait_seconds
        self.poll_interval = poll_interval
        self.timeout_seconds = timeout_seconds
        self.default_input = default_input or {}
        self.logger = get_logger()

    def _headers(self, wait: bool = True) -> Dict[str, str]:
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
        resp = self._post_with_retry(url, payload)
        data = resp.json()
        status = data.get('status')
        if status == 'succeeded':
            self.logger.info('Replicate text immediate success')
            return _extract_output_text(data.get('output'))
        if status == 'failed':
            raise RuntimeError(data.get('error') or 'Replicate prediction failed')

        prediction_url = data.get('urls', {}).get('get') or data.get('id')
        if prediction_url and not prediction_url.startswith('http'):
            prediction_url = f'{self.base_url}/v1/predictions/{prediction_url}'

        if not prediction_url:
            raise RuntimeError('Replicate prediction URL not found')

        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            data = self._poll(prediction_url)
            status = data.get('status')
            if status == 'succeeded':
                self.logger.info('Replicate text success')
                return _extract_output_text(data.get('output'))
            if status == 'failed':
                raise RuntimeError(data.get('error') or 'Replicate prediction failed')
            time.sleep(self.poll_interval)

        raise TimeoutError('Replicate prediction timed out')

    def _poll(self, url: str) -> Dict[str, Any]:
        resp = self._get_with_retry(url)
        return resp.json()

    def _post_with_retry(self, url: str, payload: Dict[str, Any]) -> requests.Response:
        delay = 2.0
        for attempt in range(3):
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=120)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            retry_after = resp.headers.get('Retry-After')
            wait = int(retry_after) if retry_after and retry_after.isdigit() else delay
            self.logger.warning('Replicate text rate limit, retry in %ss (attempt %s)', wait, attempt + 1)
            time.sleep(wait)
            delay = min(delay * 2, 20)
        resp.raise_for_status()
        return resp

    def _get_with_retry(self, url: str) -> requests.Response:
        delay = 2.0
        for attempt in range(3):
            resp = requests.get(url, headers=self._headers(wait=False), timeout=60)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            retry_after = resp.headers.get('Retry-After')
            wait = int(retry_after) if retry_after and retry_after.isdigit() else delay
            self.logger.warning('Replicate text rate limit (poll), retry in %ss (attempt %s)', wait, attempt + 1)
            time.sleep(wait)
            delay = min(delay * 2, 20)
        resp.raise_for_status()
        return resp


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
