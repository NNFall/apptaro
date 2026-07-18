import 'package:apptaro/features/billing/apple_paywall_copy.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ApplePaywallCopy', () {
    test('uses the StoreKit localized price with interval and readings', () {
      expect(
        ApplePaywallCopy.planLine(
          isRussian: false,
          planKey: 'week',
          localizedPrice: r'$4.99',
          includedReadings: 15,
        ),
        r'$4.99 / week - 15 readings',
      );
      expect(
        ApplePaywallCopy.planLine(
          isRussian: true,
          planKey: 'month',
          localizedPrice: '499,00 ₽',
          includedReadings: 60,
        ),
        '499,00 ₽ / месяц - 60 раскладов',
      );
    });

    test('includes auto-renew, cancellation, privacy, and terms before buy',
        () {
      final copy = ApplePaywallCopy.subscriptionDisclosure(
        isRussian: false,
        privacyPolicyUrl: 'https://example.test/privacy',
      );

      expect(copy, contains('automatically renews'));
      expect(copy, contains('cancel'));
      expect(copy, contains('[Privacy Policy](https://example.test/privacy)'));
      expect(
        copy,
        contains(
          '[Terms of Use](https://www.apple.com/legal/internet-services/itunes/dev/stdeula/)',
        ),
      );
    });

    test('localizes checkout and all restore outcomes', () {
      expect(
        ApplePaywallCopy.checkoutProgress(isRussian: false),
        contains('App Store'),
      );
      expect(
        ApplePaywallCopy.restoreSuccess(isRussian: false),
        contains('restored'),
      );
      expect(
        ApplePaywallCopy.restoreNoPurchases(isRussian: true),
        contains('Покупки для восстановления не найдены'),
      );
      expect(
        ApplePaywallCopy.restorePartial(
          isRussian: false,
          failedCount: 2,
        ),
        contains('2 purchases could not be restored'),
      );
      expect(
        ApplePaywallCopy.restoreError(
          isRussian: true,
          error: 'StoreKit error',
        ),
        contains('StoreKit error'),
      );
    });
  });
}
