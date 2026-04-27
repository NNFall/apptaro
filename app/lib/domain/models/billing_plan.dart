class BillingPlan {
  const BillingPlan({
    required this.key,
    required this.title,
    required this.priceRub,
    required this.limit,
    required this.days,
    required this.recurring,
  });

  final String key;
  final String title;
  final int priceRub;
  final int limit;
  final int days;
  final bool recurring;

  factory BillingPlan.fromJson(Map<String, dynamic> json) {
    return BillingPlan(
      key: json['key'] as String,
      title: json['title'] as String,
      priceRub: json['price_rub'] as int,
      limit: json['limit'] as int,
      days: json['days'] as int,
      recurring: json['recurring'] as bool,
    );
  }
}
