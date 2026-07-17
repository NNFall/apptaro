import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:apptaro/data/api/appslides_api_client.dart';
import 'package:apptaro/data/repositories/appslides_repository.dart';
import 'package:apptaro/data/repositories/backend_config_repository.dart';
import 'package:apptaro/data/repositories/language_repository.dart';
import 'package:apptaro/domain/models/billing_plan.dart';
import 'package:apptaro/domain/models/billing_summary.dart';
import 'package:apptaro/features/billing/billing_controller.dart';
import 'package:apptaro/features/billing/store_billing_service.dart';

void main() {
  group('BillingController', () {
    test('initialize starts the store and refreshes without restoring',
        () async {
      final initialSummary = _summary(clientId: 'initial');
      final repository = _FakeRepository(initialSummary);
      final store = _FakeStoreBillingService();
      final controller = BillingController(
        repository: repository,
        storeBillingService: store,
      );

      await controller.initialize();

      expect(store.initializeCalls, 1);
      expect(store.restoreCalls, 0);
      expect(repository.fetchSummaryCalls, 1);
      expect(controller.summary, same(initialSummary));
      controller.dispose();
    });

    test('explicit restore updates the summary and payment', () async {
      final initialSummary = _summary(clientId: 'initial');
      final restoredSummary = _summary(clientId: 'restored');
      final repository = _FakeRepository(initialSummary);
      final store = _FakeStoreBillingService(
        restoreResult: StoreBillingResult(
          summary: restoredSummary,
          transactionReference: 'google_play:restore',
        ),
      );
      final controller = BillingController(
        repository: repository,
        storeBillingService: store,
      );

      await controller.restorePurchases();

      expect(store.restoreCalls, 1);
      expect(controller.summary, same(restoredSummary));
      expect(controller.payment?.paymentId, 'google_play:restore');
      expect(controller.payment?.summary, same(restoredSummary));
      controller.dispose();
    });

    test('purchase uses the payment id returned by the store', () async {
      final plan = _plan();
      final initialSummary =
          _summary(clientId: 'initial', plans: <BillingPlan>[plan]);
      final purchasedSummary = _summary(clientId: 'purchased');
      final repository = _FakeRepository(initialSummary);
      final store = _FakeStoreBillingService(
        purchaseResult: StoreBillingResult(
          summary: purchasedSummary,
          transactionReference: 'store:custom-transaction-id',
        ),
      );
      final controller = BillingController(
        repository: repository,
        storeBillingService: store,
      );

      await controller.startCheckout(planKey: plan.key);

      expect(store.purchaseCalls, 1);
      expect(store.lastPurchasedPlan, same(plan));
      expect(controller.summary, same(purchasedSummary));
      expect(controller.payment?.paymentId, 'store:custom-transaction-id');
      expect(controller.payment?.plan, same(plan));
      controller.dispose();
    });

    test('does not notify listeners after dispose', () async {
      final repository = _DeferredRepository();
      final store = _FakeStoreBillingService();
      final controller = BillingController(
        repository: repository,
        storeBillingService: store,
      );
      var notifications = 0;
      controller.addListener(() => notifications += 1);

      final refresh = controller.refreshSummary();
      expect(notifications, 1);
      controller.dispose();
      repository.summaryCompleter.complete(_summary(clientId: 'late'));

      await refresh;

      expect(notifications, 1);
    });
  });
}

class _FakeStoreBillingService implements StoreBillingService {
  _FakeStoreBillingService({
    this.purchaseResult,
    this.restoreResult,
  });

  final StoreBillingResult? purchaseResult;
  final StoreBillingResult? restoreResult;

  int initializeCalls = 0;
  int purchaseCalls = 0;
  int restoreCalls = 0;
  int disposeCalls = 0;
  BillingPlan? lastPurchasedPlan;

  @override
  Future<void> initialize() async {
    initializeCalls += 1;
  }

  @override
  Future<StoreBillingResult> purchasePlan(BillingPlan plan) async {
    purchaseCalls += 1;
    lastPurchasedPlan = plan;
    return purchaseResult!;
  }

  @override
  Future<StoreBillingResult?> restorePurchases() async {
    restoreCalls += 1;
    return restoreResult;
  }

  @override
  Future<void> dispose() async {
    disposeCalls += 1;
  }
}

class _FakeRepository extends AppSlidesRepository {
  _FakeRepository(this.summary)
      : super(
          api: AppSlidesApiClient(
            backendConfig: BackendConfigRepository(),
            languageRepository: LanguageRepository(),
            clientIdProvider: () async => 'test-client',
          ),
        );

  final BillingSummary summary;
  int fetchSummaryCalls = 0;

  @override
  Future<BillingSummary> fetchBillingSummary() async {
    fetchSummaryCalls += 1;
    return summary;
  }
}

class _DeferredRepository extends AppSlidesRepository {
  _DeferredRepository()
      : super(
          api: AppSlidesApiClient(
            backendConfig: BackendConfigRepository(),
            languageRepository: LanguageRepository(),
            clientIdProvider: () async => 'test-client',
          ),
        );

  final Completer<BillingSummary> summaryCompleter =
      Completer<BillingSummary>();

  @override
  Future<BillingSummary> fetchBillingSummary() => summaryCompleter.future;
}

BillingPlan _plan() {
  return const BillingPlan(
    key: 'week',
    title: 'Weekly',
    priceRub: 199,
    limit: 15,
    days: 7,
    recurring: true,
    googleProductId: 'weekly_readings',
  );
}

BillingSummary _summary({
  required String clientId,
  List<BillingPlan> plans = const <BillingPlan>[],
}) {
  return BillingSummary(
    clientId: clientId,
    supportUsername: 'support',
    supportMaxUrl: '',
    offerUrl: 'https://example.com/offer',
    testMode: false,
    plans: plans,
    activeSubscription: null,
    latestValidSubscription: null,
  );
}
