#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import queue
import socket
import ssl
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from typing import NamedTuple
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit


DEFAULT_TIMEOUT_SECONDS = 8.0
MAX_TIMEOUT_SECONDS = 30.0
MAX_REDIRECTS = 4
MAX_RESPONSE_BYTES = 1024 * 1024
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
POLICY_CONTENT_TYPES = frozenset(
    {
        'text/html',
        'text/plain',
        'text/markdown',
        'application/xhtml+xml',
        'application/pdf',
    },
)


class ReleaseProbeError(RuntimeError):
    pass


class ValidatedUrl(NamedTuple):
    url: str
    parsed: SplitResult
    host: str
    port: int
    addresses: tuple[str, ...]


class ProbeResponse(NamedTuple):
    status: int
    headers: Mapping[str, str]
    body: bytes


Resolver = Callable[..., Sequence[tuple]]
Requester = Callable[[ValidatedUrl, float], ProbeResponse]


def _resolve_public_addresses(
    label: str,
    host: str,
    port: int,
    resolver: Resolver,
    timeout_seconds: float,
) -> tuple[str, ...]:
    normalized_host = host.rstrip('.').lower()
    if normalized_host == 'localhost' or normalized_host.endswith('.localhost'):
        raise ReleaseProbeError(f'{label} must resolve only to public IP addresses; localhost is forbidden.')

    outcome: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

    def resolve() -> None:
        try:
            answers = resolver(
                host,
                port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
            outcome.put((True, answers))
        except BaseException as exc:
            outcome.put((False, exc))

    worker = threading.Thread(target=resolve, name=f'resolve-{host}', daemon=True)
    worker.start()
    try:
        succeeded, result = outcome.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise ReleaseProbeError(f'{label} DNS resolution timed out after {timeout_seconds:g} seconds.') from exc
    if not succeeded:
        error = result
        if isinstance(error, BaseException):
            raise ReleaseProbeError(f'{label} DNS resolution failed: {error}') from error
        raise ReleaseProbeError(f'{label} DNS resolution failed.')
    answers = result
    if not isinstance(answers, Sequence):
        raise ReleaseProbeError(f'{label} DNS resolver returned an invalid response.')

    addresses: set[str] = set()
    rejected: set[str] = set()
    for answer in answers:
        if len(answer) < 5 or not answer[4]:
            continue
        raw_address = str(answer[4][0]).split('%', 1)[0]
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError:
            rejected.add(raw_address)
            continue
        canonical = str(address)
        if (
            not address.is_global
            or address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
            or address.is_multicast
        ):
            rejected.add(canonical)
        else:
            addresses.add(canonical)

    if rejected:
        values = ', '.join(sorted(rejected))
        raise ReleaseProbeError(f'{label} must resolve only to public IP addresses; rejected: {values}.')
    if not addresses:
        raise ReleaseProbeError(f'{label} did not resolve to any public IP address.')
    return tuple(sorted(addresses))


def validate_release_url(
    label: str,
    value: str,
    *,
    origin_only: bool,
    resolver: Resolver = socket.getaddrinfo,
    dns_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ValidatedUrl:
    if not 0 < dns_timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ReleaseProbeError(f'DNS timeout must be between 0 and {MAX_TIMEOUT_SECONDS:g} seconds.')
    if value != value.strip() or any(character.isspace() for character in value):
        raise ReleaseProbeError(f'{label} must not contain whitespace.')
    try:
        parsed = urlsplit(value)
        port = parsed.port or 443
    except ValueError as exc:
        raise ReleaseProbeError(f'{label} is invalid: {exc}') from exc

    if parsed.scheme.lower() != 'https' or not parsed.hostname:
        raise ReleaseProbeError(f'{label} must be an absolute HTTPS URL.')
    if parsed.username or parsed.password:
        raise ReleaseProbeError(f'{label} must not contain credentials.')
    if parsed.fragment:
        raise ReleaseProbeError(f'{label} must not contain a fragment.')
    if not 1 <= port <= 65535:
        raise ReleaseProbeError(f'{label} has an invalid port.')
    if origin_only and (parsed.path not in ('', '/') or parsed.query):
        raise ReleaseProbeError(f'{label} must be exactly one HTTPS origin without path or query.')

    host = parsed.hostname.rstrip('.').lower()
    addresses = _resolve_public_addresses(label, host, port, resolver, dns_timeout_seconds)
    normalized = parsed._replace(scheme='https', netloc=parsed.netloc.rstrip('.'))
    return ValidatedUrl(urlunsplit(normalized), normalized, host, port, addresses)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, validated: ValidatedUrl, address: str, timeout: float) -> None:
        super().__init__(
            validated.host,
            port=validated.port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self._pinned_address = address

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self._pinned_address, self.port),
            timeout=self.timeout,
            source_address=self.source_address,
        )
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


def _request_public_https(validated: ValidatedUrl, timeout_seconds: float) -> ProbeResponse:
    request_target = urlunsplit(('', '', validated.parsed.path or '/', validated.parsed.query, ''))
    failures: list[str] = []
    deadline = time.monotonic() + timeout_seconds
    for address in validated.addresses:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        connection = _PinnedHTTPSConnection(validated, address, remaining)
        try:
            connection.request(
                'GET',
                request_target,
                headers={
                    'Accept': 'application/json,text/html;q=0.9,*/*;q=0.1',
                    'User-Agent': 'ASapptaro-Release-Preflight/1.0',
                },
            )
            response = connection.getresponse()
            headers = {name.lower(): value for name, value in response.getheaders()}
            if response.status in REDIRECT_STATUSES:
                body = b''
            else:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ReleaseProbeError('response exceeded the 1 MiB safety limit')
            return ProbeResponse(response.status, headers, body)
        except (OSError, ssl.SSLError, http.client.HTTPException, ReleaseProbeError) as exc:
            failures.append(f'{address}: {exc}')
        finally:
            connection.close()
    details = '; '.join(failures)
    raise ReleaseProbeError(f'HTTPS request failed for every validated public address: {details}')


def probe_https_url(
    label: str,
    value: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    resolver: Resolver = socket.getaddrinfo,
    requester: Requester | None = None,
    max_redirects: int = MAX_REDIRECTS,
) -> tuple[str, ProbeResponse]:
    if not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ReleaseProbeError(f'timeout must be between 0 and {MAX_TIMEOUT_SECONDS:g} seconds.')
    if not 0 <= max_redirects <= MAX_REDIRECTS:
        raise ReleaseProbeError(f'max redirects must be between 0 and {MAX_REDIRECTS}.')
    request = requester or _request_public_https
    current_url = value
    deadline = time.monotonic() + timeout_seconds

    for redirect_index in range(max_redirects + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ReleaseProbeError(f'{label} probe timed out after {timeout_seconds:g} seconds.')
        validated = validate_release_url(
            label,
            current_url,
            origin_only=False,
            resolver=resolver,
            dns_timeout_seconds=remaining,
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ReleaseProbeError(f'{label} probe timed out after {timeout_seconds:g} seconds.')
        response = request(validated, remaining)
        if response.status in REDIRECT_STATUSES:
            location = response.headers.get('location')
            if not location:
                raise ReleaseProbeError(f'{label} returned redirect {response.status} without Location.')
            if redirect_index == max_redirects:
                raise ReleaseProbeError(f'{label} exceeded the {max_redirects}-redirect limit.')
            next_url = urljoin(validated.url, location)
            if urlsplit(next_url).scheme.lower() != 'https':
                raise ReleaseProbeError(f'{label} redirect downgrade is forbidden; every hop must use HTTPS.')
            current_url = next_url
            continue
        if not 200 <= response.status < 300:
            raise ReleaseProbeError(f'{label} returned HTTP {response.status}; expected 2xx.')
        return validated.url, response
    raise ReleaseProbeError(f'{label} redirect handling failed.')


def probe_release_urls(
    backend_origin: str,
    privacy_url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    resolver: Resolver = socket.getaddrinfo,
    requester: Requester | None = None,
) -> None:
    if not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ReleaseProbeError(f'timeout must be between 0 and {MAX_TIMEOUT_SECONDS:g} seconds.')

    backend = validate_release_url(
        'APPLE_BACKEND_BASE_URL',
        backend_origin,
        origin_only=True,
        resolver=resolver,
        dns_timeout_seconds=timeout_seconds,
    )
    validate_release_url(
        'APPLE_PRIVACY_POLICY_URL',
        privacy_url,
        origin_only=False,
        resolver=resolver,
        dns_timeout_seconds=timeout_seconds,
    )
    health_url = f'{backend.url.rstrip("/")}/v1/health'
    _, health_response = probe_https_url(
        'backend health URL',
        health_url,
        timeout_seconds=timeout_seconds,
        resolver=resolver,
        requester=requester,
    )
    try:
        health_payload = json.loads(health_response.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseProbeError('backend health URL must return UTF-8 JSON with status=ok.') from exc
    expected_health = {
        'status': 'ok',
        'service': 'ASapptaro Backend',
        'environment': 'production',
    }
    if not isinstance(health_payload, dict) or any(
        health_payload.get(name) != expected
        for name, expected in expected_health.items()
    ):
        raise ReleaseProbeError(
            "backend health URL must return JSON with status=ok, "
            "service='ASapptaro Backend', and environment='production'.",
        )

    _, privacy_response = probe_https_url(
        'privacy policy URL',
        privacy_url,
        timeout_seconds=timeout_seconds,
        resolver=resolver,
        requester=requester,
    )
    if not privacy_response.body.strip():
        raise ReleaseProbeError('privacy policy URL must return a non-empty policy document.')
    content_type_header = next(
        (
            value
            for name, value in privacy_response.headers.items()
            if name.lower() == 'content-type'
        ),
        '',
    )
    content_type = content_type_header.split(';', 1)[0].strip().lower()
    if content_type not in POLICY_CONTENT_TYPES:
        allowed = ', '.join(sorted(POLICY_CONTENT_TYPES))
        raise ReleaseProbeError(
            f'privacy policy URL returned unsupported content type; expected one of: {allowed}.',
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate and probe App Store release URLs.')
    parser.add_argument('--backend-origin', required=True)
    parser.add_argument('--privacy-url', required=True)
    parser.add_argument('--timeout-seconds', type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    try:
        probe_release_urls(
            args.backend_origin,
            args.privacy_url,
            timeout_seconds=args.timeout_seconds,
        )
    except ReleaseProbeError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    print('Release backend health and privacy policy HTTPS probes passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
