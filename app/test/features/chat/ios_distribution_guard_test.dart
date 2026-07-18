import 'package:apptaro/core/policies/billing_platform_policy.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('BillingPlatformPolicy', () {
    const ios = BillingPlatformPolicy(
      isWeb: false,
      targetPlatform: TargetPlatform.iOS,
    );
    const android = BillingPlatformPolicy(
      isWeb: false,
      targetPlatform: TargetPlatform.android,
    );

    test('exposes Apple legal links and restore visibility only on iOS', () {
      final links = ios.appleLegalLinks('https://example.test/privacy');

      expect(ios.isNativeIos, isTrue);
      expect(ios.restorePurchasesVisible, isTrue);
      expect(ios.promoSupported, isFalse);
      expect(links?.privacyPolicy.toString(), 'https://example.test/privacy');
      expect(
        links?.termsOfUse.toString(),
        'https://www.apple.com/legal/internet-services/itunes/dev/stdeula/',
      );
      expect(android.restorePurchasesVisible, isFalse);
      expect(android.promoSupported, isTrue);
      expect(android.appleLegalLinks('https://example.test/privacy'), isNull);
    });

    test('does not invoke promo redemption on native iOS', () async {
      var redeemCalls = 0;

      final outcome = await ios.executePromoCommand(
        code: 'SAVE20',
        redeem: (_) async => redeemCalls += 1,
      );

      expect(outcome, PromoCommandOutcome.unsupported);
      expect(redeemCalls, 0);
    });

    test('keeps Android promo redemption behavior', () async {
      var redeemedCode = '';

      final outcome = await android.executePromoCommand(
        code: 'SAVE20',
        redeem: (code) async => redeemedCode = code,
      );

      expect(outcome, PromoCommandOutcome.redeemed);
      expect(redeemedCode, 'SAVE20');
    });

    test('rejects legacy iOS paywall actions but accepts versioned actions',
        () {
      expect(
        ios.allowsPersistedAction(
          actionKey: 'start_billing_payment',
          payload: const <String, dynamic>{'plan_key': 'week'},
        ),
        isFalse,
      );
      final payload = ios.decorateBillingActionPayload(
        const <String, dynamic>{'plan_key': 'week'},
      );
      expect(
        ios.allowsPersistedAction(
          actionKey: 'start_billing_payment',
          payload: payload,
        ),
        isTrue,
      );
      expect(
        ios.allowsPersistedAction(
          actionKey: 'restore_purchases',
          payload: const <String, dynamic>{},
        ),
        isTrue,
      );
      expect(
        android.allowsPersistedAction(
          actionKey: 'start_billing_payment',
          payload: const <String, dynamic>{'plan_key': 'week'},
        ),
        isTrue,
      );
    });
  });
}
