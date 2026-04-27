import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../data/api/appslides_api_client.dart';
import '../../data/repositories/appslides_repository.dart';
import '../../domain/models/billing_payment.dart';
import '../../domain/models/billing_summary.dart';

class BillingController extends ChangeNotifier {
  BillingController({
    required AppSlidesRepository repository,
  }) : _repository = repository;

  final AppSlidesRepository _repository;

  BillingSummary? _summary;
  BillingPayment? _payment;
  bool _loadingSummary = false;
  bool _creatingPayment = false;
  bool _canceling = false;
  String? _error;
  Timer? _pollTimer;

  BillingSummary? get summary => _summary;
  BillingPayment? get payment => _payment;
  bool get loadingSummary => _loadingSummary;
  bool get creatingPayment => _creatingPayment;
  bool get canceling => _canceling;
  String? get error => _error;

  Future<void> initialize() async {
    if (_summary != null || _loadingSummary) {
      return;
    }
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

  Future<void> startCheckout({
    required String planKey,
    bool renew = false,
  }) async {
    _creatingPayment = true;
    _error = null;
    notifyListeners();

    try {
      final payment = await _repository.createBillingPayment(
        planKey: planKey,
        renew: renew,
      );
      _payment = payment;
      _summary = payment.summary;
      if (!payment.isFinished) {
        _startPolling(payment.paymentId);
      }
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _creatingPayment = false;
      notifyListeners();
    }
  }

  Future<void> pollPayment(String paymentId) async {
    try {
      final payment = await _repository.getBillingPayment(paymentId);
      _payment = payment;
      _summary = payment.summary;
      if (payment.isFinished) {
        _pollTimer?.cancel();
      }
      notifyListeners();
    } catch (error) {
      _error = _describeError(error);
      _pollTimer?.cancel();
      notifyListeners();
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

  void clearPayment() {
    _pollTimer?.cancel();
    _payment = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  void _startPolling(String paymentId) {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 4), (_) async {
      await pollPayment(paymentId);
    });
    unawaited(pollPayment(paymentId));
  }

  String _describeError(Object error) {
    if (error is AppSlidesApiException) {
      return error.message;
    }
    return error.toString();
  }
}
