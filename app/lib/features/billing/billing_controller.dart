import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../data/api/appslides_api_client.dart';
import '../../data/repositories/appslides_repository.dart';
import '../../domain/models/billing_payment.dart';
import '../../domain/models/billing_summary.dart';
import 'google_play_billing_service.dart';
import 'store_billing_service.dart';

class BillingController extends ChangeNotifier {
  BillingController({
    required AppSlidesRepository repository,
    StoreBillingService? storeBillingService,
  })  : _repository = repository,
        _storeBillingService = storeBillingService ??
            GooglePlayBillingService(repository: repository);

  final AppSlidesRepository _repository;
  final StoreBillingService _storeBillingService;

  BillingSummary? _summary;
  BillingPayment? _payment;
  bool _loadingSummary = false;
  bool _creatingPayment = false;
  String? _error;

  BillingSummary? get summary => _summary;
  BillingPayment? get payment => _payment;
  bool get loadingSummary => _loadingSummary;
  bool get creatingPayment => _creatingPayment;
  String? get error => _error;

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
    notifyListeners();

    try {
      _summary = await _repository.fetchBillingSummary();
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _loadingSummary = false;
      notifyListeners();
    }
  }

  Future<void> startCheckout({required String planKey}) async {
    _creatingPayment = true;
    _error = null;
    notifyListeners();

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
        paymentId: result.paymentId,
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
      notifyListeners();
    }
  }

  Future<void> restorePurchases() async {
    _loadingSummary = true;
    _error = null;
    notifyListeners();

    try {
      final result = await _storeBillingService.restorePurchases();
      if (result != null) {
        _summary = result.summary;
        _payment = BillingPayment(
          paymentId: result.paymentId,
          status: 'paid',
          confirmationUrl: null,
          testMode: false,
          summary: result.summary,
        );
      }
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _loadingSummary = false;
      notifyListeners();
    }
  }

  Future<void> redeemPromoCode(String code) async {
    _error = null;
    notifyListeners();

    try {
      _summary = await _repository.redeemPromoCode(code);
    } catch (error) {
      _error = _describeError(error);
      rethrow;
    } finally {
      notifyListeners();
    }
  }

  void clearPayment() {
    _payment = null;
    notifyListeners();
  }

  @override
  void dispose() {
    unawaited(_storeBillingService.dispose());
    super.dispose();
  }

  String _describeError(Object error) {
    if (error is AppSlidesApiException) {
      return error.message;
    }
    return error.toString();
  }
}
