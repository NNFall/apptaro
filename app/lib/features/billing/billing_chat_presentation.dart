import 'package:flutter/foundation.dart';

import '../../core/policies/billing_platform_policy.dart';
import '../../domain/models/billing_payment.dart';
import '../../domain/models/billing_plan.dart';
import '../../domain/models/billing_subscription.dart';
import 'apple_paywall_copy.dart';

enum BillingChatAction { restorePurchases }

@immutable
class BillingPaymentSuccessDetails {
  const BillingPaymentSuccessDetails({
    required this.plan,
    required this.remainingReadings,
    required this.validUntil,
  });

  final BillingPlan plan;
  final int remainingReadings;
  final String? validUntil;
}

@immutable
class BillingChatPresentation {
  const BillingChatPresentation._({
    required this.actions,
    required this.applePrivacyPolicy,
    required this.appleSubscriptionDisclosure,
    required this.applePurchaseLegalCopy,
  });

  factory BillingChatPresentation.forPlatform({
    required BillingPlatformPolicy platformPolicy,
    required bool isRussian,
    required String applePrivacyPolicyUrl,
  }) {
    if (!platformPolicy.isNativeIos) {
      return const BillingChatPresentation._(
        actions: <BillingChatAction>{},
        applePrivacyPolicy: null,
        appleSubscriptionDisclosure: null,
        applePurchaseLegalCopy: null,
      );
    }

    const actions = <BillingChatAction>{BillingChatAction.restorePurchases};
    try {
      final links = platformPolicy.appleLegalLinks(applePrivacyPolicyUrl)!;
      return BillingChatPresentation._(
        actions: actions,
        applePrivacyPolicy: links.privacyPolicy,
        appleSubscriptionDisclosure: ApplePaywallCopy.subscriptionDisclosure(
          isRussian: isRussian,
        ),
        applePurchaseLegalCopy: ApplePaywallCopy.purchaseLegalLinks(
          isRussian: isRussian,
          privacyPolicyUrl: links.privacyPolicy.toString(),
        ),
      );
    } on Object {
      return BillingChatPresentation._(
        actions: actions,
        applePrivacyPolicy: null,
        appleSubscriptionDisclosure: null,
        applePurchaseLegalCopy: ApplePaywallCopy.privacyUnavailable(
          isRussian: isRussian,
        ),
      );
    }
  }

  final Set<BillingChatAction> actions;
  final Uri? applePrivacyPolicy;
  final String? appleSubscriptionDisclosure;
  final String? applePurchaseLegalCopy;

  bool get showsRestorePurchases =>
      actions.contains(BillingChatAction.restorePurchases);

  String? applePaymentSuccessText({
    required BillingPayment payment,
    required bool isRussian,
    required String Function(BillingPlan plan) planLineFor,
    required String Function(String value) formatDate,
  }) {
    final details = paymentSuccessDetails(payment);
    if (details == null) {
      return null;
    }
    final planLine = planLineFor(details.plan);
    final text = details.plan.recurring && details.validUntil == null
        ? ApplePaywallCopy.subscriptionStatusUpdating(
            isRussian: isRussian,
            planLine: planLine,
            remainingReadings: details.remainingReadings,
          )
        : ApplePaywallCopy.purchaseSuccess(
            isRussian: isRussian,
            recurring: details.plan.recurring,
            planLine: planLine,
            remainingReadings: details.remainingReadings,
            validUntil: details.validUntil == null
                ? ''
                : formatDate(details.validUntil!),
            subscriptionDisclosure: appleSubscriptionDisclosure ?? '',
          );
    return withApplePurchaseLegalCopy(text);
  }

  String withApplePurchaseLegalCopy(String text) {
    final legalCopy = applePurchaseLegalCopy;
    if (legalCopy == null || legalCopy.isEmpty) {
      return text;
    }
    return '$text\n\n$legalCopy';
  }

  static List<BillingPlan> visiblePlans(Iterable<BillingPlan> plans) {
    return List<BillingPlan>.unmodifiable(plans);
  }

  static bool showsPlanOptionsOnBalance({
    required BillingPlatformPolicy platformPolicy,
    required bool hasActiveEntitlement,
  }) {
    return platformPolicy.isNativeIos || !hasActiveEntitlement;
  }

  static List<BillingPlan> subscriptionPlans(Iterable<BillingPlan> plans) {
    return List<BillingPlan>.unmodifiable(
      plans.where((plan) => plan.recurring),
    );
  }

  static List<BillingPlan> readingPackPlans(Iterable<BillingPlan> plans) {
    return List<BillingPlan>.unmodifiable(
      plans.where((plan) => !plan.recurring),
    );
  }

  static bool isOneTimeEntitlement({
    required Iterable<BillingPlan> plans,
    required String planKey,
  }) {
    for (final plan in plans) {
      if (plan.key == planKey) {
        return !plan.recurring;
      }
    }
    return planKey == 'one10' || planKey == 'one40';
  }

  static BillingPaymentSuccessDetails? paymentSuccessDetails(
    BillingPayment payment,
  ) {
    final plan = payment.plan;
    if (plan == null) {
      return null;
    }

    String? validUntil;
    if (plan.recurring) {
      final entitlements = <BillingSubscription?>[
        payment.summary.activeSubscription,
        payment.summary.latestValidSubscription,
      ];
      for (final entitlement in entitlements) {
        if (entitlement != null && entitlement.planKey == plan.key) {
          validUntil = entitlement.endsAt;
          break;
        }
      }
    }

    return BillingPaymentSuccessDetails(
      plan: plan,
      remainingReadings: payment.summary.remainingGenerations,
      validUntil: validUntil,
    );
  }
}
