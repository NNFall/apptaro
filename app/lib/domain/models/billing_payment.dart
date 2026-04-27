import 'billing_plan.dart';
import 'billing_summary.dart';

class BillingPayment {
  const BillingPayment({
    required this.paymentId,
    required this.status,
    required this.confirmationUrl,
    required this.testMode,
    required this.summary,
    this.plan,
  });

  final String paymentId;
  final String status;
  final String? confirmationUrl;
  final bool testMode;
  final BillingSummary summary;
  final BillingPlan? plan;

  bool get isFinished => status == 'paid' || status == 'canceled' || status == 'failed';
  bool get isSuccessful => status == 'paid';

  factory BillingPayment.fromJson(
    Map<String, dynamic> json, {
    BillingPlan? plan,
  }) {
    return BillingPayment(
      paymentId: json['payment_id'] as String,
      status: json['status'] as String,
      confirmationUrl: json['confirmation_url'] as String?,
      testMode: json['test_mode'] as bool? ?? false,
      summary: BillingSummary.fromJson(
        (json['summary'] as Map).cast<String, dynamic>(),
      ),
      plan: plan,
    );
  }
}
