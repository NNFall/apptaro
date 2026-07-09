from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


ANDROID_PUBLISHER_SCOPE = 'https://www.googleapis.com/auth/androidpublisher'


@dataclass(frozen=True)
class GooglePlayPurchaseInfo:
    product_id: str
    purchase_token: str
    order_id: str
    status: str
    expires_at: str | None
    auto_renewing: bool
    raw_state: str


class GooglePlayGateway:
    def __init__(
        self,
        *,
        package_name: str,
        service_account_file: str = '',
        service_account_json: str = '',
        test_mode: bool = False,
    ) -> None:
        self._package_name = package_name.strip()
        self._service_account_file = service_account_file.strip()
        self._service_account_json = service_account_json.strip()
        self._test_mode = test_mode
        self._session: requests.Session | None = None

    @property
    def is_configured(self) -> bool:
        return self._test_mode or bool(self._service_account_file or self._service_account_json)

    def verify_purchase(
        self,
        *,
        package_name: str,
        product_id: str,
        purchase_token: str,
        recurring: bool,
    ) -> GooglePlayPurchaseInfo:
        resolved_package = (package_name or self._package_name).strip()
        if not resolved_package:
            raise RuntimeError('Google Play package name is not configured')
        if self._package_name and resolved_package != self._package_name:
            raise ValueError('Purchase package name does not match this backend')
        if not product_id.strip():
            raise ValueError('Missing Google Play product id')
        if not purchase_token.strip():
            raise ValueError('Missing Google Play purchase token')

        if self._test_mode and purchase_token.startswith('test_'):
            return GooglePlayPurchaseInfo(
                product_id=product_id,
                purchase_token=purchase_token,
                order_id=f'test:{purchase_token[-16:]}',
                status='paid',
                expires_at=None,
                auto_renewing=recurring,
                raw_state='TEST_PURCHASED',
            )

        if recurring:
            return self._verify_subscription(
                package_name=resolved_package,
                product_id=product_id,
                purchase_token=purchase_token,
            )
        return self._verify_product(
            package_name=resolved_package,
            product_id=product_id,
            purchase_token=purchase_token,
        )

    def _verify_subscription(
        self,
        *,
        package_name: str,
        product_id: str,
        purchase_token: str,
    ) -> GooglePlayPurchaseInfo:
        url = (
            'https://androidpublisher.googleapis.com/androidpublisher/v3/'
            f'applications/{package_name}/purchases/subscriptionsv2/tokens/{purchase_token}'
        )
        data = self._get_json(url)
        state = str(data.get('subscriptionState') or 'SUBSCRIPTION_STATE_UNSPECIFIED')
        line_item = _find_subscription_line_item(data, product_id)
        if line_item is None:
            raise ValueError('Google Play subscription product does not match requested plan')

        expires_at = str(line_item.get('expiryTime') or '').strip() or None
        auto_renewing = 'autoRenewingPlan' in line_item
        latest_order_id = str(data.get('latestOrderId') or '').strip()
        status = 'paid' if _is_subscription_paid(state, expires_at) else 'failed'
        return GooglePlayPurchaseInfo(
            product_id=product_id,
            purchase_token=purchase_token,
            order_id=latest_order_id or f'google-play:{purchase_token[-32:]}',
            status=status,
            expires_at=expires_at,
            auto_renewing=auto_renewing,
            raw_state=state,
        )

    def _verify_product(
        self,
        *,
        package_name: str,
        product_id: str,
        purchase_token: str,
    ) -> GooglePlayPurchaseInfo:
        url = (
            'https://androidpublisher.googleapis.com/androidpublisher/v3/'
            f'applications/{package_name}/purchases/products/{product_id}/tokens/{purchase_token}'
        )
        data = self._get_json(url)
        purchase_state = int(data.get('purchaseState', 1))
        order_id = str(data.get('orderId') or '').strip()
        status = 'paid' if purchase_state == 0 else 'failed'
        return GooglePlayPurchaseInfo(
            product_id=product_id,
            purchase_token=purchase_token,
            order_id=order_id or f'google-play:{purchase_token[-32:]}',
            status=status,
            expires_at=None,
            auto_renewing=False,
            raw_state=str(purchase_state),
        )

    def _get_json(self, url: str) -> dict[str, Any]:
        session = self._authorized_session()
        response = session.get(url, timeout=30)
        if response.status_code == 404:
            raise ValueError('Google Play purchase token was not found')
        if response.status_code in {400, 401, 403}:
            raise RuntimeError(f'Google Play API rejected request: {response.status_code} {response.text[:300]}')
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}

    def _authorized_session(self) -> requests.Session:
        if self._session is not None:
            return self._session
        credentials_info = self._load_credentials_info()
        if not credentials_info:
            raise RuntimeError('Google Play service account is not configured')

        from google.auth.transport.requests import AuthorizedSession  # type: ignore[import-not-found]
        from google.oauth2 import service_account  # type: ignore[import-not-found]

        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=[ANDROID_PUBLISHER_SCOPE],
        )
        self._session = AuthorizedSession(credentials)
        return self._session

    def _load_credentials_info(self) -> dict[str, Any]:
        if self._service_account_json:
            try:
                data = json.loads(self._service_account_json)
            except json.JSONDecodeError as exc:
                raise RuntimeError('GOOGLE_PLAY_SERVICE_ACCOUNT_JSON is not valid JSON') from exc
            if not isinstance(data, dict):
                raise RuntimeError('GOOGLE_PLAY_SERVICE_ACCOUNT_JSON must contain an object')
            return data
        if self._service_account_file:
            path = Path(self._service_account_file)
            if not path.exists():
                raise RuntimeError(f'Google Play service account file not found: {path}')
            with path.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise RuntimeError('Google Play service account file must contain an object')
            return data
        return {}


def _find_subscription_line_item(data: dict[str, Any], product_id: str) -> dict[str, Any] | None:
    line_items = data.get('lineItems')
    if not isinstance(line_items, list):
        return None
    for item in line_items:
        if isinstance(item, dict) and item.get('productId') == product_id:
            return item
    return None


def _is_subscription_paid(state: str, expires_at: str | None) -> bool:
    if state not in {
        'SUBSCRIPTION_STATE_ACTIVE',
        'SUBSCRIPTION_STATE_CANCELED',
        'SUBSCRIPTION_STATE_IN_GRACE_PERIOD',
    }:
        return False
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
    except ValueError:
        return False
    return expiry > datetime.now(timezone.utc)
