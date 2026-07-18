import 'package:apptaro/core/policies/billing_platform_policy.dart';
import 'package:apptaro/domain/models/billing_plan.dart';
import 'package:apptaro/features/billing/billing_chat_presentation.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const iosPolicy = BillingPlatformPolicy(
    isWeb: false,
    targetPlatform: TargetPlatform.iOS,
  );
  const androidPolicy = BillingPlatformPolicy(
    isWeb: false,
    targetPlatform: TargetPlatform.android,
  );

  test('native iOS presentation provides Restore and Apple legal content', () {
    final presentation = BillingChatPresentation.forPlatform(
      platformPolicy: iosPolicy,
      isRussian: false,
      applePrivacyPolicyUrl: 'https://example.test/privacy',
    );

    expect(
      presentation.actions,
      contains(BillingChatAction.restorePurchases),
    );
    expect(presentation.showsRestorePurchases, isTrue);
    expect(
      presentation.applePrivacyPolicy?.toString(),
      'https://example.test/privacy',
    );
    expect(
      presentation.legalDisclosure,
      contains('[Privacy Policy](https://example.test/privacy)'),
    );
    expect(
      presentation.legalDisclosure,
      contains(
        '[Terms of Use](https://www.apple.com/legal/internet-services/itunes/dev/stdeula/)',
      ),
    );
  });

  test('Android presentation has no Apple Restore action or legal content', () {
    final presentation = BillingChatPresentation.forPlatform(
      platformPolicy: androidPolicy,
      isRussian: false,
      applePrivacyPolicyUrl: 'https://example.test/privacy',
    );

    expect(presentation.actions, isEmpty);
    expect(presentation.showsRestorePurchases, isFalse);
    expect(presentation.applePrivacyPolicy, isNull);
    expect(presentation.legalDisclosure, isNull);
  });

  test('paywall keeps subscriptions and consumable reading packs visible', () {
    const plans = <BillingPlan>[
      BillingPlan(
        key: 'week',
        title: 'Weekly',
        priceRub: 0,
        limit: 15,
        days: 7,
        recurring: true,
        googleProductId: 'weekly_readings',
      ),
      BillingPlan(
        key: 'one10',
        title: '10 readings',
        priceRub: 0,
        limit: 10,
        days: 0,
        recurring: false,
        googleProductId: 'one10_readings',
      ),
    ];

    expect(
      BillingChatPresentation.visiblePlans(plans).map((plan) => plan.key),
      <String>['week', 'one10'],
    );
  });
}
