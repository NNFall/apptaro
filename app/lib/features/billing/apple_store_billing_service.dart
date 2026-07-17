import 'dart:async';

import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:in_app_purchase_storekit/in_app_purchase_storekit.dart';

import '../../core/config/app_config.dart';
import '../../data/repositories/appslides_repository.dart';
import '../../domain/models/billing_plan.dart';
import '../../domain/models/billing_summary.dart';
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

enum _AppleStoreOperation { purchase, restore }

class AppleStoreBillingService implements StoreBillingService {
  AppleStoreBillingService({
    required AppSlidesRepository repository,
    AppleStorePurchaseGateway? gateway,
    InAppPurchase? inAppPurchase,
    Duration restoreSettlementDelay = defaultRestoreSettlementDelay,
  })  : assert(gateway == null || inAppPurchase == null),
        _repository = repository,
        _gateway = gateway ??
            InAppPurchaseAppleStoreGateway(inAppPurchase: inAppPurchase),
        _restoreSettlementDelay = restoreSettlementDelay;

  static const Duration defaultRestoreSettlementDelay = Duration(seconds: 1);

  static const Map<String, String> defaultProductIdsByPlan = <String, String>{
    'week': 'weekly_readings',
    'month': 'monthly_readings',
    'one10': 'one10_readings',
    'one40': 'one40_readings',
  };

  final AppSlidesRepository _repository;
  final AppleStorePurchaseGateway _gateway;
  final Duration _restoreSettlementDelay;

  StreamSubscription<List<PurchaseDetails>>? _purchaseSubscription;
  Future<void> _purchaseUpdateQueue = Future<void>.value();
  Completer<StoreBillingResult>? _activePurchaseCompleter;
  Completer<StoreBillingResult?>? _restoreCompleter;
  _AppleStoreOperation? _activeOperation;
  Timer? _operationTimer;
  Timer? _restoreSettleTimer;
  String? _activeProductId;
  StoreBillingResult? _latestRestoreResult;
  Object? _restoreError;
  int _restoredItems = 0;
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
  Future<StoreBillingResult> purchasePlan(BillingPlan plan) async {
    _ensureCanStartOperation();
    final completer = Completer<StoreBillingResult>();
    _activeOperation = _AppleStoreOperation.purchase;
    _activePurchaseCompleter = completer;
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
    _operationTimer = Timer(
      const Duration(seconds: 12),
      () => _finishRestore(completer),
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
      if (!await _gateway.isAvailable()) {
        throw StateError('App Store purchases are unavailable on this device.');
      }
      if (!_isActivePurchase(completer)) {
        return;
      }

      final response = await _gateway.queryProductDetails(<String>{productId});
      if (!_isActivePurchase(completer)) {
        return;
      }
      if (response.error != null) {
        throw StateError(response.error!.message);
      }
      if (response.productDetails.isEmpty) {
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
      final product = response.productDetails.firstWhere(
        (item) => item.id == productId,
        orElse: () => response.productDetails.first,
      );
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
        _completeRestore(completer, null);
        return;
      }
      if (!_isActiveRestore(completer)) {
        return;
      }
      await _gateway.restorePurchases();
    } catch (error) {
      _failRestore(completer, error);
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
            _restoreError ??= error;
            sawRestoredItem = true;
          } else {
            _failMatchingActivePurchase(purchase, error);
          }
          break;
        case PurchaseStatus.canceled:
          final error = StateError('App Store purchase was canceled.');
          if (restoreCompleter != null && _isActiveRestore(restoreCompleter)) {
            _restoreError ??= error;
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
          } catch (error) {
            _lastError = error;
            _restoreError ??= error;
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
      _enqueuePurchaseStreamAction(() async => _finishRestore(completer));
    });
  }

  void _finishRestore(Completer<StoreBillingResult?> completer) {
    if (!_isActiveRestore(completer)) {
      return;
    }
    final error = _restoreError;
    if (error != null) {
      _failRestore(completer, error);
      return;
    }
    if (_restoredItems == 0) {
      _completeRestore(completer, null);
      return;
    }
    final result = _latestRestoreResult;
    if (result != null) {
      _completeRestore(completer, result);
    }
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
    return completer;
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
    _latestRestoreResult = null;
    _restoreError = null;
    _restoredItems = 0;
  }
}
