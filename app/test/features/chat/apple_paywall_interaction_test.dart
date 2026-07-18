import 'package:apptaro/features/billing/apple_paywall_copy.dart';
import 'package:apptaro/features/chat/chat_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('production Markdown renders and launches Apple legal links',
      (tester) async {
    final launchedUris = <Uri>[];
    final disclosure = ApplePaywallCopy.subscriptionDisclosure(
      isRussian: false,
      privacyPolicyUrl: 'https://example.test/privacy',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatMessageMarkdown(
            data: disclosure,
            textColor: Colors.black,
            launchLink: (uri) async => launchedUris.add(uri),
          ),
        ),
      ),
    );
    final semantics = tester.ensureSemantics();

    final privacyLink = find.semantics.byLabel('Privacy Policy');
    final termsLink = find.semantics.byLabel('Terms of Use');
    expect(privacyLink, findsOne);
    expect(termsLink, findsOne);

    tester.semantics.tap(privacyLink);
    await tester.pump();
    tester.semantics.tap(termsLink);
    await tester.pump();

    expect(
      launchedUris,
      <Uri>[
        Uri.parse('https://example.test/privacy'),
        Uri.parse(
          'https://www.apple.com/legal/internet-services/itunes/dev/stdeula/',
        ),
      ],
    );
    semantics.dispose();
  });

  testWidgets('production keyboard restore button invokes its callback',
      (tester) async {
    var restoreCalls = 0;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatKeyboardButton(
            label: 'Restore Purchases',
            compact: false,
            onPressed: () async => restoreCalls += 1,
          ),
        ),
      ),
    );

    final restoreButton = find.widgetWithText(
      ElevatedButton,
      'Restore Purchases',
    );
    expect(restoreButton, findsOneWidget);
    expect(restoreButton.hitTestable(), findsOneWidget);

    await tester.tap(restoreButton);
    await tester.pump();

    expect(restoreCalls, 1);
  });
}
