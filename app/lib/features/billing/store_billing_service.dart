import '../../domain/models/billing_plan.dart';
import '../../domain/models/billing_summary.dart';

class StoreBillingProduct {
  const StoreBillingProduct({
    required this.planKey,
    required this.productId,
    required this.localizedPrice,
  });

  final String planKey;
  final String productId;
  final String localizedPrice;

  @override
  bool operator ==(Object other) {
    return other is StoreBillingProduct &&
        other.planKey == planKey &&
        other.productId == productId &&
        other.localizedPrice == localizedPrice;
  }

  @override
  int get hashCode => Object.hash(planKey, productId, localizedPrice);
}

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

  Future<List<StoreBillingProduct>> loadProducts(List<BillingPlan> plans);

  Future<StoreBillingResult> purchasePlan(BillingPlan plan);

  Future<StoreBillingResult?> restorePurchases();

  Future<void> dispose();
}
