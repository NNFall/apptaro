import 'package:apptaro/features/billing/apple_paywall_copy.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ApplePaywallCopy', () {
    test('uses the StoreKit localized price with interval and readings', () {
      expect(
        ApplePaywallCopy.planLine(
          isRussian: false,
          planKey: 'week',
          recurring: true,
          localizedPrice: r'$4.99',
          includedReadings: 15,
        ),
        r'$4.99 / week - 15 readings',
      );
      expect(
        ApplePaywallCopy.planLine(
          isRussian: true,
          planKey: 'month',
          recurring: true,
          localizedPrice: '499,00 ₽',
          includedReadings: 60,
        ),
        '499,00 ₽ / месяц - 60 раскладов',
      );
    });

    test('separates auto-renew disclosure from purchase legal links', () {
      final disclosure = ApplePaywallCopy.subscriptionDisclosure(
        isRussian: false,
      );
      final links = ApplePaywallCopy.purchaseLegalLinks(
        isRussian: false,
        privacyPolicyUrl: 'https://example.test/privacy',
      );

      expect(disclosure, contains('automatically renews'));
      expect(disclosure, contains('cancel'));
      expect(disclosure, isNot(contains('Privacy Policy')));
      expect(links, contains('[Privacy Policy](https://example.test/privacy)'));
      expect(
        links,
        contains(
          '[Terms of Use](https://www.apple.com/legal/internet-services/itunes/dev/stdeula/)',
        ),
      );
      expect(links, isNot(contains('automatically renews')));
    });

    test('distinguishes subscription and one-time pack choices', () {
      expect(
        ApplePaywallCopy.paywallTitle(
          isRussian: false,
          offersSubscriptions: true,
          offersReadingPacks: true,
        ),
        contains('subscription or reading pack'),
      );
      expect(
        ApplePaywallCopy.planButtonLabel(
          isRussian: false,
          recurring: true,
          planLine: r'$4.99 / week - 15 readings',
        ),
        contains('Subscribe'),
      );
      final packLine = ApplePaywallCopy.planLine(
        isRussian: false,
        planKey: 'one10',
        recurring: false,
        localizedPrice: r'$8.99',
        includedReadings: 10,
      );
      expect(packLine, contains('one-time reading pack'));
      expect(
        ApplePaywallCopy.planButtonLabel(
          isRussian: false,
          recurring: false,
          planLine: packLine,
        ),
        contains('Buy reading pack'),
      );
    });

    test('one-time pack success and balance never claim a subscription', () {
      final success = ApplePaywallCopy.purchaseSuccess(
        isRussian: false,
        recurring: false,
        planLine: r'$8.99 - 10 readings (one-time reading pack)',
        remainingReadings: 10,
        validUntil: '9999-12-31',
        subscriptionDisclosure: 'automatically renews',
      );
      final balance = ApplePaywallCopy.activeBalance(
        isRussian: false,
        recurring: false,
        autoRenew: false,
        planLine: r'$8.99 - 10 readings (one-time reading pack)',
        remainingReadings: 7,
        validUntil: '9999-12-31',
        subscriptionDisclosure: 'automatically renews',
      );

      expect(success, contains('Reading pack added'));
      expect(success, contains('Latest reading pack'));
      expect(success, contains('Total readings available'));
      expect(balance, contains('Reading credits available'));
      expect(balance, contains('Latest reading pack'));
      expect(balance, contains('Total readings available'));
      for (final copy in <String>[success, balance]) {
        expect(copy.toLowerCase(), isNot(contains('subscription')));
        expect(copy.toLowerCase(), isNot(contains('valid until')));
        expect(copy, isNot(contains('9999-12-31')));
        expect(copy.toLowerCase(), isNot(contains('automatically renews')));
      }
    });

    test('Russian one-time pack copy is clear and has no subscription terms',
        () {
      final success = ApplePaywallCopy.purchaseSuccess(
        isRussian: true,
        recurring: false,
        planLine: '899 ₽ — 10 раскладов, разовая покупка',
        remainingReadings: 10,
        validUntil: '9999-12-31',
        subscriptionDisclosure: 'Подписка продлевается автоматически',
      );

      expect(success, contains('Пакет раскладов добавлен'));
      expect(success, contains('Последний пакет раскладов'));
      expect(success, contains('Всего доступно раскладов'));
      expect(success.toLowerCase(), isNot(contains('подпис')));
      expect(success, isNot(contains('9999-12-31')));
      expect(success, isNot(contains('Действует до')));
    });

    test('subscription success and balance keep expiry and renewal copy', () {
      const disclosure =
          'The subscription automatically renews unless canceled.';
      final success = ApplePaywallCopy.purchaseSuccess(
        isRussian: false,
        recurring: true,
        planLine: r'$4.99 / week - 15 readings',
        remainingReadings: 15,
        validUntil: '2026-07-25',
        subscriptionDisclosure: disclosure,
      );
      final balance = ApplePaywallCopy.activeBalance(
        isRussian: false,
        recurring: true,
        autoRenew: true,
        planLine: r'$4.99 / week - 15 readings',
        remainingReadings: 8,
        validUntil: '2026-07-25',
        subscriptionDisclosure: disclosure,
      );

      for (final copy in <String>[success, balance]) {
        expect(copy, contains('Subscription'));
        expect(copy, contains(r'$4.99 / week - 15 readings'));
        expect(copy, contains('Total readings available'));
        expect(copy, contains('Subscription access until'));
        expect(copy, contains('automatically renews'));
      }
    });

    test('non-renewing active subscription is canceled but valid until expiry',
        () {
      final copy = ApplePaywallCopy.activeBalance(
        isRussian: false,
        recurring: true,
        autoRenew: false,
        planLine: r'$4.99 / week - 15 readings',
        remainingReadings: 21,
        validUntil: '2026-07-25',
        subscriptionDisclosure: 'automatically renews',
      );

      expect(copy, contains('Subscription status'));
      expect(copy, contains('Canceled'));
      expect(copy, contains('available until expiry'));
      expect(copy, contains(r'$4.99 / week - 15 readings'));
      expect(copy, contains('Total readings available'));
      expect(copy, contains('21'));
      expect(copy, contains('Subscription access until'));
      expect(copy, contains('2026-07-25'));
      expect(copy.toLowerCase(), isNot(contains('automatically renews')));
    });

    test('canceled subscription keeps plan readings and expiry without renewal',
        () {
      final copy = ApplePaywallCopy.canceledSubscriptionBalance(
        isRussian: false,
        planLine: r'$4.99 / week - 15 readings',
        remainingReadings: 6,
        validUntil: '2026-07-25',
      );
      final russianCopy = ApplePaywallCopy.canceledSubscriptionBalance(
        isRussian: true,
        planLine: '499 ₽ / неделю - 15 раскладов',
        remainingReadings: 6,
        validUntil: '2026-07-25',
      );

      expect(copy, contains('Subscription canceled'));
      expect(copy, contains(r'$4.99 / week - 15 readings'));
      expect(copy, contains('Total readings available'));
      expect(copy, contains('Subscription access until'));
      expect(copy, contains('2026-07-25'));
      expect(copy, isNot(contains('Readings are available until')));
      expect(copy.toLowerCase(), isNot(contains('automatically renews')));
      expect(russianCopy, contains('Подписка отключена'));
      expect(russianCopy, contains('499 ₽ / неделю - 15 раскладов'));
      expect(russianCopy, contains('Всего доступно раскладов'));
      expect(russianCopy, contains('Доступ по подписке до'));
      expect(russianCopy, contains('2026-07-25'));
      expect(russianCopy.toLowerCase(), isNot(contains('продлевается')));
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
