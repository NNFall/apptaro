import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Google Play client does not expose redirect billing remnants', () {
    final chatScreen =
        File('lib/features/chat/chat_screen.dart').readAsStringSync();
    final billingController =
        File('lib/features/billing/billing_controller.dart').readAsStringSync();
    final appConfig =
        File('lib/core/config/app_config.dart').readAsStringSync();
    final apiClient =
        File('lib/data/api/appslides_api_client.dart').readAsStringSync();
    final repository = File('lib/data/repositories/appslides_repository.dart')
        .readAsStringSync();
    final pubspec = File('pubspec.yaml').readAsStringSync();
    final manifest =
        File('android/app/src/main/AndroidManifest.xml').readAsStringSync();
    final gradle = File('android/app/build.gradle.kts').readAsStringSync();
    final iosPlist = File('ios/Runner/Info.plist').readAsStringSync();

    expect(pubspec, isNot(contains('app_links')));
    expect(chatScreen, isNot(contains('AppLinks')));
    expect(chatScreen, isNot(contains('_initializeIncomingLinks')));
    expect(chatScreen, isNot(contains('billing/return')));
    expect(chatScreen, isNot(contains('YooKassa')));
    expect(chatScreen, isNot(contains('yookassa')));
    expect(chatScreen, isNot(contains('Payment test mode is enabled')));
    expect(chatScreen, isNot(contains('Тестовый режим оплаты включён')));
    expect(chatScreen, isNot(contains('launch_payment_url')));
    expect(chatScreen, isNot(contains('check_billing_payment')));
    expect(chatScreen, isNot(contains('cancel_billing_subscription')));
    expect(billingController, isNot(contains('cancelSubscription')));
    expect(appConfig, isNot(contains('billingCancelSubscriptionPath')));
    expect(apiClient, isNot(contains('cancelBillingSubscription')));
    expect(repository, isNot(contains('cancelBillingSubscription')));
    expect(manifest, isNot(contains('apptaro://billing')));
    expect(manifest, isNot(contains('appslides://billing')));
    expect(manifest, isNot(contains('android:host="billing"')));
    expect(manifest, isNot(contains('android:pathPrefix="/return"')));
    expect(gradle, isNot(contains('else "debug"')));
    expect(iosPlist, isNot(contains('<string>billing</string>')));
    expect(iosPlist, isNot(contains('<string>appslides</string>')));
    expect(iosPlist, isNot(contains('<string>apptaro</string>')));
    expect(iosPlist, isNot(contains('Таро Расклад')));
  });
  test('Google Play restore is explicit and remains backend-verified', () {
    final billingController =
        File('lib/features/billing/billing_controller.dart').readAsStringSync();
    final googlePlayBillingService =
        File('lib/features/billing/google_play_billing_service.dart')
            .readAsStringSync();

    expect(billingController, isNot(contains('restorePurchases(silent: true)')));
    expect(billingController, isNot(contains('restoreGooglePlayPurchases')));
    expect(billingController, contains('Future<void> restorePurchases()'));
    expect(
      googlePlayBillingService,
      contains('restored: purchase.status == PurchaseStatus.restored'),
    );
    expect(
      googlePlayBillingService,
      contains('await _inAppPurchase.restorePurchases()'),
    );
  });
}
