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
    if (_summary != null || _loadingSummary) {
      return;
    }
    await _storeBillingService.initialize();
    await refreshSummary();
  }

  Future<void> refreshSummary() async {
    _loadingSummary = true;
    _error = null;
    _notifyListeners();

    try {
      final summary = await _repository.fetchBillingSummary();
      _summary = summary;
      try {
        final products = await _storeBillingService.loadProducts(summary.plans);
        _productsByPlanKey
          ..clear()
          ..addEntries(products.map((product) => MapEntry(
                product.planKey,
                product,
              )));
      } catch (_) {
        _productsByPlanKey.clear();
      }
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _loadingSummary = false;
      _notifyListeners();
    }
  }

  Future<void> startCheckout({required String planKey}) async {
    _creatingPayment = true;
    _error = null;
    _restoreOutcome = BillingRestoreOutcome.idle;
    _restoreWarnings = const <String>[];
    _restorePartialFailureCount = 0;
    _notifyListeners();

    try {
      final currentSummary =
          _summary ?? await _repository.fetchBillingSummary();
      final plan = currentSummary.plans.firstWhere(
        (item) => item.key == planKey,
        orElse: () => throw StateError('Billing plan was not found: $planKey'),
      );
      final result = await _storeBillingService.purchasePlan(plan);
      _summary = result.summary;
      _payment = BillingPayment(
        paymentId: result.transactionReference,
        status: 'paid',
        confirmationUrl: null,
        testMode: false,
        summary: result.summary,
        plan: plan,
      );
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _creatingPayment = false;
      _notifyListeners();
    }
  }

  Future<void> restorePurchases() async {
    _loadingSummary = true;
    _error = null;
    _payment = null;
    _restoreOutcome = BillingRestoreOutcome.idle;
    _restoreWarnings = const <String>[];
    _restorePartialFailureCount = 0;
    _notifyListeners();

    try {
      final result = await _storeBillingService.restorePurchases();
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
    } catch (error) {
      _error = _describeError(error);
      _restoreOutcome = BillingRestoreOutcome.failed;
    } finally {
      _loadingSummary = false;
      _notifyListeners();
    }
  }

  Future<void> redeemPromoCode(String code) async {
    _error = null;
    _notifyListeners();

    try {
      _summary = await _repository.redeemPromoCode(code);
    } catch (error) {
      _error = _describeError(error);
      rethrow;
    } finally {
      _notifyListeners();
    }
  }

  void clearPayment() {
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

  String _describeError(Object error) {
    if (error is AppSlidesApiException) {
      return error.message;
    }
    return error.toString();
  }
}
