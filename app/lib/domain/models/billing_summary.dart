import 'billing_plan.dart';
import 'billing_subscription.dart';

class BillingSummary {
  const BillingSummary({
    required this.clientId,
    required this.supportUsername,
    required this.supportMaxUrl,
    required this.offerUrl,
    required this.testMode,
    required this.plans,
    required this.activeSubscription,
    required this.latestValidSubscription,
  });

  final String clientId;
  final String supportUsername;
  final String supportMaxUrl;
  final String offerUrl;
  final bool testMode;
  final List<BillingPlan> plans;
  final BillingSubscription? activeSubscription;
  final BillingSubscription? latestValidSubscription;

  BillingSubscription? get effectiveSubscription =>
      activeSubscription ?? latestValidSubscription;

  int get remainingGenerations => effectiveSubscription?.remaining ?? 0;

  factory BillingSummary.fromJson(Map<String, dynamic> json) {
    final rawPlans = json['plans'] as List<dynamic>? ?? const <dynamic>[];
    final rawActive = json['active_subscription'];
    final rawLatest = json['latest_valid_subscription'];

    return BillingSummary(
      clientId: json['client_id'] as String,
      supportUsername: json['support_username'] as String,
      supportMaxUrl: json['support_max_url'] as String? ?? '',
      offerUrl: json['offer_url'] as String,
      testMode: json['test_mode'] as bool? ?? false,
      plans: rawPlans
          .whereType<Map>()
          .map((item) => BillingPlan.fromJson(item.cast<String, dynamic>()))
          .toList(),
      activeSubscription: rawActive is Map<String, dynamic>
          ? BillingSubscription.fromJson(rawActive)
          : rawActive is Map
              ? BillingSubscription.fromJson(rawActive.cast<String, dynamic>())
              : null,
      latestValidSubscription: rawLatest is Map<String, dynamic>
          ? BillingSubscription.fromJson(rawLatest)
          : rawLatest is Map
              ? BillingSubscription.fromJson(rawLatest.cast<String, dynamic>())
              : null,
    );
  }
}
