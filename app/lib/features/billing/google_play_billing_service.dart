import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:in_app_purchase_android/in_app_purchase_android.dart';

import '../../core/config/app_config.dart';
import '../../data/repositories/appslides_repository.dart';
import '../../domain/models/billing_plan.dart';
import '../../domain/models/billing_summary.dart';
import 'store_billing_service.dart';

class GooglePlayBillingService implements StoreBillingService {
  GooglePlayBillingService({
    required AppSlidesRepository repository,
    InAppPurchase? inAppPurchase,
    String packageName = AppConfig.androidPackageName,
  })  : _repository = repository,
        _inAppPurchase = inAppPurchase ?? InAppPurchase.instance,
        _packageName = packageName;

  static const Map<String, String> defaultProductIdsByPlan = <String, String>{
    'week': 'weekly_readings',
    'month': 'monthly_readings',
    'one10': 'one10_readings',
    'one40': 'one40_readings',
  };

  final AppSlidesRepository _repository;
  final InAppPurchase _inAppPurchase;
  final String _packageName;

  StreamSubscription<List<PurchaseDetails>>? _purchaseSubscription;
  Completer<StoreBillingResult>? _activePurchaseCompleter;
  Completer<StoreBillingResult?>? _restoreCompleter;
  String? _activeProductId;
  bool _activeProductIsConsumable = false;
  Object? _lastError;

  Object? get lastError => _lastError;

  @override
  Future<void> initialize() async {
    _purchaseSubscription ??= _inAppPurchase.purchaseStream.listen(
      (items) => unawaited(_handlePurchaseUpdates(items)),
      onError: (Object error) {
        _lastError = error;
        _completeActivePurchaseError(error);
        _completeRestore(null);
      },
    );
  }

  @override
  Future<StoreBillingResult> purchasePlan(BillingPlan plan) async {
    await initialize();
    _lastError = null;

    final productId = productIdForPlan(plan);
    if (productId.isEmpty) {
      throw StateError(
          'Google Play product id is missing for plan ${plan.key}');
    }
    if (!await _inAppPurchase.isAvailable()) {
      throw StateError('Google Play purchases are unavailable on this device.');
    }

    final response =
        await _inAppPurchase.queryProductDetails(<String>{productId});
    if (response.error != null) {
      throw StateError(response.error!.message);
    }
    if (response.productDetails.isEmpty) {
      throw StateError('Google Play product was not found: $productId');
    }

    final product = response.productDetails.first;
    _activeProductId = productId;
    _activeProductIsConsumable = !plan.recurring;
    _activePurchaseCompleter = Completer<StoreBillingResult>();
    final purchaseParam = PurchaseParam(productDetails: product);
    final started = plan.recurring
        ? await _inAppPurchase.buyNonConsumable(purchaseParam: purchaseParam)
        : await _inAppPurchase.buyConsumable(
            purchaseParam: purchaseParam,
            autoConsume: false,
          );
    if (!started) {
      _activePurchaseCompleter = null;
      _activeProductId = null;
      _activeProductIsConsumable = false;
      throw StateError('Google Play purchase was not started.');
    }

    return _activePurchaseCompleter!.future.timeout(
      const Duration(minutes: 5),
      onTimeout: () {
        _activePurchaseCompleter = null;
        _activeProductId = null;
        _activeProductIsConsumable = false;
        throw TimeoutException('Google Play purchase confirmation timed out.');
      },
    );
  }

  @override
  Future<StoreBillingResult?> restorePurchases() async {
    await initialize();
    if (!await _inAppPurchase.isAvailable()) {
      return null;
    }
    _restoreCompleter = Completer<StoreBillingResult?>();
    await _inAppPurchase.restorePurchases();
    return _restoreCompleter!.future.timeout(
      const Duration(seconds: 12),
      onTimeout: () {
        _restoreCompleter = null;
        return null;
      },
    );
  }

  @override
  Future<void> dispose() async {
    await _purchaseSubscription?.cancel();
    _purchaseSubscription = null;
  }

  static String productIdForPlan(BillingPlan plan) {
    if (plan.googleProductId.isNotEmpty) {
      return plan.googleProductId;
    }
    return defaultProductIdsByPlan[plan.key] ?? '';
  }

  Future<void> _handlePurchaseUpdates(List<PurchaseDetails> purchases) async {
    for (final purchase in purchases) {
      switch (purchase.status) {
        case PurchaseStatus.pending:
          continue;
        case PurchaseStatus.error:
          final error =
              purchase.error?.message ?? 'Google Play purchase failed.';
          _lastError = error;
          _completeActivePurchaseError(StateError(error));
          _completeRestore(null);
          break;
        case PurchaseStatus.canceled:
          final error = StateError('Google Play purchase was canceled.');
          _lastError = error;
          _completeActivePurchaseError(error);
          _completeRestore(null);
          break;
        case PurchaseStatus.purchased:
        case PurchaseStatus.restored:
          await _verifyAndComplete(purchase);
          break;
      }
    }
  }

  Future<void> _verifyAndComplete(PurchaseDetails purchase) async {
    try {
      final summary = await _repository.verifyGooglePlayPurchase(
        productId: purchase.productID,
        purchaseToken: purchase.verificationData.serverVerificationData,
        packageName: _packageName,
        restored: purchase.status == PurchaseStatus.restored,
      );
      if (_shouldConsume(purchase)) {
        await _consumeAndroidPurchase(purchase);
      }
      if (purchase.pendingCompletePurchase) {
        await _inAppPurchase.completePurchase(purchase);
      }
      if (_activeProductId == null || _activeProductId == purchase.productID) {
        _activePurchaseCompleter?.complete(
          StoreBillingResult(
            summary: summary,
            paymentId: 'google_play:${purchase.productID}',
          ),
        );
        _activePurchaseCompleter = null;
        _activeProductId = null;
        _activeProductIsConsumable = false;
      }
      _completeRestore(
        StoreBillingResult(
          summary: summary,
          paymentId: 'google_play:restore',
        ),
      );
    } catch (error) {
      _lastError = error;
      if (_activeProductId == null || _activeProductId == purchase.productID) {
        _completeActivePurchaseError(error);
      }
      _completeRestore(null);
    }
  }

  void _completeActivePurchaseError(Object error) {
    final completer = _activePurchaseCompleter;
    if (completer != null && !completer.isCompleted) {
      completer.completeError(error);
    }
    _activePurchaseCompleter = null;
    _activeProductId = null;
    _activeProductIsConsumable = false;
  }

  void _completeRestore(StoreBillingResult? result) {
    final completer = _restoreCompleter;
    if (completer != null && !completer.isCompleted) {
      completer.complete(result);
    }
    _restoreCompleter = null;
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

  Future<void> _consumeAndroidPurchase(PurchaseDetails purchase) async {
    if (defaultTargetPlatform != TargetPlatform.android) {
      return;
    }
    final androidAddition =
        _inAppPurchase.getPlatformAddition<InAppPurchaseAndroidPlatformAddition>();
    await androidAddition.consumePurchase(purchase);
  }
}
