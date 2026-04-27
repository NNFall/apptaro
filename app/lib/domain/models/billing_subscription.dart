class BillingSubscription {
  const BillingSubscription({
    required this.planKey,
    required this.status,
    required this.remaining,
    required this.startsAt,
    required this.endsAt,
    required this.autoRenew,
    required this.provider,
  });

  final String planKey;
  final String status;
  final int remaining;
  final String startsAt;
  final String endsAt;
  final bool autoRenew;
  final String provider;

  bool get isActive => status == 'active';
  bool get isCanceled => status == 'canceled';

  factory BillingSubscription.fromJson(Map<String, dynamic> json) {
    return BillingSubscription(
      planKey: json['plan_key'] as String,
      status: json['status'] as String,
      remaining: json['remaining'] as int,
      startsAt: json['starts_at'] as String,
      endsAt: json['ends_at'] as String,
      autoRenew: json['auto_renew'] as bool,
      provider: json['provider'] as String,
    );
  }
}
