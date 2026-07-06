import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../data/api/appslides_api_client.dart';
import '../../data/repositories/appslides_repository.dart';
import '../../domain/models/billing_payment.dart';
import '../../domain/models/billing_summary.dart';
import 'google_play_billing_service.dart';

class BillingController extends ChangeNotifier {
  BillingController({
    required AppSlidesRepository repository,
    GooglePlayBillingService? googlePlayBillingService,
  })  : _repository = repository,
        _googlePlayBillingService = googlePlayBillingService ??
            GooglePlayBillingService(repository: repository);

  final AppSlidesRepository _repository;
  final GooglePlayBillingService _googlePlayBillingService;

  BillingSummary? _summary;
  BillingPayment? _payment;
  bool _loadingSummary = false;
  bool _creatingPayment = false;
  bool _canceling = false;
  String? _error;
  bool _pollingInFlight = false;
  bool _paymentPollingTimedOut = false;

  BillingSummary? get summary => _summary;
  BillingPayment? get payment => _payment;
  bool get loadingSummary => _loadingSummary;
  bool get creatingPayment => _creatingPayment;
  bool get canceling => _canceling;
  String? get error => _error;
  bool get paymentPollingTimedOut => _paymentPollingTimedOut;

  Future<void> initialize() async {
    if (_summary != null || _loadingSummary) {
      return;
    }
    await _googlePlayBillingService.initialize();
    await refreshSummary();
    unawaited(restoreGooglePlayPurchases(silent: true));
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

  Future<void> startCheckout({
    required String planKey,
    bool renew = false,
  }) async {
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
      final summary = await _googlePlayBillingService.purchasePlan(plan);
      _summary = summary;
      _payment = BillingPayment(
        paymentId:
            'google_play:${GooglePlayBillingService.productIdForPlan(plan)}',
        status: 'paid',
        confirmationUrl: null,
        testMode: false,
        summary: summary,
        plan: plan,
      );
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _creatingPayment = false;
      notifyListeners();
    }
  }

  Future<void> pollPayment(String paymentId) async {
    if (_pollingInFlight) {
      return;
    }

    _pollingInFlight = true;
    try {
      final payment = await _repository.getBillingPayment(paymentId);
      _payment = payment;
      _summary = payment.summary;
      if (payment.isFinished) {
        _paymentPollingTimedOut = false;
      }
      notifyListeners();
    } catch (error) {
      _error = _describeError(error);
      notifyListeners();
    } finally {
      _pollingInFlight = false;
    }
  }

  Future<void> cancelSubscription() async {
    _canceling = true;
    _error = null;
    notifyListeners();

    try {
      _summary = await _repository.cancelBillingSubscription();
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _canceling = false;
      notifyListeners();
    }
  }

  Future<void> restoreGooglePlayPurchases({bool silent = false}) async {
    if (!silent) {
      _loadingSummary = true;
      _error = null;
      notifyListeners();
    }

    try {
      final restoredSummary =
          await _googlePlayBillingService.restorePurchases();
      if (restoredSummary != null) {
        _summary = restoredSummary;
        _payment = BillingPayment(
          paymentId: 'google_play:restore',
          status: 'paid',
          confirmationUrl: null,
          testMode: false,
          summary: restoredSummary,
        );
      }
    } catch (error) {
      if (!silent) {
        _error = _describeError(error);
      }
    } finally {
      if (!silent) {
        _loadingSummary = false;
        notifyListeners();
      } else if (_payment != null) {
        notifyListeners();
      }
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
    _resetPollingState();
    _payment = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _resetPollingState();
    unawaited(_googlePlayBillingService.dispose());
    super.dispose();
  }

  void _resetPollingState() {
    _pollingInFlight = false;
    _paymentPollingTimedOut = false;
  }

  String _describeError(Object error) {
    if (error is AppSlidesApiException) {
      return error.message;
    }
    return error.toString();
  }
}
