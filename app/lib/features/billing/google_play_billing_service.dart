import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:in_app_purchase_android/in_app_purchase_android.dart';

import '../../core/config/app_config.dart';
import '../../data/repositories/appslides_repository.dart';
import '../../domain/models/billing_plan.dart';
import '../../domain/models/billing_summary.dart';
import 'store_billing_service.dart';

abstract interface class StorePurchaseGateway {
  Stream<List<PurchaseDetails>> get purchaseStream;

  Future<bool> isAvailable();

  Future<ProductDetailsResponse> queryProductDetails(Set<String> productIds);

  Future<bool> buyNonConsumable(ProductDetails product);

  Future<bool> buyConsumable(ProductDetails product);

  Future<void> restorePurchases();

  Future<void> completePurchase(PurchaseDetails purchase);

  Future<void> consumePurchase(PurchaseDetails purchase);
}

class InAppPurchaseStoreGateway implements StorePurchaseGateway {
  InAppPurchaseStoreGateway({InAppPurchase? inAppPurchase})
      : _inAppPurchase = inAppPurchase ?? InAppPurchase.instance;

  final InAppPurchase _inAppPurchase;

  @override
  Stream<List<PurchaseDetails>> get purchaseStream =>
      _inAppPurchase.purchaseStream;

  @override
  Future<bool> isAvailable() => _inAppPurchase.isAvailable();

  @override
  Future<ProductDetailsResponse> queryProductDetails(
    Set<String> productIds,
  ) {
    return _inAppPurchase.queryProductDetails(productIds);
  }

  @override
  Future<bool> buyNonConsumable(ProductDetails product) {
    return _inAppPurchase.buyNonConsumable(
      purchaseParam: PurchaseParam(productDetails: product),
    );
  }

  @override
  Future<bool> buyConsumable(ProductDetails product) {
    return _inAppPurchase.buyConsumable(
      purchaseParam: PurchaseParam(productDetails: product),
      autoConsume: false,
    );
  }

  @override
  Future<void> restorePurchases() async {
    await _inAppPurchase.restorePurchases();
  }

  @override
  Future<void> completePurchase(PurchaseDetails purchase) {
    return _inAppPurchase.completePurchase(purchase);
  }

  @override
  Future<void> consumePurchase(PurchaseDetails purchase) async {
    if (defaultTargetPlatform != TargetPlatform.android) {
      return;
    }
    final androidAddition = _inAppPurchase
        .getPlatformAddition<InAppPurchaseAndroidPlatformAddition>();
    await androidAddition.consumePurchase(purchase);
  }
}

enum _StoreOperation { purchase, restore }

class GooglePlayBillingService implements StoreBillingService {
  GooglePlayBillingService({
    required AppSlidesRepository repository,
    StorePurchaseGateway? gateway,
    InAppPurchase? inAppPurchase,
    String packageName = AppConfig.androidPackageName,
  })  : assert(gateway == null || inAppPurchase == null),
        _repository = repository,
        _gateway =
            gateway ?? InAppPurchaseStoreGateway(inAppPurchase: inAppPurchase),
        _packageName = packageName;

  static const Map<String, String> defaultProductIdsByPlan = <String, String>{
    'week': 'weekly_readings',
    'month': 'monthly_readings',
    'one10': 'one10_readings',
    'one40': 'one40_readings',
  };

  final AppSlidesRepository _repository;
  final StorePurchaseGateway _gateway;
  final String _packageName;

  StreamSubscription<List<PurchaseDetails>>? _purchaseSubscription;
  Future<void> _purchaseUpdateQueue = Future<void>.value();
  Completer<StoreBillingResult>? _activePurchaseCompleter;
  Completer<StoreBillingResult?>? _restoreCompleter;
  _StoreOperation? _activeOperation;
  Timer? _operationTimer;
  String? _activeProductId;
  bool _activeProductIsConsumable = false;
  bool _disposed = false;
  Object? _lastError;

  Object? get lastError => _lastError;

  @override
  Future<void> initialize() async {
    _ensureNotDisposed();
    _purchaseSubscription ??= _gateway.purchaseStream.listen(
      _enqueuePurchaseUpdates,
      onError: _handleStreamError,
    );
  }

  @override
  Future<StoreBillingResult> purchasePlan(BillingPlan plan) async {
    _ensureCanStartOperation();
    final completer = Completer<StoreBillingResult>();
    _activeOperation = _StoreOperation.purchase;
    _activePurchaseCompleter = completer;
    _lastError = null;
    _operationTimer = Timer(
      const Duration(minutes: 5),
      () => _failPurchase(
        completer,
        TimeoutException('Google Play purchase confirmation timed out.'),
      ),
    );
    unawaited(_startPurchase(plan, completer));
    return completer.future;
  }

  @override
  Future<StoreBillingResult?> restorePurchases() async {
    _ensureCanStartOperation();
    final completer = Completer<StoreBillingResult?>();
    _activeOperation = _StoreOperation.restore;
    _restoreCompleter = completer;
    _lastError = null;
    _operationTimer = Timer(
      const Duration(seconds: 12),
      () => _completeRestore(completer, null),
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
    _operationTimer = null;

    final purchaseCompleter = _activePurchaseCompleter;
    final restoreCompleter = _restoreCompleter;
    _clearOperation();

    await _purchaseSubscription?.cancel();
    _purchaseSubscription = null;

    final error = StateError('Google Play billing service is disposed.');
    if (purchaseCompleter != null && !purchaseCompleter.isCompleted) {
      purchaseCompleter.completeError(error);
    }
    if (restoreCompleter != null && !restoreCompleter.isCompleted) {
      restoreCompleter.completeError(error);
    }
  }

  static String productIdForPlan(BillingPlan plan) {
    if (plan.googleProductId.isNotEmpty) {
      return plan.googleProductId;
    }
    return defaultProductIdsByPlan[plan.key] ?? '';
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
        throw StateError(
          'Google Play product id is missing for plan ${plan.key}',
        );
      }
      if (!await _gateway.isAvailable()) {
        throw StateError(
          'Google Play purchases are unavailable on this device.',
        );
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
        throw StateError('Google Play product was not found: $productId');
      }

      _activeProductId = productId;
      _activeProductIsConsumable = !plan.recurring;
      final product = response.productDetails.first;
      final started = plan.recurring
          ? await _gateway.buyNonConsumable(product)
          : await _gateway.buyConsumable(product);
      if (!_isActivePurchase(completer)) {
        return;
      }
      if (!started) {
        throw StateError('Google Play purchase was not started.');
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

  Future<void> _handlePurchaseUpdates(List<PurchaseDetails> purchases) async {
    final restoreCompleter =
        _activeOperation == _StoreOperation.restore ? _restoreCompleter : null;
    StoreBillingResult? latestRestoreResult;
    Object? restoreError;
    var restoredItems = 0;

    for (final purchase in purchases) {
      switch (purchase.status) {
        case PurchaseStatus.pending:
          continue;
        case PurchaseStatus.error:
          final error = StateError(
            purchase.error?.message ?? 'Google Play purchase failed.',
          );
          if (restoreCompleter != null && _isActiveRestore(restoreCompleter)) {
            restoreError ??= error;
          } else {
            _failMatchingActivePurchase(purchase, error);
          }
          break;
        case PurchaseStatus.canceled:
          final error = StateError('Google Play purchase was canceled.');
          if (restoreCompleter != null && _isActiveRestore(restoreCompleter)) {
            restoreError ??= error;
          } else {
            _failMatchingActivePurchase(purchase, error);
          }
          break;
        case PurchaseStatus.purchased:
          await _processPurchased(purchase);
          break;
        case PurchaseStatus.restored:
          if (restoreCompleter == null || !_isActiveRestore(restoreCompleter)) {
            continue;
          }
          restoredItems += 1;
          try {
            latestRestoreResult = await _processRestored(purchase);
          } catch (error) {
            _lastError = error;
            restoreError ??= error;
          }
          break;
      }
    }

    if (restoreCompleter == null || !_isActiveRestore(restoreCompleter)) {
      return;
    }
    if (restoreError != null) {
      _failRestore(restoreCompleter, restoreError);
    } else if (restoredItems > 0 && latestRestoreResult != null) {
      _completeRestore(restoreCompleter, latestRestoreResult);
    }
  }

  void _enqueuePurchaseUpdates(List<PurchaseDetails> purchases) {
    _purchaseUpdateQueue = _purchaseUpdateQueue.then((_) async {
      if (_disposed) {
        return;
      }
      await _handlePurchaseUpdates(purchases);
    }).catchError((Object error, StackTrace stackTrace) {
      if (!_disposed) {
        _handleStreamError(error);
      }
    });
  }

  Future<void> _processPurchased(PurchaseDetails purchase) async {
    final completer = _matchingActivePurchase(purchase);
    try {
      final summary = await _verifyPurchase(purchase, restored: false);
      if (_shouldConsume(purchase)) {
        await _gateway.consumePurchase(purchase);
      }
      if (purchase.pendingCompletePurchase) {
        await _gateway.completePurchase(purchase);
      }
      if (completer != null && _isActivePurchase(completer)) {
        _completePurchase(
          completer,
          StoreBillingResult(
            summary: summary,
            transactionReference: _transactionReference(purchase),
          ),
        );
      }
    } catch (error) {
      _lastError = error;
      if (completer != null && _isActivePurchase(completer)) {
        _failPurchase(completer, error);
      }
    }
  }

  Future<StoreBillingResult> _processRestored(
    PurchaseDetails purchase,
  ) async {
    final summary = await _verifyPurchase(purchase, restored: true);
    if (purchase.pendingCompletePurchase) {
      await _gateway.completePurchase(purchase);
    }
    return StoreBillingResult(
      summary: summary,
      transactionReference: _transactionReference(purchase),
    );
  }

  Future<BillingSummary> _verifyPurchase(
    PurchaseDetails purchase, {
    required bool restored,
  }) {
    return _repository.verifyGooglePlayPurchase(
      productId: purchase.productID,
      purchaseToken: purchase.verificationData.serverVerificationData,
      packageName: _packageName,
      restored: restored,
    );
  }

  void _handleStreamError(Object error) {
    _lastError = error;
    _handleOperationError(error);
  }

  void _handleOperationError(Object error) {
    _lastError = error;
    final purchaseCompleter = _activePurchaseCompleter;
    if (_activeOperation == _StoreOperation.purchase &&
        purchaseCompleter != null) {
      _failPurchase(purchaseCompleter, error);
      return;
    }
    final restoreCompleter = _restoreCompleter;
    if (_activeOperation == _StoreOperation.restore &&
        restoreCompleter != null) {
      _failRestore(restoreCompleter, error);
    }
  }

  Completer<StoreBillingResult>? _matchingActivePurchase(
    PurchaseDetails purchase,
  ) {
    final completer = _activePurchaseCompleter;
    if (_activeOperation != _StoreOperation.purchase ||
        completer == null ||
        _activeProductId != purchase.productID) {
      return null;
    }
    return completer;
  }

  void _failMatchingActivePurchase(
    PurchaseDetails purchase,
    Object error,
  ) {
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
          'Another store billing operation is already in progress.');
    }
  }

  void _ensureNotDisposed() {
    if (_disposed) {
      throw StateError('Google Play billing service is disposed.');
    }
  }

  bool _isActivePurchase(Completer<StoreBillingResult> completer) {
    return !_disposed &&
        _activeOperation == _StoreOperation.purchase &&
        identical(_activePurchaseCompleter, completer);
  }

  bool _isActiveRestore(Completer<StoreBillingResult?> completer) {
    return !_disposed &&
        _activeOperation == _StoreOperation.restore &&
        identical(_restoreCompleter, completer);
  }

  void _clearOperation() {
    _operationTimer?.cancel();
    _operationTimer = null;
    _activeOperation = null;
    _activePurchaseCompleter = null;
    _restoreCompleter = null;
    _activeProductId = null;
    _activeProductIsConsumable = false;
  }

  bool _shouldConsume(PurchaseDetails purchase) {
    if (purchase.status != PurchaseStatus.purchased) {
      return false;
    }
    if (_activeProductId == purchase.productID) {
      return _activeProductIsConsumable;
    }
    return _isConsumableProductId(purchase.productID);
  }

  static bool _isConsumableProductId(String productId) {
    for (final entry in defaultProductIdsByPlan.entries) {
      if (entry.value == productId) {
        return entry.key == 'one10' || entry.key == 'one40';
      }
    }
    return false;
  }

  static String _transactionReference(PurchaseDetails purchase) {
    final purchaseId = purchase.purchaseID?.trim();
    if (purchaseId != null && purchaseId.isNotEmpty) {
      return 'google_play:$purchaseId';
    }
    final verificationData = purchase.verificationData.serverVerificationData;
    final fingerprintSource = verificationData.isEmpty
        ? '${purchase.productID}|${purchase.transactionDate ?? ''}|${purchase.status.name}'
        : '${purchase.productID}|$verificationData';
    return 'google_play:fallback:${_stableFingerprint(fingerprintSource)}';
  }

  static String _stableFingerprint(String value) {
    var first = 0x1505;
    var second = 0x45d9f3b;
    for (final codeUnit in value.codeUnits) {
      first = (((first << 5) - first) + codeUnit) & 0x7fffffff;
      second = (((second << 5) + second) ^ codeUnit) & 0x7fffffff;
    }
    final firstHex = first.toRadixString(16).padLeft(8, '0');
    final secondHex = second.toRadixString(16).padLeft(8, '0');
    return '$firstHex$secondHex';
  }
}
