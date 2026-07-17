import '../../domain/models/billing_plan.dart';
import '../../domain/models/billing_summary.dart';

class StoreBillingResult {
  const StoreBillingResult({
    required this.summary,
    required this.transactionReference,
  });

  final BillingSummary summary;
  final String transactionReference;
}

abstract interface class StoreBillingService {
  Future<void> initialize();

  Future<StoreBillingResult> purchasePlan(BillingPlan plan);

  Future<StoreBillingResult?> restorePurchases();

  Future<void> dispose();
}
