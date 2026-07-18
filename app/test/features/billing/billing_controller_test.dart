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
import 'package:flutter/foundation.dart';

void main() {
  group('BillingController', () {
    test('platform factory selects Apple only for native iOS', () {
      final repository = _FakeRepository(_summary(clientId: 'factory'));
      final apple = _FakeStoreBillingService();
      final google = _FakeStoreBillingService();

      StoreBillingService create({
        required bool isWeb,
        required TargetPlatform platform,
      }) {
        return createPlatformStoreBillingService(
          repository: repository,
          isWeb: isWeb,
          targetPlatform: platform,
          appleBuilder: (_) => apple,
          googleBuilder: (_) => google,
        );
      }

      expect(
        create(isWeb: false, platform: TargetPlatform.iOS),
        same(apple),
      );
      expect(
        create(isWeb: true, platform: TargetPlatform.iOS),
        same(google),
      );
      expect(
        create(isWeb: false, platform: TargetPlatform.macOS),
        same(google),
      );
      expect(
        create(isWeb: false, platform: TargetPlatform.android),
        same(google),
      );
    });

    test('initialize starts the store and refreshes without restoring',
        () async {
      final plan = _plan();
      final initialSummary =
          _summary(clientId: 'initial', plans: <BillingPlan>[plan]);
      final repository = _FakeRepository(initialSummary);
      final store = _FakeStoreBillingService(
        products: const <StoreBillingProduct>[
          StoreBillingProduct(
            planKey: 'week',
            productId: 'weekly_readings',
            localizedPrice: r'$4.99',
          ),
        ],
      );
      final controller = BillingController(
        repository: repository,
        storeBillingService: store,
      );

      await controller.initialize();

      expect(store.initializeCalls, 1);
      expect(store.loadProductsCalls, 1);
      expect(store.lastLoadedPlans, <BillingPlan>[plan]);
      expect(store.restoreCalls, 0);
      expect(repository.fetchSummaryCalls, 1);
      expect(controller.summary, same(initialSummary));
      expect(controller.localizedPriceForPlan('week'), r'$4.99');
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
      expect(controller.restoreOutcome, BillingRestoreOutcome.restored);
      controller.dispose();
    });

    test('explicit restore reports no purchases without creating payment',
        () async {
      final controller = BillingController(
        repository: _FakeRepository(_summary(clientId: 'initial')),
        storeBillingService: _FakeStoreBillingService(),
      );

      await controller.restorePurchases();

      expect(controller.restoreOutcome, BillingRestoreOutcome.noPurchases);
      expect(controller.payment, isNull);
      controller.dispose();
    });

    test('explicit restore exposes partial warnings', () async {
      final restoredSummary = _summary(clientId: 'restored');
      final controller = BillingController(
        repository: _FakeRepository(_summary(clientId: 'initial')),
        storeBillingService: _FakeStoreBillingService(
          restoreResult: StoreBillingResult(
            summary: restoredSummary,
            transactionReference: 'app_store:restore',
            warnings: const <String>['one transaction failed'],
            partialFailureCount: 1,
          ),
        ),
      );

      await controller.restorePurchases();

      expect(controller.restoreOutcome, BillingRestoreOutcome.partial);
      expect(controller.restoreWarnings, <String>['one transaction failed']);
      expect(controller.restorePartialFailureCount, 1);
      controller.dispose();
    });

    test('explicit restore reports store unavailable as failed', () async {
      final controller = BillingController(
        repository: _FakeRepository(_summary(clientId: 'initial')),
        storeBillingService: _FakeStoreBillingService(
          restoreError: StateError(
            'App Store purchases are unavailable on this device.',
          ),
        ),
      );

      await controller.restorePurchases();

      expect(controller.restoreOutcome, BillingRestoreOutcome.failed);
      expect(controller.error, contains('App Store purchases are unavailable'));
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

    test('rapid double checkout starts one store operation', () async {
      final plan = _plan();
      final purchasedSummary = _summary(clientId: 'purchased');
      final purchaseCompleter = Completer<StoreBillingResult>();
      final store = _FakeStoreBillingService(
        purchaseFuture: purchaseCompleter.future,
      );
      final controller = BillingController(
        repository: _FakeRepository(
          _summary(clientId: 'initial', plans: <BillingPlan>[plan]),
        ),
        storeBillingService: store,
      );

      final first = controller.startCheckout(planKey: plan.key);
      final second = controller.startCheckout(planKey: plan.key);
      await _flushAsyncWork();

      expect(store.purchaseCalls, 1);
      expect(controller.creatingPayment, isTrue);
      expect(controller.loadingSummary, isFalse);
      expect(controller.error, isNull);

      purchaseCompleter.complete(
        StoreBillingResult(
          summary: purchasedSummary,
          transactionReference: 'app_store:first-purchase',
        ),
      );
      final results = await Future.wait(<Future<bool>>[first, second]);

      expect(store.purchaseCalls, 1);
      expect(results, <bool>[true, false]);
      expect(controller.creatingPayment, isFalse);
      expect(controller.error, isNull);
      expect(controller.payment?.paymentId, 'app_store:first-purchase');
      expect(controller.summary, same(purchasedSummary));
      controller.dispose();
    });

    test('rapid double restore starts one store operation', () async {
      final restoredSummary = _summary(clientId: 'restored');
      final restoreCompleter = Completer<StoreBillingResult?>();
      final store = _FakeStoreBillingService(
        restoreFuture: restoreCompleter.future,
      );
      final controller = BillingController(
        repository: _FakeRepository(_summary(clientId: 'initial')),
        storeBillingService: store,
      );

      final first = controller.restorePurchases();
      final second = controller.restorePurchases();
      await _flushAsyncWork();

      expect(store.restoreCalls, 1);
      expect(controller.loadingSummary, isTrue);
      expect(controller.creatingPayment, isFalse);
      expect(controller.error, isNull);

      restoreCompleter.complete(
        StoreBillingResult(
          summary: restoredSummary,
          transactionReference: 'app_store:restore',
        ),
      );
      final results = await Future.wait(<Future<bool>>[first, second]);

      expect(store.restoreCalls, 1);
      expect(results, <bool>[true, false]);
      expect(controller.loadingSummary, isFalse);
      expect(controller.error, isNull);
      expect(controller.restoreOutcome, BillingRestoreOutcome.restored);
      expect(controller.payment?.paymentId, 'app_store:restore');
      controller.dispose();
    });

    test('restore cannot overlap checkout or overwrite its final result',
        () async {
      final plan = _plan();
      final purchasedSummary = _summary(clientId: 'purchased');
      final purchaseCompleter = Completer<StoreBillingResult>();
      final restoreCompleter = Completer<StoreBillingResult?>();
      final store = _FakeStoreBillingService(
        purchaseFuture: purchaseCompleter.future,
        restoreFuture: restoreCompleter.future,
      );
      final controller = BillingController(
        repository: _FakeRepository(
          _summary(clientId: 'initial', plans: <BillingPlan>[plan]),
        ),
        storeBillingService: store,
      );

      final purchase = controller.startCheckout(planKey: plan.key);
      final restore = controller.restorePurchases();
      await _flushAsyncWork();

      expect(store.purchaseCalls, 1);
      expect(store.restoreCalls, 0);
      expect(controller.creatingPayment, isTrue);
      expect(controller.loadingSummary, isFalse);
      expect(controller.restoreOutcome, BillingRestoreOutcome.idle);
      expect(controller.error, isNull);

      purchaseCompleter.complete(
        StoreBillingResult(
          summary: purchasedSummary,
          transactionReference: 'app_store:winning-purchase',
        ),
      );
      restoreCompleter.complete(null);
      final results = await Future.wait(<Future<bool>>[purchase, restore]);

      expect(results, <bool>[true, false]);
      expect(controller.payment?.paymentId, 'app_store:winning-purchase');
      expect(controller.summary, same(purchasedSummary));
      expect(controller.restoreOutcome, BillingRestoreOutcome.idle);
      expect(controller.error, isNull);
      controller.dispose();
    });

    test('checkout and clearPayment cannot mutate an active restore', () async {
      final plan = _plan();
      final initialPurchaseSummary = _summary(clientId: 'first-purchase');
      final restoreCompleter = Completer<StoreBillingResult?>();
      final store = _FakeStoreBillingService(
        purchaseResult: StoreBillingResult(
          summary: initialPurchaseSummary,
          transactionReference: 'app_store:existing-payment',
        ),
        restoreFuture: restoreCompleter.future,
      );
      final controller = BillingController(
        repository: _FakeRepository(
          _summary(clientId: 'initial', plans: <BillingPlan>[plan]),
        ),
        storeBillingService: store,
      );
      await controller.startCheckout(planKey: plan.key);
      expect(controller.payment?.paymentId, 'app_store:existing-payment');

      final restore = controller.restorePurchases();
      final overlappingCheckout = controller.startCheckout(planKey: plan.key);
      controller.clearPayment();
      await _flushAsyncWork();

      expect(store.purchaseCalls, 1);
      expect(store.restoreCalls, 1);
      expect(controller.loadingSummary, isTrue);
      expect(controller.creatingPayment, isFalse);
      expect(controller.payment?.paymentId, 'app_store:existing-payment');

      restoreCompleter.complete(null);
      final results =
          await Future.wait(<Future<bool>>[restore, overlappingCheckout]);

      expect(results, <bool>[true, false]);
      expect(controller.restoreOutcome, BillingRestoreOutcome.noPurchases);
      expect(controller.payment?.paymentId, 'app_store:existing-payment');
      expect(controller.summary, same(initialPurchaseSummary));
      expect(controller.error, isNull);
      controller.dispose();
    });

    test('dispose during checkout ignores late result safely', () async {
      final plan = _plan();
      final purchaseCompleter = Completer<StoreBillingResult>();
      final store = _FakeStoreBillingService(
        purchaseFuture: purchaseCompleter.future,
      );
      final controller = BillingController(
        repository: _FakeRepository(
          _summary(clientId: 'initial', plans: <BillingPlan>[plan]),
        ),
        storeBillingService: store,
      );
      var notifications = 0;
      controller.addListener(() => notifications += 1);

      final checkout = controller.startCheckout(planKey: plan.key);
      await _flushAsyncWork();
      expect(store.purchaseCalls, 1);
      expect(controller.creatingPayment, isTrue);
      final notificationsBeforeDispose = notifications;

      controller.dispose();
      purchaseCompleter.complete(
        StoreBillingResult(
          summary: _summary(clientId: 'late-purchase'),
          transactionReference: 'app_store:late-purchase',
        ),
      );
      expect(await checkout, isFalse);
      await _flushAsyncWork();

      expect(controller.payment, isNull);
      expect(controller.creatingPayment, isFalse);
      expect(notifications, notificationsBeforeDispose);
      expect(store.disposeCalls, 1);
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
    this.purchaseFuture,
    this.restoreResult,
    this.restoreFuture,
    this.restoreError,
    this.products = const <StoreBillingProduct>[],
  });

  final StoreBillingResult? purchaseResult;
  final Future<StoreBillingResult>? purchaseFuture;
  final StoreBillingResult? restoreResult;
  final Future<StoreBillingResult?>? restoreFuture;
  final Object? restoreError;
  final List<StoreBillingProduct> products;

  int initializeCalls = 0;
  int purchaseCalls = 0;
  int restoreCalls = 0;
  int loadProductsCalls = 0;
  int disposeCalls = 0;
  BillingPlan? lastPurchasedPlan;
  List<BillingPlan> lastLoadedPlans = const <BillingPlan>[];

  @override
  Future<void> initialize() async {
    initializeCalls += 1;
  }

  @override
  Future<List<StoreBillingProduct>> loadProducts(
    List<BillingPlan> plans,
  ) async {
    loadProductsCalls += 1;
    lastLoadedPlans = List<BillingPlan>.of(plans);
    return products;
  }

  @override
  Future<StoreBillingResult> purchasePlan(BillingPlan plan) async {
    purchaseCalls += 1;
    lastPurchasedPlan = plan;
    if (purchaseFuture case final future?) {
      return future;
    }
    return purchaseResult!;
  }

  @override
  Future<StoreBillingResult?> restorePurchases() async {
    restoreCalls += 1;
    if (restoreError case final error?) {
      throw error;
    }
    if (restoreFuture case final future?) {
      return future;
    }
    return restoreResult;
  }

  @override
  Future<void> dispose() async {
    disposeCalls += 1;
  }
}

Future<void> _flushAsyncWork() async {
  await Future<void>.delayed(Duration.zero);
  await Future<void>.delayed(Duration.zero);
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
