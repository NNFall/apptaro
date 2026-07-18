import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../data/api/appslides_api_client.dart';
import '../../data/repositories/appslides_repository.dart';
import '../../domain/models/billing_payment.dart';
import '../../domain/models/billing_summary.dart';
import 'apple_store_billing_service.dart';
import 'google_play_billing_service.dart';
import 'store_billing_service.dart';

typedef StoreBillingServiceBuilder = StoreBillingService Function(
  AppSlidesRepository repository,
);

enum BillingRestoreOutcome { idle, restored, noPurchases, partial, failed }

enum _BillingOperation { refreshSummary, checkout, restore, redeemPromo }

StoreBillingService createPlatformStoreBillingService({
  required AppSlidesRepository repository,
  required bool isWeb,
  required TargetPlatform targetPlatform,
  StoreBillingServiceBuilder? appleBuilder,
  StoreBillingServiceBuilder? googleBuilder,
}) {
  final useApple = !isWeb && targetPlatform == TargetPlatform.iOS;
  if (useApple) {
    return (appleBuilder ??
        (repository) => AppleStoreBillingService(repository: repository))(
      repository,
    );
  }
  return (googleBuilder ??
      (repository) => GooglePlayBillingService(repository: repository))(
    repository,
  );
}

class BillingController extends ChangeNotifier {
  BillingController({
    required AppSlidesRepository repository,
    StoreBillingService? storeBillingService,
  })  : _repository = repository,
        _storeBillingService = storeBillingService ??
            createPlatformStoreBillingService(
              repository: repository,
              isWeb: kIsWeb,
              targetPlatform: defaultTargetPlatform,
            );

  final AppSlidesRepository _repository;
  final StoreBillingService _storeBillingService;

  BillingSummary? _summary;
  BillingPayment? _payment;
  bool _loadingSummary = false;
  bool _creatingPayment = false;
  bool _disposed = false;
  _BillingOperation? _activeBillingOperation;
  String? _error;
  final Map<String, StoreBillingProduct> _productsByPlanKey =
      <String, StoreBillingProduct>{};
  BillingRestoreOutcome _restoreOutcome = BillingRestoreOutcome.idle;
  List<String> _restoreWarnings = const <String>[];
  int _restorePartialFailureCount = 0;

  BillingSummary? get summary => _summary;
  BillingPayment? get payment => _payment;
  bool get loadingSummary => _loadingSummary;
  bool get creatingPayment => _creatingPayment;
  String? get error => _error;
  BillingRestoreOutcome get restoreOutcome => _restoreOutcome;
  List<String> get restoreWarnings => _restoreWarnings;
  int get restorePartialFailureCount => _restorePartialFailureCount;

  String? localizedPriceForPlan(String planKey) {
    return _productsByPlanKey[planKey]?.localizedPrice;
  }

  Future<void> initialize() async {
    if (_disposed || _summary != null || _loadingSummary) {
      return;
    }
    await _storeBillingService.initialize();
    await refreshSummary();
  }

  Future<void> refreshSummary() async {
    const operation = _BillingOperation.refreshSummary;
    if (!_tryBeginBillingOperation(operation)) {
      return;
    }
    _loadingSummary = true;
    _error = null;
    _notifyListeners();

    try {
      final summary = await _repository.fetchBillingSummary();
      if (_disposed) {
        return;
      }
      _summary = summary;
      try {
        final products = await _storeBillingService.loadProducts(summary.plans);
        if (_disposed) {
          return;
        }
        _productsByPlanKey
          ..clear()
          ..addEntries(products.map((product) => MapEntry(
                product.planKey,
                product,
              )));
      } catch (_) {
        if (!_disposed) {
          _productsByPlanKey.clear();
        }
      }
    } catch (error) {
      if (!_disposed) {
        _error = _describeError(error);
      }
    } finally {
      _loadingSummary = false;
      _finishBillingOperation(operation);
      _notifyListeners();
    }
  }

  Future<bool> startCheckout({required String planKey}) async {
    const operation = _BillingOperation.checkout;
    if (!_tryBeginBillingOperation(operation)) {
      return false;
    }
    _creatingPayment = true;
    _error = null;
    _restoreOutcome = BillingRestoreOutcome.idle;
    _restoreWarnings = const <String>[];
    _restorePartialFailureCount = 0;
    _notifyListeners();

    try {
      final currentSummary =
          _summary ?? await _repository.fetchBillingSummary();
      if (_disposed) {
        return false;
      }
      final plan = currentSummary.plans.firstWhere(
        (item) => item.key == planKey,
        orElse: () => throw StateError('Billing plan was not found: $planKey'),
      );
      final result = await _storeBillingService.purchasePlan(plan);
      if (_disposed) {
        return false;
      }
      _summary = result.summary;
      _payment = BillingPayment(
        paymentId: result.transactionReference,
        status: 'paid',
        confirmationUrl: null,
        testMode: false,
        summary: result.summary,
        plan: plan,
      );
      return true;
    } catch (error) {
      if (_disposed) {
        return false;
      }
      _error = _describeError(error);
      return true;
    } finally {
      _creatingPayment = false;
      _finishBillingOperation(operation);
      _notifyListeners();
    }
  }

  Future<bool> restorePurchases() async {
    const operation = _BillingOperation.restore;
    if (!_tryBeginBillingOperation(operation)) {
      return false;
    }
    _loadingSummary = true;
    _error = null;
    _restoreOutcome = BillingRestoreOutcome.idle;
    _restoreWarnings = const <String>[];
    _restorePartialFailureCount = 0;
    _notifyListeners();

    try {
      final result = await _storeBillingService.restorePurchases();
      if (_disposed) {
        return false;
      }
      if (result == null) {
        _restoreOutcome = BillingRestoreOutcome.noPurchases;
      } else {
        _summary = result.summary;
        _restoreWarnings = List<String>.unmodifiable(result.warnings);
        _restorePartialFailureCount = result.partialFailureCount;
        _restoreOutcome =
            result.partialFailureCount > 0 || result.warnings.isNotEmpty
                ? BillingRestoreOutcome.partial
                : BillingRestoreOutcome.restored;
        _payment = BillingPayment(
          paymentId: result.transactionReference,
          status: 'paid',
          confirmationUrl: null,
          testMode: false,
          summary: result.summary,
        );
      }
      return true;
    } catch (error) {
      if (_disposed) {
        return false;
      }
      _error = _describeError(error);
      _restoreOutcome = BillingRestoreOutcome.failed;
      return true;
    } finally {
      _loadingSummary = false;
      _finishBillingOperation(operation);
      _notifyListeners();
    }
  }

  Future<bool> redeemPromoCode(String code) async {
    const operation = _BillingOperation.redeemPromo;
    if (!_tryBeginBillingOperation(operation)) {
      return false;
    }
    _error = null;
    _notifyListeners();

    try {
      final summary = await _repository.redeemPromoCode(code);
      if (_disposed) {
        return false;
      }
      _summary = summary;
      return true;
    } catch (error) {
      if (_disposed) {
        return false;
      }
      _error = _describeError(error);
      rethrow;
    } finally {
      _finishBillingOperation(operation);
      _notifyListeners();
    }
  }

  void clearPayment() {
    if (_disposed || _activeBillingOperation != null) {
      return;
    }
    _payment = null;
    _notifyListeners();
  }

  @override
  void dispose() {
    if (_disposed) {
      return;
    }
    _disposed = true;
    unawaited(_storeBillingService.dispose());
    super.dispose();
  }

  void _notifyListeners() {
    if (!_disposed) {
      notifyListeners();
    }
  }

  bool _tryBeginBillingOperation(_BillingOperation operation) {
    if (_disposed || _activeBillingOperation != null) {
      return false;
    }
    _activeBillingOperation = operation;
    return true;
  }

  void _finishBillingOperation(_BillingOperation operation) {
    if (_activeBillingOperation == operation) {
      _activeBillingOperation = null;
    }
  }

  String _describeError(Object error) {
    if (error is AppSlidesApiException) {
      return error.message;
    }
    return error.toString();
  }
}
