import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Google Play client does not expose redirect billing remnants', () {
    final chatScreen = File('lib/features/chat/chat_screen.dart').readAsStringSync();
    final pubspec = File('pubspec.yaml').readAsStringSync();
    final manifest = File('android/app/src/main/AndroidManifest.xml').readAsStringSync();
    final gradle = File('android/app/build.gradle.kts').readAsStringSync();

    expect(pubspec, isNot(contains('app_links')));
    expect(chatScreen, isNot(contains('AppLinks')));
    expect(chatScreen, isNot(contains('_initializeIncomingLinks')));
    expect(chatScreen, isNot(contains('billing/return')));
    expect(chatScreen, isNot(contains('YooKassa')));
    expect(chatScreen, isNot(contains('launch_payment_url')));
    expect(chatScreen, isNot(contains('check_billing_payment')));
    expect(manifest, isNot(contains('apptaro://billing')));
    expect(manifest, isNot(contains('appslides://billing')));
    expect(manifest, isNot(contains('android:host="billing"')));
    expect(manifest, isNot(contains('android:pathPrefix="/return"')));
    expect(gradle, isNot(contains('else "debug"')));
  });
}
