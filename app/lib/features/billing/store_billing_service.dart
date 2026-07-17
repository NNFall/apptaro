import '../../domain/models/billing_plan.dart';
import '../../domain/models/billing_summary.dart';

class StoreBillingResult {
  const StoreBillingResult({
    required this.summary,
    required this.transactionReference,
    this.warnings = const <String>[],
    this.partialFailureCount = 0,
  });

  final BillingSummary summary;
  final String transactionReference;
  final List<String> warnings;
  final int partialFailureCount;
}

abstract interface class StoreBillingService {
  Future<void> initialize();

  Future<StoreBillingResult> purchasePlan(BillingPlan plan);

  Future<StoreBillingResult?> restorePurchases();

  Future<void> dispose();
}
