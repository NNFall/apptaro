import 'package:flutter/foundation.dart';

import '../../core/policies/billing_platform_policy.dart';
import 'apple_paywall_copy.dart';

enum BillingChatAction { restorePurchases }

@immutable
class BillingChatPresentation {
  const BillingChatPresentation._({
    required this.actions,
    required this.applePrivacyPolicy,
    required this.legalDisclosure,
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
        legalDisclosure: null,
      );
    }

    const actions = <BillingChatAction>{BillingChatAction.restorePurchases};
    try {
      final links = platformPolicy.appleLegalLinks(applePrivacyPolicyUrl)!;
      return BillingChatPresentation._(
        actions: actions,
        applePrivacyPolicy: links.privacyPolicy,
        legalDisclosure: ApplePaywallCopy.subscriptionDisclosure(
          isRussian: isRussian,
          privacyPolicyUrl: links.privacyPolicy.toString(),
        ),
      );
    } on Object {
      return BillingChatPresentation._(
        actions: actions,
        applePrivacyPolicy: null,
        legalDisclosure: ApplePaywallCopy.privacyUnavailable(
          isRussian: isRussian,
        ),
      );
    }
  }

  final Set<BillingChatAction> actions;
  final Uri? applePrivacyPolicy;
  final String? legalDisclosure;

  bool get showsRestorePurchases =>
      actions.contains(BillingChatAction.restorePurchases);
}
