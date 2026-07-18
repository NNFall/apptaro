from __future__ import annotations

import importlib.util
import socket
import time
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / 'scripts' / 'macos' / 'release_url_probe.py'


def _load_probe() -> ModuleType:
    spec = importlib.util.spec_from_file_location('release_url_probe', PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe()

HEALTHY_PAYLOAD = (
    b'{"status":"ok","service":"ASapptaro Backend","environment":"production"}'
)


def _resolver(*addresses: str) -> Callable[..., list[tuple]]:
    def resolve(host: str, port: int, *args, **kwargs) -> list[tuple]:
        del host, args, kwargs
        results = []
        for address in addresses:
            family = socket.AF_INET6 if ':' in address else socket.AF_INET
            sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
            results.append((family, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', sockaddr))
        return results

    return resolve


def test_public_https_origin_resolves_to_public_addresses() -> None:
    validated = probe.validate_release_url(
        'backend',
        'https://api.example.com',
        origin_only=True,
        resolver=_resolver('8.8.8.8', '2606:4700:4700::1111'),
    )

    assert validated.host == 'api.example.com'
    assert validated.addresses == ('2606:4700:4700::1111', '8.8.8.8')


@pytest.mark.parametrize(
    'host,address',
    [
        ('localhost', '127.0.0.1'),
        ('api.example.test', '10.0.0.1'),
        ('api.example.test', '169.254.1.2'),
        ('api.example.test', '0.0.0.0'),
        ('api.example.test', '224.0.0.1'),
        ('api.example.test', '192.0.2.1'),
        ('api.example.test', '::1'),
        ('api.example.test', 'fc00::1'),
        ('api.example.test', 'fe80::1'),
        ('api.example.test', '::'),
        ('api.example.test', 'ff02::1'),
        ('api.example.test', '2001:db8::1'),
    ],
)
def test_non_public_release_hosts_are_rejected(host: str, address: str) -> None:
    with pytest.raises(probe.ReleaseProbeError, match='public'):
        probe.validate_release_url(
            'release URL',
            f'https://{host}',
            origin_only=True,
            resolver=_resolver(address),
        )


def test_mixed_public_and_private_dns_answers_are_rejected() -> None:
    with pytest.raises(probe.ReleaseProbeError, match='10.1.2.3'):
        probe.validate_release_url(
            'backend',
            'https://api.example.com',
            origin_only=True,
            resolver=_resolver('8.8.8.8', '10.1.2.3'),
        )


def test_dns_resolution_has_a_bounded_timeout() -> None:
    def slow_resolver(*args, **kwargs):
        del args, kwargs
        time.sleep(0.2)
        return _resolver('8.8.8.8')('example.com', 443)

    with pytest.raises(probe.ReleaseProbeError, match='timed out'):
        probe.validate_release_url(
            'backend',
            'https://api.example.com',
            origin_only=True,
            resolver=slow_resolver,
            dns_timeout_seconds=0.01,
        )


def test_https_redirect_cannot_downgrade_to_http() -> None:
    def requester(validated, timeout_seconds: float):
        del validated, timeout_seconds
        return probe.ProbeResponse(302, {'location': 'http://public.example.com'}, b'')

    with pytest.raises(probe.ReleaseProbeError, match='HTTPS'):
        probe.probe_https_url(
            'privacy',
            'https://privacy.example.com/policy',
            resolver=_resolver('8.8.8.8'),
            requester=requester,
        )


def test_https_redirect_cannot_target_private_dns() -> None:
    calls = 0

    def resolver(host: str, port: int, *args, **kwargs):
        if host == 'privacy.example.com':
            return _resolver('8.8.8.8')(host, port, *args, **kwargs)
        return _resolver('127.0.0.1')(host, port, *args, **kwargs)

    def requester(validated, timeout_seconds: float):
        nonlocal calls
        del validated, timeout_seconds
        calls += 1
        return probe.ProbeResponse(302, {'location': 'https://private.example.com/policy'}, b'')

    with pytest.raises(probe.ReleaseProbeError, match='public'):
        probe.probe_https_url(
            'privacy',
            'https://privacy.example.com/policy',
            resolver=resolver,
            requester=requester,
        )
    assert calls == 1


def test_release_probe_checks_health_json_and_privacy_page() -> None:
    requested_urls: list[str] = []

    def requester(validated, timeout_seconds: float):
        assert 0 < timeout_seconds <= 30
        requested_urls.append(validated.url)
        if validated.url.endswith('/v1/health'):
            return probe.ProbeResponse(200, {'content-type': 'application/json'}, HEALTHY_PAYLOAD)
        return probe.ProbeResponse(200, {'content-type': 'text/html'}, b'<html>Privacy</html>')

    probe.probe_release_urls(
        'https://api.example.com',
        'https://www.example.com/privacy',
        timeout_seconds=4,
        resolver=_resolver('8.8.8.8'),
        requester=requester,
    )

    assert requested_urls == [
        'https://api.example.com/v1/health',
        'https://www.example.com/privacy',
    ]


def test_release_probe_rejects_unhealthy_backend_and_unbounded_timeout() -> None:
    def requester(validated, timeout_seconds: float):
        del validated, timeout_seconds
        return probe.ProbeResponse(200, {}, b'{"status":"degraded"}')

    with pytest.raises(probe.ReleaseProbeError, match='status=ok'):
        probe.probe_release_urls(
            'https://api.example.com',
            'https://www.example.com/privacy',
            timeout_seconds=4,
            resolver=_resolver('8.8.8.8'),
            requester=requester,
        )


@pytest.mark.parametrize(
    'payload',
    [
        b'{"status":"ok"}',
        b'{"status":"ok","service":"Other Backend","environment":"production"}',
        b'{"status":"ok","service":"ASapptaro Backend","environment":"staging"}',
        b'{"status":"degraded","service":"ASapptaro Backend","environment":"production"}',
    ],
)
def test_backend_health_requires_exact_production_identity(payload: bytes) -> None:
    def requester(validated, timeout_seconds: float):
        del timeout_seconds
        if validated.url.endswith('/v1/health'):
            return probe.ProbeResponse(200, {'content-type': 'application/json'}, payload)
        return probe.ProbeResponse(200, {'content-type': 'text/html'}, b'Privacy policy')

    with pytest.raises(probe.ReleaseProbeError, match='ASapptaro Backend'):
        probe.probe_release_urls(
            'https://api.example.com',
            'https://www.example.com/privacy',
            timeout_seconds=4,
            resolver=_resolver('8.8.8.8'),
            requester=requester,
        )


@pytest.mark.parametrize(
    ('status', 'headers', 'body', 'message'),
    [
        (204, {'content-type': 'text/html'}, b'', 'non-empty'),
        (200, {'content-type': 'text/html'}, b'', 'non-empty'),
        (200, {'content-type': 'text/plain'}, b'   \n', 'non-empty'),
        (200, {}, b'Privacy policy', 'content type'),
        (200, {'content-type': 'application/octet-stream'}, b'Privacy policy', 'content type'),
        (200, {'content-type': 'image/png'}, b'not a policy page', 'content type'),
    ],
)
def test_privacy_probe_rejects_non_page_responses(
    status: int,
    headers: dict[str, str],
    body: bytes,
    message: str,
) -> None:
    def requester(validated, timeout_seconds: float):
        del timeout_seconds
        if validated.url.endswith('/v1/health'):
            return probe.ProbeResponse(200, {'content-type': 'application/json'}, HEALTHY_PAYLOAD)
        return probe.ProbeResponse(status, headers, body)

    with pytest.raises(probe.ReleaseProbeError, match=message):
        probe.probe_release_urls(
            'https://api.example.com',
            'https://www.example.com/privacy',
            timeout_seconds=4,
            resolver=_resolver('8.8.8.8'),
            requester=requester,
        )


@pytest.mark.parametrize(
    'content_type',
    [
        'text/html',
        'text/html; charset=utf-8',
        'text/plain',
        'application/xhtml+xml',
        'application/pdf',
    ],
)
def test_privacy_probe_accepts_document_content_types(content_type: str) -> None:
    def requester(validated, timeout_seconds: float):
        del timeout_seconds
        if validated.url.endswith('/v1/health'):
            return probe.ProbeResponse(200, {'content-type': 'application/json'}, HEALTHY_PAYLOAD)
        return probe.ProbeResponse(200, {'content-type': content_type}, b'Privacy policy')

    probe.probe_release_urls(
        'https://api.example.com',
        'https://www.example.com/privacy',
        timeout_seconds=4,
        resolver=_resolver('8.8.8.8'),
        requester=requester,
    )

    with pytest.raises(probe.ReleaseProbeError, match='between'):
        probe.probe_release_urls(
            'https://api.example.com',
            'https://www.example.com/privacy',
            timeout_seconds=31,
            resolver=_resolver('8.8.8.8'),
            requester=requester,
        )
