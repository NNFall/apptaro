from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Collection, Protocol

from appstoreserverlibrary.api_client import (
    APIError,
    APIException,
    AppStoreServerAPIClient,
)
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.signed_data_verifier import (
    SignedDataVerifier,
    VerificationException,
    VerificationStatus,
)
from requests import RequestException


APP_STORE_PRODUCT_IDS = frozenset({
    'weekly_readings',
    'monthly_readings',
    'one10_readings',
    'one40_readings',
})
SUBSCRIPTION_PRODUCT_IDS = frozenset({'weekly_readings', 'monthly_readings'})


class AppStoreGatewayError(RuntimeError):
    """Raised when Apple cannot be queried or the gateway is misconfigured."""


class AppStoreValidationError(AppStoreGatewayError):
    """Raised when an Apple transaction cannot grant an entitlement."""


class _TransactionClient(Protocol):
    def get_transaction_info(self, transaction_id: str) -> object: ...


class _TransactionVerifier(Protocol):
    def verify_and_decode_signed_transaction(self, signed_transaction: str) -> object: ...

    def verify_and_decode_notification(self, signed_payload: str) -> object: ...

    def verify_and_decode_renewal_info(self, signed_renewal_info: str) -> object: ...


@dataclass(frozen=True)
class AppStoreGatewayConfig:
    private_key_path: Path
    key_id: str
    issuer_id: str
    bundle_id: str
    app_apple_id: int
    root_certificates_dir: Path
    allowed_product_ids: Collection[str]
    enable_online_checks: bool = False


@dataclass(frozen=True)
class VerifiedAppStoreTransaction:
    transaction_id: str
    original_transaction_id: str
    bundle_id: str
    product_id: str
    environment: Environment
    app_account_token: str | None
    purchase_date_ms: int | None
    expires_date_ms: int | None
    revocation_date_ms: int | None
    transaction_type: object | None
    signed_transaction: str


@dataclass(frozen=True)
class VerifiedAppStoreRenewalInfo:
    original_transaction_id: str
    product_id: str
    environment: Environment
    app_account_token: str | None
    grace_period_expires_date_ms: int | None
    is_in_billing_retry_period: bool
    expiration_intent: object | None
    signed_renewal_info: str
    auto_renew: bool | None
    signed_date_ms: int | None


@dataclass(frozen=True)
class VerifiedAppStoreNotification:
    notification_uuid: str
    notification_type: str
    subtype: str | None
    signed_date_ms: int | None
    environment: Environment
    transaction: VerifiedAppStoreTransaction | None
    renewal_info: VerifiedAppStoreRenewalInfo | None
    signed_payload: str


class AppStoreGateway:
    def __init__(
        self,
        *,
        config: AppStoreGatewayConfig,
        api_client_factory: Callable[..., _TransactionClient] = AppStoreServerAPIClient,
        verifier_factory: Callable[..., _TransactionVerifier] = SignedDataVerifier,
        clock: Callable[[], float] = time.time,
    ) -> None:
        _validate_config(config)
        signing_key = _read_required_file(config.private_key_path, 'App Store private key')
        root_certificates = _read_root_certificates(config.root_certificates_dir)

        self._bundle_id = config.bundle_id
        self._app_apple_id = config.app_apple_id
        self._allowed_product_ids = _validate_product_ids(config.allowed_product_ids)
        self._clock = clock
        self._production_client = api_client_factory(
            signing_key,
            config.key_id,
            config.issuer_id,
            config.bundle_id,
            Environment.PRODUCTION,
        )
        self._sandbox_client = api_client_factory(
            signing_key,
            config.key_id,
            config.issuer_id,
            config.bundle_id,
            Environment.SANDBOX,
        )
        self._production_verifier = verifier_factory(
            root_certificates,
            config.enable_online_checks,
            Environment.PRODUCTION,
            config.bundle_id,
            config.app_apple_id,
        )
        self._sandbox_verifier = verifier_factory(
            root_certificates,
            config.enable_online_checks,
            Environment.SANDBOX,
            config.bundle_id,
            None,
        )

    @classmethod
    def from_dependencies(
        cls,
        *,
        bundle_id: str,
        app_apple_id: int,
        allowed_product_ids: Collection[str],
        production_client: _TransactionClient,
        sandbox_client: _TransactionClient,
        production_verifier: _TransactionVerifier,
        sandbox_verifier: _TransactionVerifier,
        clock: Callable[[], float] = time.time,
    ) -> AppStoreGateway:
        if not bundle_id.strip():
            raise ValueError('App Store bundle id is required')
        if app_apple_id <= 0:
            raise ValueError('App Store appAppleId must be positive')
        validated_product_ids = _validate_product_ids(allowed_product_ids)

        gateway = cls.__new__(cls)
        gateway._bundle_id = bundle_id.strip()
        gateway._app_apple_id = app_apple_id
        gateway._allowed_product_ids = validated_product_ids
        gateway._clock = clock
        gateway._production_client = production_client
        gateway._sandbox_client = sandbox_client
        gateway._production_verifier = production_verifier
        gateway._sandbox_verifier = sandbox_verifier
        return gateway

    def get_verified_transaction(self, transaction_id: str) -> VerifiedAppStoreTransaction:
        requested_transaction_id = transaction_id.strip()
        if not requested_transaction_id:
            raise AppStoreValidationError('Apple transaction id is required')

        try:
            response = self._production_client.get_transaction_info(requested_transaction_id)
        except APIException as exc:
            if not _is_transaction_not_found(exc):
                raise AppStoreGatewayError(
                    f'Apple Production transaction lookup failed ({exc.http_status_code})'
                ) from exc
        except RequestException as exc:
            raise AppStoreGatewayError(
                'Apple Production transaction lookup failed due to a network error'
            ) from exc
        else:
            return self._verify_response(
                response,
                requested_transaction_id=requested_transaction_id,
                expected_environment=Environment.PRODUCTION,
                verifier=self._production_verifier,
            )

        try:
            response = self._sandbox_client.get_transaction_info(requested_transaction_id)
        except APIException as exc:
            raise AppStoreGatewayError(
                f'Apple Sandbox transaction lookup failed ({exc.http_status_code})'
            ) from exc
        except RequestException as exc:
            raise AppStoreGatewayError(
                'Apple Sandbox transaction lookup failed due to a network error'
            ) from exc
        return self._verify_response(
            response,
            requested_transaction_id=requested_transaction_id,
            expected_environment=Environment.SANDBOX,
            verifier=self._sandbox_verifier,
        )

    def verify_signed_transaction(
        self,
        signed_transaction: str,
        *,
        expected_environment: Environment,
        requested_transaction_id: str | None = None,
    ) -> VerifiedAppStoreTransaction:
        verifier = self._verifier_for(expected_environment)
        return self._verify_signed_transaction(
            signed_transaction,
            requested_transaction_id=requested_transaction_id,
            expected_environment=expected_environment,
            verifier=verifier,
        )

    def verify_notification(self, signed_payload: str) -> VerifiedAppStoreNotification:
        normalized_payload = signed_payload.strip()
        if not normalized_payload:
            raise AppStoreValidationError('Apple notification signed payload is required')

        try:
            return self._verify_notification_with(
                normalized_payload,
                expected_environment=Environment.PRODUCTION,
                verifier=self._production_verifier,
            )
        except AppStoreValidationError:
            return self._verify_notification_with(
                normalized_payload,
                expected_environment=Environment.SANDBOX,
                verifier=self._sandbox_verifier,
            )

    def _verify_notification_with(
        self,
        signed_payload: str,
        *,
        expected_environment: Environment,
        verifier: _TransactionVerifier,
    ) -> VerifiedAppStoreNotification:
        try:
            payload = verifier.verify_and_decode_notification(signed_payload)
        except VerificationException as exc:
            _raise_verification_error(exc, 'notification')
        except AppStoreGatewayError:
            raise
        except (ValueError, TypeError) as exc:
            raise AppStoreValidationError(
                'Apple notification signature verification failed'
            ) from exc

        environment = _notification_environment(payload)
        if environment != expected_environment:
            raise AppStoreValidationError(
                'Apple notification environment does not match its signature verifier'
            )

        data = getattr(payload, 'data', None)
        transaction: VerifiedAppStoreTransaction | None = None
        renewal_info: VerifiedAppStoreRenewalInfo | None = None
        if data is not None:
            signed_transaction = _optional_string(data, 'signedTransactionInfo')
            if signed_transaction is not None:
                transaction = self._verify_signed_transaction(
                    signed_transaction,
                    requested_transaction_id=None,
                    expected_environment=expected_environment,
                    verifier=verifier,
                    allow_inactive=True,
                )
            signed_renewal = _optional_string(data, 'signedRenewalInfo')
            if signed_renewal is not None:
                renewal_info = self._verify_renewal_info(
                    signed_renewal,
                    expected_environment=expected_environment,
                    verifier=verifier,
                )

        notification_uuid = _required_string(payload, 'notificationUUID', 'notification UUID')
        notification_type = (
            _enum_or_raw_value(payload, 'notificationType', 'rawNotificationType')
            or 'UNKNOWN'
        )
        subtype = _enum_or_raw_value(payload, 'subtype', 'rawSubtype')
        return VerifiedAppStoreNotification(
            notification_uuid=notification_uuid,
            notification_type=notification_type,
            subtype=subtype,
            signed_date_ms=_optional_int(payload, 'signedDate'),
            environment=environment,
            transaction=transaction,
            renewal_info=renewal_info,
            signed_payload=signed_payload,
        )

    def _verify_renewal_info(
        self,
        signed_renewal_info: str,
        *,
        expected_environment: Environment,
        verifier: _TransactionVerifier,
    ) -> VerifiedAppStoreRenewalInfo:
        try:
            payload = verifier.verify_and_decode_renewal_info(signed_renewal_info)
        except VerificationException as exc:
            _raise_verification_error(exc, 'renewal info')
        except (ValueError, TypeError) as exc:
            raise AppStoreValidationError(
                'Apple renewal info signature verification failed'
            ) from exc

        environment = getattr(payload, 'environment', None)
        if environment != expected_environment:
            raise AppStoreValidationError('Apple renewal environment does not match notification')
        product_id = _required_string(payload, 'productId', 'renewal product id')
        if product_id not in self._allowed_product_ids:
            raise AppStoreValidationError('Apple renewal product is not allowed')
        return VerifiedAppStoreRenewalInfo(
            original_transaction_id=_required_string(
                payload,
                'originalTransactionId',
                'renewal original transaction id',
            ),
            product_id=product_id,
            environment=environment,
            app_account_token=_optional_string(payload, 'appAccountToken'),
            grace_period_expires_date_ms=_optional_int(payload, 'gracePeriodExpiresDate'),
            is_in_billing_retry_period=bool(
                getattr(payload, 'isInBillingRetryPeriod', False)
            ),
            expiration_intent=getattr(payload, 'expirationIntent', None),
            signed_renewal_info=signed_renewal_info,
            auto_renew=_optional_auto_renew_status(payload),
            signed_date_ms=_optional_int(payload, 'signedDate'),
        )

    def _verify_response(
        self,
        response: object,
        *,
        requested_transaction_id: str,
        expected_environment: Environment,
        verifier: _TransactionVerifier,
    ) -> VerifiedAppStoreTransaction:
        signed_transaction = getattr(response, 'signedTransactionInfo', None)
        if not isinstance(signed_transaction, str) or not signed_transaction.strip():
            raise AppStoreValidationError('Apple response is missing signed transaction data')
        return self._verify_signed_transaction(
            signed_transaction,
            requested_transaction_id=requested_transaction_id,
            expected_environment=expected_environment,
            verifier=verifier,
        )

    def _verify_signed_transaction(
        self,
        signed_transaction: str,
        *,
        requested_transaction_id: str | None,
        expected_environment: Environment,
        verifier: _TransactionVerifier,
        allow_inactive: bool = False,
    ) -> VerifiedAppStoreTransaction:
        try:
            payload = verifier.verify_and_decode_signed_transaction(signed_transaction)
        except VerificationException as exc:
            if exc.status == VerificationStatus.RETRYABLE_VERIFICATION_FAILURE:
                raise AppStoreGatewayError(
                    'Apple transaction verification is temporarily unavailable'
                ) from exc
            raise AppStoreValidationError('Apple transaction signature verification failed') from exc
        except (ValueError, TypeError) as exc:
            raise AppStoreValidationError('Apple transaction signature verification failed') from exc
        return self._validate_payload(
            payload,
            requested_transaction_id=requested_transaction_id,
            expected_environment=expected_environment,
            signed_transaction=signed_transaction,
            allow_inactive=allow_inactive,
        )

    def _validate_payload(
        self,
        payload: object,
        *,
        requested_transaction_id: str | None,
        expected_environment: Environment,
        signed_transaction: str,
        allow_inactive: bool = False,
    ) -> VerifiedAppStoreTransaction:
        transaction_id = _required_string(payload, 'transactionId', 'transaction id')
        if requested_transaction_id is not None and transaction_id != requested_transaction_id:
            raise AppStoreValidationError('Apple transaction id does not match the requested transaction')

        bundle_id = _required_string(payload, 'bundleId', 'bundle id')
        if bundle_id != self._bundle_id:
            raise AppStoreValidationError('Apple transaction bundle id does not match this app')

        environment = getattr(payload, 'environment', None)
        if environment != expected_environment:
            raise AppStoreValidationError('Apple transaction environment does not match the lookup environment')

        product_id = _required_string(payload, 'productId', 'product id')
        if product_id not in self._allowed_product_ids:
            raise AppStoreValidationError('Apple transaction product is not allowed')

        revocation_date_ms = _optional_int(payload, 'revocationDate')
        if revocation_date_ms is not None and not allow_inactive:
            raise AppStoreValidationError('Apple transaction was revoked')

        expires_date_ms = _optional_int(payload, 'expiresDate')
        if product_id in SUBSCRIPTION_PRODUCT_IDS and not allow_inactive:
            now_ms = int(self._clock() * 1000)
            if expires_date_ms is None or expires_date_ms <= now_ms:
                raise AppStoreValidationError('Apple subscription transaction is expired')

        original_transaction_id = (
            _optional_string(payload, 'originalTransactionId') or transaction_id
        )
        return VerifiedAppStoreTransaction(
            transaction_id=transaction_id,
            original_transaction_id=original_transaction_id,
            bundle_id=bundle_id,
            product_id=product_id,
            environment=environment,
            app_account_token=_optional_string(payload, 'appAccountToken'),
            purchase_date_ms=_optional_int(payload, 'purchaseDate'),
            expires_date_ms=expires_date_ms,
            revocation_date_ms=revocation_date_ms,
            transaction_type=getattr(payload, 'type', None),
            signed_transaction=signed_transaction,
        )

    def _verifier_for(self, environment: Environment) -> _TransactionVerifier:
        if environment == Environment.PRODUCTION:
            return self._production_verifier
        if environment == Environment.SANDBOX:
            return self._sandbox_verifier
        raise AppStoreValidationError(f'Unsupported Apple environment: {environment}')


def _validate_config(config: AppStoreGatewayConfig) -> None:
    if not config.key_id.strip():
        raise ValueError('App Store key id is required')
    if not config.issuer_id.strip():
        raise ValueError('App Store issuer id is required')
    if not config.bundle_id.strip():
        raise ValueError('App Store bundle id is required')
    if config.app_apple_id <= 0:
        raise ValueError('App Store appAppleId must be positive')
    _validate_product_ids(config.allowed_product_ids)


def _validate_product_ids(product_ids: Collection[str]) -> frozenset[str]:
    resolved = frozenset(product_ids)
    if resolved != APP_STORE_PRODUCT_IDS:
        raise ValueError('Gateway must allow exactly the four App Store product ids')
    return resolved


def _read_required_file(path: Path, label: str) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise AppStoreGatewayError(f'{label} cannot be read: {path}') from exc
    if not data:
        raise AppStoreGatewayError(f'{label} is empty: {path}')
    return data


def _read_root_certificates(directory: Path) -> list[bytes]:
    if not directory.is_dir():
        raise AppStoreGatewayError(
            f'Apple root certificates directory cannot be read: {directory}'
        )
    certificates = [path.read_bytes() for path in sorted(directory.glob('*.cer'))]
    if not certificates or any(not certificate for certificate in certificates):
        raise AppStoreGatewayError('Apple root certificates are missing or empty')
    return certificates


def _is_transaction_not_found(exc: APIException) -> bool:
    return (
        exc.api_error == APIError.TRANSACTION_ID_NOT_FOUND
        or exc.raw_api_error == APIError.TRANSACTION_ID_NOT_FOUND.value
    )


def _required_string(payload: object, attribute: str, label: str) -> str:
    value = _optional_string(payload, attribute)
    if value is None:
        raise AppStoreValidationError(f'Apple transaction is missing {label}')
    return value


def _optional_string(payload: object, attribute: str) -> str | None:
    value = getattr(payload, attribute, None)
    if value is None:
        return None
    resolved = str(value).strip()
    return resolved or None


def _optional_int(payload: object, attribute: str) -> int | None:
    value = getattr(payload, attribute, None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AppStoreValidationError(f'Apple transaction has invalid {attribute}') from exc


def _optional_auto_renew_status(payload: object) -> bool | None:
    raw_value = getattr(payload, 'autoRenewStatus', None)
    if raw_value is None:
        return None

    value = getattr(raw_value, 'value', raw_value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)

    normalized = str(value).strip().upper()
    if normalized in {'0', 'OFF'}:
        return False
    if normalized in {'1', 'ON'}:
        return True

    enum_name = str(getattr(raw_value, 'name', '')).strip().upper()
    if enum_name == 'OFF':
        return False
    if enum_name == 'ON':
        return True
    raise AppStoreValidationError('Apple renewal info has invalid autoRenewStatus')


def _raise_verification_error(exc: VerificationException, label: str) -> None:
    if exc.status == VerificationStatus.RETRYABLE_VERIFICATION_FAILURE:
        raise AppStoreGatewayError(
            f'Apple {label} verification is temporarily unavailable'
        ) from exc
    raise AppStoreValidationError(f'Apple {label} signature verification failed') from exc


def _notification_environment(payload: object) -> Environment:
    for container_name in ('data', 'summary', 'appData'):
        container = getattr(payload, container_name, None)
        environment = getattr(container, 'environment', None) if container is not None else None
        if environment in (Environment.PRODUCTION, Environment.SANDBOX):
            return environment
    raise AppStoreValidationError('Apple notification environment is missing')


def _enum_or_raw_value(payload: object, enum_attribute: str, raw_attribute: str) -> str | None:
    value = getattr(payload, enum_attribute, None)
    if value is not None:
        resolved = getattr(value, 'value', value)
        text = str(resolved).strip()
        if text:
            return text
    return _optional_string(payload, raw_attribute)
