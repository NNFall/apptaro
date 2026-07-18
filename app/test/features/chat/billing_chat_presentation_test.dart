import 'package:apptaro/core/policies/billing_platform_policy.dart';
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
}
