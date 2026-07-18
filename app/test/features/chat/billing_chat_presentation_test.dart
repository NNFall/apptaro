import 'package:apptaro/core/policies/billing_platform_policy.dart';
import 'package:apptaro/domain/models/billing_payment.dart';
import 'package:apptaro/domain/models/billing_plan.dart';
import 'package:apptaro/domain/models/billing_subscription.dart';
import 'package:apptaro/domain/models/billing_summary.dart';
import 'package:apptaro/features/billing/apple_paywall_copy.dart';
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

  test('native iOS separates subscription disclosure from purchase links', () {
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
      presentation.appleSubscriptionDisclosure,
      contains('automatically renews'),
    );
    expect(
      presentation.appleSubscriptionDisclosure,
      isNot(contains('Privacy Policy')),
    );
    expect(
      presentation.applePurchaseLegalCopy,
      contains('[Privacy Policy](https://example.test/privacy)'),
    );
    expect(
      presentation.applePurchaseLegalCopy,
      contains(
        '[Terms of Use](https://www.apple.com/legal/internet-services/itunes/dev/stdeula/)',
      ),
    );
    expect(
      presentation.applePurchaseLegalCopy,
      isNot(contains('automatically renews')),
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
    expect(presentation.appleSubscriptionDisclosure, isNull);
    expect(presentation.applePurchaseLegalCopy, isNull);
  });

  test('paywall separates subscriptions and consumable reading packs', () {
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
    expect(
      BillingChatPresentation.subscriptionPlans(plans).map((plan) => plan.key),
      <String>['week'],
    );
    expect(
      BillingChatPresentation.readingPackPlans(plans).map((plan) => plan.key),
      <String>['one10'],
    );
  });

  test('known reading pack keys stay consumable without plan metadata', () {
    expect(
      BillingChatPresentation.isOneTimeEntitlement(
        plans: const <BillingPlan>[],
        planKey: 'one10',
      ),
      isTrue,
    );
    expect(
      BillingChatPresentation.isOneTimeEntitlement(
        plans: const <BillingPlan>[],
        planKey: 'month',
      ),
      isFalse,
    );
  });

  test('payment success uses purchased pack instead of active subscription',
      () {
    const week = BillingPlan(
      key: 'week',
      title: 'Weekly',
      priceRub: 0,
      limit: 15,
      days: 7,
      recurring: true,
      googleProductId: 'weekly_readings',
    );
    const one10 = BillingPlan(
      key: 'one10',
      title: '10 readings',
      priceRub: 0,
      limit: 10,
      days: 0,
      recurring: false,
      googleProductId: 'one10_readings',
    );
    const activeWeek = BillingSubscription(
      planKey: 'week',
      status: 'active',
      remaining: 27,
      startsAt: '2026-07-18T00:00:00Z',
      endsAt: '2026-07-25T00:00:00Z',
      autoRenew: true,
      provider: 'app_store',
    );
    const summary = BillingSummary(
      clientId: 'client',
      supportUsername: 'support',
      supportMaxUrl: '',
      offerUrl: '',
      testMode: false,
      plans: <BillingPlan>[week, one10],
      activeSubscription: activeWeek,
      latestValidSubscription: null,
    );
    const payment = BillingPayment(
      paymentId: 'tx-pack',
      status: 'paid',
      confirmationUrl: null,
      testMode: false,
      summary: summary,
      plan: one10,
    );

    final details = BillingChatPresentation.paymentSuccessDetails(payment);

    expect(details?.plan.key, 'one10');
    expect(details?.plan.recurring, isFalse);
    expect(details?.remainingReadings, 27);
    final presentation = BillingChatPresentation.forPlatform(
      platformPolicy: iosPolicy,
      isRussian: false,
      applePrivacyPolicyUrl: 'https://example.test/privacy',
    );
    final copy = presentation.applePaymentSuccessText(
      payment: payment,
      isRussian: false,
      planLineFor: (_) => r'$8.99 - 10 readings (one-time reading pack)',
      formatDate: (value) => value,
    );
    expect(copy, contains('Reading pack added'));
    expect(copy, contains('**Total readings available:** 27'));
    expect(copy, contains('[Privacy Policy](https://example.test/privacy)'));
    expect(copy, contains('[Terms of Use]'));
    expect(copy?.toLowerCase(), isNot(contains('subscription')));
    expect(copy?.toLowerCase(), isNot(contains('valid until')));

    const summaryWithoutEntitlement = BillingSummary(
      clientId: 'client',
      supportUsername: 'support',
      supportMaxUrl: '',
      offerUrl: '',
      testMode: false,
      plans: <BillingPlan>[week, one10],
      activeSubscription: null,
      latestValidSubscription: null,
    );
    const paymentWithoutEntitlement = BillingPayment(
      paymentId: 'tx-pack-no-entitlement',
      status: 'paid',
      confirmationUrl: null,
      testMode: false,
      summary: summaryWithoutEntitlement,
      plan: one10,
    );

    final noEntitlementDetails = BillingChatPresentation.paymentSuccessDetails(
      paymentWithoutEntitlement,
    );
    expect(noEntitlementDetails?.plan.key, 'one10');
    expect(noEntitlementDetails?.remainingReadings, 0);
    final noEntitlementCopy = presentation.applePaymentSuccessText(
      payment: paymentWithoutEntitlement,
      isRussian: false,
      planLineFor: (_) => r'$8.99 - 10 readings (one-time reading pack)',
      formatDate: (value) => value,
    );
    expect(noEntitlementCopy, contains('Reading pack added'));
    expect(noEntitlementCopy, contains('**Total readings available:** 0'));
    expect(
      noEntitlementCopy,
      contains('[Privacy Policy](https://example.test/privacy)'),
    );
    expect(noEntitlementCopy?.toLowerCase(), isNot(contains('subscription')));
    expect(noEntitlementCopy?.toLowerCase(), isNot(contains('valid until')));
  });

  test('canceled subscription display keeps Apple links without renewal copy',
      () {
    final presentation = BillingChatPresentation.forPlatform(
      platformPolicy: iosPolicy,
      isRussian: false,
      applePrivacyPolicyUrl: 'https://example.test/privacy',
    );
    final canceledCopy = ApplePaywallCopy.canceledSubscriptionBalance(
      isRussian: false,
      planLine: r'$4.99 / week - 15 readings',
      remainingReadings: 6,
      validUntil: '2026-07-25',
    );

    final copy = presentation.withApplePurchaseLegalCopy(canceledCopy);

    expect(copy, contains('Subscription canceled'));
    expect(copy, contains(r'$4.99 / week - 15 readings'));
    expect(copy, contains('Total readings available'));
    expect(copy, contains('Subscription access until'));
    expect(copy, contains('2026-07-25'));
    expect(copy, contains('[Privacy Policy](https://example.test/privacy)'));
    expect(copy, contains('[Terms of Use]'));
    expect(copy.toLowerCase(), isNot(contains('automatically renews')));
  });

  test('native iOS keeps plan options available with an active entitlement',
      () {
    expect(
      BillingChatPresentation.showsPlanOptionsOnBalance(
        platformPolicy: iosPolicy,
        hasActiveEntitlement: true,
      ),
      isTrue,
    );
    expect(
      BillingChatPresentation.showsPlanOptionsOnBalance(
        platformPolicy: androidPolicy,
        hasActiveEntitlement: true,
      ),
      isFalse,
    );
    expect(
      BillingChatPresentation.showsPlanOptionsOnBalance(
        platformPolicy: androidPolicy,
        hasActiveEntitlement: false,
      ),
      isTrue,
    );
  });

  test('recurring payment without matching entitlement reports status updating',
      () {
    const month = BillingPlan(
      key: 'month',
      title: 'Monthly',
      priceRub: 0,
      limit: 60,
      days: 30,
      recurring: true,
      googleProductId: 'monthly_readings',
    );
    const summary = BillingSummary(
      clientId: 'client',
      supportUsername: 'support',
      supportMaxUrl: '',
      offerUrl: '',
      testMode: false,
      plans: <BillingPlan>[month],
      activeSubscription: null,
      latestValidSubscription: null,
    );
    const payment = BillingPayment(
      paymentId: 'tx-month',
      status: 'paid',
      confirmationUrl: null,
      testMode: false,
      summary: summary,
      plan: month,
    );
    final presentation = BillingChatPresentation.forPlatform(
      platformPolicy: iosPolicy,
      isRussian: false,
      applePrivacyPolicyUrl: 'https://example.test/privacy',
    );

    final copy = presentation.applePaymentSuccessText(
      payment: payment,
      isRussian: false,
      planLineFor: (_) => r'$14.99 / month - 60 readings',
      formatDate: (value) => value,
    );

    expect(copy, contains('Payment confirmed'));
    expect(copy, contains('subscription status is updating'));
    expect(copy, contains(r'$14.99 / month - 60 readings'));
    expect(copy, contains('Total readings available'));
    expect(copy, contains('[Privacy Policy](https://example.test/privacy)'));
    expect(copy, contains('[Terms of Use]'));
    expect(copy, isNot(contains('Subscription activated')));
    expect(copy, isNot(contains('Valid until')));
    expect(copy, isNot(contains('Subscription access until')));
    expect(copy?.toLowerCase(), isNot(contains('automatically renews')));
  });
}
