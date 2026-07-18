import 'dart:async';

import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:in_app_purchase_storekit/in_app_purchase_storekit.dart';

import '../../core/config/app_config.dart';
import '../../data/repositories/appslides_repository.dart';
import '../../domain/models/billing_plan.dart';
import 'store_billing_service.dart';

abstract interface class AppleStorePurchaseGateway {
  Stream<List<PurchaseDetails>> get purchaseStream;

  Future<bool> isAvailable();

  Future<ProductDetailsResponse> queryProductDetails(Set<String> productIds);

  Future<bool> buyProduct(
    ProductDetails product, {
    required String appAccountToken,
    required bool consumable,
  });

  Future<void> restorePurchases();

  Future<void> completePurchase(PurchaseDetails purchase);
}

class InAppPurchaseAppleStoreGateway implements AppleStorePurchaseGateway {
  InAppPurchaseAppleStoreGateway({InAppPurchase? inAppPurchase})
      : _inAppPurchase = inAppPurchase ?? InAppPurchase.instance;

  final InAppPurchase _inAppPurchase;

  @override
  Stream<List<PurchaseDetails>> get purchaseStream =>
      _inAppPurchase.purchaseStream;

  @override
  Future<bool> isAvailable() => _inAppPurchase.isAvailable();

  @override
  Future<ProductDetailsResponse> queryProductDetails(Set<String> productIds) {
    return _inAppPurchase.queryProductDetails(productIds);
  }

  @override
  Future<bool> buyProduct(
    ProductDetails product, {
    required String appAccountToken,
    required bool consumable,
  }) {
    final purchaseParam = Sk2PurchaseParam(
      productDetails: product,
      applicationUserName: appAccountToken,
    );
    if (consumable) {
      return _inAppPurchase.buyConsumable(purchaseParam: purchaseParam);
    }
    return _inAppPurchase.buyNonConsumable(purchaseParam: purchaseParam);
  }

  @override
  Future<void> restorePurchases() => _inAppPurchase.restorePurchases();

  @override
  Future<void> completePurchase(PurchaseDetails purchase) {
    return _inAppPurchase.completePurchase(purchase);
  }
}

class ApplePurchaseDetailsMetadata {
  const ApplePurchaseDetailsMetadata({
    required this.isStoreKit2,
    required this.appAccountToken,
    required this.transactionTime,
  });

  final bool isStoreKit2;
  final String? appAccountToken;
  final DateTime? transactionTime;

  static ApplePurchaseDetailsMetadata fromPurchase(PurchaseDetails purchase) {
    if (purchase is! SK2PurchaseDetails) {
      return const ApplePurchaseDetailsMetadata(
        isStoreKit2: false,
        appAccountToken: null,
        transactionTime: null,
      );
    }
    return ApplePurchaseDetailsMetadata(
      isStoreKit2: true,
      appAccountToken: purchase.appAccountToken,
      transactionTime: _parseTransactionTime(purchase.transactionDate),
    );
  }

  static DateTime? _parseTransactionTime(String? value) {
    final normalized = value?.trim();
    if (normalized == null || normalized.isEmpty) {
      return null;
    }
    final milliseconds = int.tryParse(normalized);
    if (milliseconds != null) {
      try {
        return DateTime.fromMillisecondsSinceEpoch(milliseconds, isUtc: true);
      } on ArgumentError {
        return null;
      }
    }
    return DateTime.tryParse(normalized)?.toUtc();
  }
}

String? _normalizeAppAccountToken(String? value) {
  final normalized = value?.trim().toLowerCase();
  return normalized == null || normalized.isEmpty ? null : normalized;
}

typedef ApplePurchaseDetailsMetadataExtractor = ApplePurchaseDetailsMetadata
    Function(PurchaseDetails purchase);

enum _AppleStoreOperation { purchase, restore }

class AppleStoreBillingService implements StoreBillingService {
  AppleStoreBillingService({
    required AppSlidesRepository repository,
    AppleStorePurchaseGateway? gateway,
    InAppPurchase? inAppPurchase,
    Duration restoreSettlementDelay = defaultRestoreSettlementDelay,
    Duration restoreTimeout = defaultRestoreTimeout,
    DateTime Function()? now,
    ApplePurchaseDetailsMetadataExtractor? purchaseDetailsMetadata,
  })  : assert(gateway == null || inAppPurchase == null),
        _repository = repository,
        _gateway = gateway ??
            InAppPurchaseAppleStoreGateway(inAppPurchase: inAppPurchase),
        _restoreSettlementDelay = restoreSettlementDelay,
        _restoreTimeout = restoreTimeout,
        _now = now ?? DateTime.now,
        _purchaseDetailsMetadata = purchaseDetailsMetadata ??
            ApplePurchaseDetailsMetadata.fromPurchase;

  static const Duration defaultRestoreSettlementDelay = Duration(seconds: 1);
  static const Duration defaultRestoreTimeout = Duration(seconds: 12);

  static const Map<String, String> defaultProductIdsByPlan = <String, String>{
    'week': 'weekly_readings',
    'month': 'monthly_readings',
    'one10': 'one10_readings',
    'one40': 'one40_readings',
  };

  final AppSlidesRepository _repository;
  final AppleStorePurchaseGateway _gateway;
  final Duration _restoreSettlementDelay;
  final Duration _restoreTimeout;
  final DateTime Function() _now;
  final ApplePurchaseDetailsMetadataExtractor _purchaseDetailsMetadata;
  final Map<String, ProductDetails> _productsByPlanKey =
      <String, ProductDetails>{};

  StreamSubscription<List<PurchaseDetails>>? _purchaseSubscription;
  Future<void> _purchaseUpdateQueue = Future<void>.value();
  Completer<StoreBillingResult>? _activePurchaseCompleter;
  Completer<StoreBillingResult?>? _restoreCompleter;
  _AppleStoreOperation? _activeOperation;
  Timer? _operationTimer;
  Timer? _restoreSettleTimer;
  String? _activeProductId;
  String? _activeAppAccountToken;
  DateTime? _activeCheckoutStartedAt;
  StoreBillingResult? _latestRestoreResult;
  Object? _restoreError;
  int _restoredItems = 0;
  int _restoreVerifiedItems = 0;
  int _restoreFailedItems = 0;
  final List<String> _restoreWarnings = <String>[];
  bool _nativeRestoreCompleted = false;
  bool _restoreCompletionRequested = false;
  bool _disposed = false;
  Object? _lastError;

  Object? get lastError => _lastError;

  static String productIdForPlan(BillingPlan plan) {
    return defaultProductIdsByPlan[plan.key] ?? '';
  }

  @override
  Future<void> initialize() async {
    _ensureNotDisposed();
    _purchaseSubscription ??= _gateway.purchaseStream.listen(
      _enqueuePurchaseUpdates,
      onError: _enqueuePurchaseStreamError,
    );
  }

  @override
  Future<List<StoreBillingProduct>> loadProducts(
    List<BillingPlan> plans,
  ) async {
    _ensureNotDisposed();
    await initialize();
    if (!await _gateway.isAvailable()) {
      throw StateError('App Store purchases are unavailable on this device.');
    }

    final plansByProductId = <String, BillingPlan>{};
    for (final plan in plans) {
      final productId = productIdForPlan(plan);
      if (productId.isNotEmpty) {
        plansByProductId[productId] = plan;
      }
    }
    final missingProductIds = plansByProductId.entries
        .where((entry) => !_productsByPlanKey.containsKey(entry.value.key))
        .map((entry) => entry.key)
        .toSet();
    if (missingProductIds.isNotEmpty) {
      final response = await _gateway.queryProductDetails(missingProductIds);
      if (response.error != null) {
        throw StateError(response.error!.message);
      }
      for (final product in response.productDetails) {
        final plan = plansByProductId[product.id];
        if (plan != null) {
          _productsByPlanKey[plan.key] = product;
        }
      }
    }

    return <StoreBillingProduct>[
      for (final plan in plans)
        if (_productsByPlanKey[plan.key] case final product?)
          StoreBillingProduct(
            planKey: plan.key,
            productId: product.id,
            localizedPrice: product.price,
          ),
    ];
  }

  @override
  Future<StoreBillingResult> purchasePlan(BillingPlan plan) async {
    _ensureCanStartOperation();
    final completer = Completer<StoreBillingResult>();
    _activeOperation = _AppleStoreOperation.purchase;
    _activePurchaseCompleter = completer;
    _activeCheckoutStartedAt = _now().toUtc();
    _lastError = null;
    _operationTimer = Timer(
      const Duration(minutes: 5),
      () => _failPurchase(
        completer,
        TimeoutException('App Store purchase confirmation timed out.'),
      ),
    );
    unawaited(_startPurchase(plan, completer));
    return completer.future;
  }

  @override
  Future<StoreBillingResult?> restorePurchases() async {
    _ensureCanStartOperation();
    final completer = Completer<StoreBillingResult?>();
    _activeOperation = _AppleStoreOperation.restore;
    _restoreCompleter = completer;
    _lastError = null;
    _latestRestoreResult = null;
    _restoreError = null;
    _restoredItems = 0;
    _restoreVerifiedItems = 0;
    _restoreFailedItems = 0;
    _restoreWarnings.clear();
    _nativeRestoreCompleted = false;
    _restoreCompletionRequested = false;
    _operationTimer = Timer(
      _restoreTimeout,
      () => _requestRestoreCompletion(completer),
    );
    unawaited(_startRestore(completer));
    return completer.future;
  }

  @override
  Future<void> dispose() async {
    if (_disposed) {
      return;
    }
    _disposed = true;
    _operationTimer?.cancel();
    _restoreSettleTimer?.cancel();

    final purchaseCompleter = _activePurchaseCompleter;
    final restoreCompleter = _restoreCompleter;
    _clearOperation();

    await _purchaseSubscription?.cancel();
    _purchaseSubscription = null;
    _productsByPlanKey.clear();

    final error = StateError('Apple Store billing service is disposed.');
    if (purchaseCompleter != null && !purchaseCompleter.isCompleted) {
      purchaseCompleter.completeError(error);
    }
    if (restoreCompleter != null && !restoreCompleter.isCompleted) {
      restoreCompleter.completeError(error);
    }
  }

  Future<void> _startPurchase(
    BillingPlan plan,
    Completer<StoreBillingResult> completer,
  ) async {
    try {
      await initialize();
      if (!_isActivePurchase(completer)) {
        return;
      }

      final productId = productIdForPlan(plan);
      if (productId.isEmpty) {
        throw StateError('App Store product id is missing for ${plan.key}.');
      }
      await loadProducts(<BillingPlan>[plan]);
      if (!_isActivePurchase(completer)) {
        return;
      }
      final product = _productsByPlanKey[plan.key];
      if (product == null) {
        throw StateError('App Store product was not found: $productId');
      }

      final appAccountToken = await _repository.fetchAppleAppAccountToken();
      if (!_isActivePurchase(completer)) {
        return;
      }
      if (!AppConfig.isCanonicalUuid(appAccountToken)) {
        throw StateError(
          'Apple app account token must be a canonical UUID.',
        );
      }
      _activeProductId = productId;
      _activeAppAccountToken = appAccountToken;
      final started = await _gateway.buyProduct(
        product,
        appAccountToken: appAccountToken,
        consumable: !plan.recurring,
      );
      if (!_isActivePurchase(completer)) {
        return;
      }
      if (!started) {
        throw StateError('App Store purchase was not started.');
      }
    } catch (error) {
      _failPurchase(completer, error);
    }
  }

  Future<void> _startRestore(
    Completer<StoreBillingResult?> completer,
  ) async {
    try {
      await initialize();
      if (!_isActiveRestore(completer)) {
        return;
      }
      if (!await _gateway.isAvailable()) {
        throw StateError('App Store purchases are unavailable on this device.');
      }
      if (!_isActiveRestore(completer)) {
        return;
      }
      await _gateway.restorePurchases();
      _enqueuePurchaseStreamAction(() async {
        if (!_isActiveRestore(completer)) {
          return;
        }
        _nativeRestoreCompleted = true;
        if (_restoreCompletionRequested) {
          _finishRestore(completer);
        }
      });
    } catch (error) {
      _enqueuePurchaseStreamAction(() async {
        if (_isActiveRestore(completer)) {
          _failRestore(completer, error);
        }
      });
    }
  }

  void _enqueuePurchaseUpdates(List<PurchaseDetails> purchases) {
    _enqueuePurchaseStreamAction(() => _handlePurchaseUpdates(purchases));
  }

  void _enqueuePurchaseStreamError(Object error, StackTrace stackTrace) {
    _enqueuePurchaseStreamAction(() async => _handleStreamError(error));
  }

  void _enqueuePurchaseStreamAction(Future<void> Function() action) {
    _purchaseUpdateQueue = _purchaseUpdateQueue.then((_) async {
      if (!_disposed) {
        await action();
      }
    }).catchError((Object error, StackTrace stackTrace) {
      if (!_disposed) {
        _handleStreamError(error);
      }
    });
  }

  Future<void> _handlePurchaseUpdates(List<PurchaseDetails> purchases) async {
    final restoreCompleter = _activeOperation == _AppleStoreOperation.restore
        ? _restoreCompleter
        : null;
    var sawRestoredItem = false;

    for (final purchase in purchases) {
      switch (purchase.status) {
        case PurchaseStatus.pending:
          continue;
        case PurchaseStatus.error:
          final error = StateError(
            purchase.error?.message ?? 'App Store purchase failed.',
          );
          if (restoreCompleter != null && _isActiveRestore(restoreCompleter)) {
            _restoredItems += 1;
            _recordRestoreFailure(error);
            sawRestoredItem = true;
          } else {
            _failMatchingActivePurchase(purchase, error);
          }
          break;
        case PurchaseStatus.canceled:
          final error = StateError('App Store purchase was canceled.');
          if (restoreCompleter != null && _isActiveRestore(restoreCompleter)) {
            _restoredItems += 1;
            _recordRestoreFailure(error);
            sawRestoredItem = true;
          } else {
            _failMatchingActivePurchase(purchase, error);
          }
          break;
        case PurchaseStatus.purchased:
          await _processPurchased(purchase);
          break;
        case PurchaseStatus.restored:
          if (restoreCompleter == null || !_isActiveRestore(restoreCompleter)) {
            try {
              await _processRestored(purchase);
            } catch (error) {
              _lastError = error;
            }
            continue;
          }
          sawRestoredItem = true;
          _restoredItems += 1;
          try {
            _latestRestoreResult = await _processRestored(purchase);
            _restoreVerifiedItems += 1;
          } catch (error) {
            _lastError = error;
            _recordRestoreFailure(error);
          }
          break;
      }
    }

    if (sawRestoredItem &&
        restoreCompleter != null &&
        _isActiveRestore(restoreCompleter)) {
      _scheduleRestoreCompletion(restoreCompleter);
    }
  }

  Future<void> _processPurchased(PurchaseDetails purchase) async {
    final completer = _matchingActivePurchase(purchase);
    try {
      final result = await _verifyPurchase(purchase, operation: 'purchase');
      if (_disposed) {
        return;
      }
      if (purchase.pendingCompletePurchase) {
        await _gateway.completePurchase(purchase);
      }
      if (completer != null && _isActivePurchase(completer)) {
        _completePurchase(completer, result);
      }
    } catch (error) {
      _lastError = error;
      if (completer != null && _isActivePurchase(completer)) {
        _failPurchase(completer, error);
      }
    }
  }

  Future<StoreBillingResult> _processRestored(PurchaseDetails purchase) async {
    final result = await _verifyPurchase(purchase, operation: 'restore');
    if (_disposed) {
      throw StateError('Apple Store billing service is disposed.');
    }
    if (purchase.pendingCompletePurchase) {
      await _gateway.completePurchase(purchase);
    }
    return result;
  }

  Future<StoreBillingResult> _verifyPurchase(
    PurchaseDetails purchase, {
    required String operation,
  }) async {
    final transactionId = purchase.purchaseID?.trim();
    if (transactionId == null || transactionId.isEmpty) {
      throw StateError('App Store transaction id is missing.');
    }
    try {
      final summary = await _repository.verifyApplePurchase(
        transactionId: transactionId,
        productId: purchase.productID,
        operation: operation,
        clientSignedData: purchase.verificationData.serverVerificationData,
      );
      return StoreBillingResult(
        summary: summary,
        transactionReference: 'app_store:$transactionId',
      );
    } catch (error) {
      if (error is StateError && error.message.contains('transaction id')) {
        rethrow;
      }
      throw StateError(
        'Apple purchase verification failed. The transaction was not '
        'completed and can be retried: $error',
      );
    }
  }

  void _scheduleRestoreCompletion(
    Completer<StoreBillingResult?> completer,
  ) {
    _restoreSettleTimer?.cancel();
    _restoreSettleTimer = Timer(_restoreSettlementDelay, () {
      _requestRestoreCompletion(completer);
    });
  }

  void _requestRestoreCompletion(
    Completer<StoreBillingResult?> completer,
  ) {
    _enqueuePurchaseStreamAction(() async {
      if (!_isActiveRestore(completer)) {
        return;
      }
      _restoreCompletionRequested = true;
      if (_nativeRestoreCompleted) {
        _finishRestore(completer);
      }
    });
  }

  void _finishRestore(Completer<StoreBillingResult?> completer) {
    if (!_isActiveRestore(completer) || !_nativeRestoreCompleted) {
      return;
    }
    final latestResult = _latestRestoreResult;
    if (_restoreVerifiedItems > 0 && latestResult != null) {
      _completeRestore(
        completer,
        StoreBillingResult(
          summary: latestResult.summary,
          transactionReference: latestResult.transactionReference,
          warnings: List<String>.unmodifiable(_restoreWarnings),
          partialFailureCount: _restoreFailedItems,
        ),
      );
      return;
    }
    if (_restoredItems == 0) {
      _completeRestore(completer, null);
      return;
    }
    _failRestore(
      completer,
      _restoreError ?? StateError('No App Store purchases could be restored.'),
    );
  }

  void _recordRestoreFailure(Object error) {
    _restoreError ??= error;
    _restoreFailedItems += 1;
    _restoreWarnings.add(error.toString());
  }

  void _handleStreamError(Object error) {
    _lastError = error;
    final purchaseCompleter = _activePurchaseCompleter;
    if (_activeOperation == _AppleStoreOperation.purchase &&
        purchaseCompleter != null) {
      _failPurchase(purchaseCompleter, error);
      return;
    }
    final restoreCompleter = _restoreCompleter;
    if (_activeOperation == _AppleStoreOperation.restore &&
        restoreCompleter != null) {
      _failRestore(restoreCompleter, error);
    }
  }

  Completer<StoreBillingResult>? _matchingActivePurchase(
    PurchaseDetails purchase,
  ) {
    final completer = _activePurchaseCompleter;
    if (_activeOperation != _AppleStoreOperation.purchase ||
        completer == null ||
        _activeProductId != purchase.productID) {
      return null;
    }
    if (purchase.status != PurchaseStatus.purchased) {
      return completer;
    }
    final metadata = _purchaseDetailsMetadata(purchase);
    if (!metadata.isStoreKit2) {
      return completer;
    }
    final expectedToken = _activeAppAccountToken;
    final checkoutStartedAt = _activeCheckoutStartedAt;
    final transactionTime = metadata.transactionTime;
    if (expectedToken == null ||
        checkoutStartedAt == null ||
        _normalizeAppAccountToken(metadata.appAccountToken) !=
            _normalizeAppAccountToken(expectedToken) ||
        transactionTime == null ||
        transactionTime.isBefore(_truncateToSeconds(checkoutStartedAt))) {
      return null;
    }
    return completer;
  }

  static DateTime _truncateToSeconds(DateTime value) {
    return DateTime.fromMillisecondsSinceEpoch(
      (value.toUtc().millisecondsSinceEpoch ~/ 1000) * 1000,
      isUtc: true,
    );
  }

  void _failMatchingActivePurchase(PurchaseDetails purchase, Object error) {
    final completer = _matchingActivePurchase(purchase);
    if (completer != null) {
      _failPurchase(completer, error);
    }
  }

  void _completePurchase(
    Completer<StoreBillingResult> completer,
    StoreBillingResult result,
  ) {
    if (!_isActivePurchase(completer) || completer.isCompleted) {
      return;
    }
    completer.complete(result);
    _clearOperation();
  }

  void _failPurchase(
    Completer<StoreBillingResult> completer,
    Object error,
  ) {
    if (!_isActivePurchase(completer) || completer.isCompleted) {
      return;
    }
    _lastError = error;
    completer.completeError(error);
    _clearOperation();
  }

  void _completeRestore(
    Completer<StoreBillingResult?> completer,
    StoreBillingResult? result,
  ) {
    if (!_isActiveRestore(completer) || completer.isCompleted) {
      return;
    }
    completer.complete(result);
    _clearOperation();
  }

  void _failRestore(
    Completer<StoreBillingResult?> completer,
    Object error,
  ) {
    if (!_isActiveRestore(completer) || completer.isCompleted) {
      return;
    }
    _lastError = error;
    completer.completeError(error);
    _clearOperation();
  }

  void _ensureCanStartOperation() {
    _ensureNotDisposed();
    if (_activeOperation != null) {
      throw StateError(
        'Another store billing operation is already in progress.',
      );
    }
  }

  void _ensureNotDisposed() {
    if (_disposed) {
      throw StateError('Apple Store billing service is disposed.');
    }
  }

  bool _isActivePurchase(Completer<StoreBillingResult> completer) {
    return !_disposed &&
        _activeOperation == _AppleStoreOperation.purchase &&
        identical(_activePurchaseCompleter, completer);
  }

  bool _isActiveRestore(Completer<StoreBillingResult?> completer) {
    return !_disposed &&
        _activeOperation == _AppleStoreOperation.restore &&
        identical(_restoreCompleter, completer);
  }

  void _clearOperation() {
    _operationTimer?.cancel();
    _operationTimer = null;
    _restoreSettleTimer?.cancel();
    _restoreSettleTimer = null;
    _activeOperation = null;
    _activePurchaseCompleter = null;
    _restoreCompleter = null;
    _activeProductId = null;
    _activeAppAccountToken = null;
    _activeCheckoutStartedAt = null;
    _latestRestoreResult = null;
    _restoreError = null;
    _restoredItems = 0;
    _restoreVerifiedItems = 0;
    _restoreFailedItems = 0;
    _restoreWarnings.clear();
    _nativeRestoreCompleted = false;
    _restoreCompletionRequested = false;
  }
}
