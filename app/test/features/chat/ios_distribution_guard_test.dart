import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  final source = File('lib/features/chat/chat_screen.dart').readAsStringSync();

  test('native iOS uses App Store checkout and blocks promo backend calls', () {
    expect(source, contains('bool get _isNativeIos'));
    expect(source, contains('Promo codes are not supported on iOS.'));
    expect(source, contains('if (_isNativeIos)'));
    expect(source, contains('ApplePaywallCopy.checkoutProgress'));

    final promoCase = source.indexOf("case '/promo':");
    final promoGuard = source.indexOf('if (_isNativeIos)', promoCase);
    final promoBackendCall = source.indexOf('await _redeemPromo', promoCase);
    expect(promoCase, greaterThanOrEqualTo(0));
    expect(promoGuard, inInclusiveRange(promoCase, promoBackendCall));

    final redeemMethod = source.indexOf('Future<void> _redeemPromo');
    final redeemGuard = source.indexOf('if (_isNativeIos)', redeemMethod);
    final billingController = source.indexOf(
      'final controller = _billingController',
      redeemMethod,
    );
    expect(redeemMethod, greaterThanOrEqualTo(0));
    expect(redeemGuard, inInclusiveRange(redeemMethod, billingController));
  });

  test('iOS paywall has legal and explicit restore actions', () {
    expect(source, contains('ApplePaywallCopy.subscriptionDisclosure'));
    expect(source, contains("actionKey: 'restore_purchases'"));
    expect(source, contains("case 'restore_purchases':"));
    expect(source, contains('callback = _restorePurchases'));
  });

  test('iOS price path does not fall back to backend RUB', () {
    expect(
      source,
      contains('_billingController?.localizedPriceForPlan(plan.key)'),
    );
    expect(source, contains('ApplePaywallCopy.priceUnavailable'));
  });
}
