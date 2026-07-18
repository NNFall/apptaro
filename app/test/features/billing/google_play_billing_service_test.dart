import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import 'package:apptaro/data/api/appslides_api_client.dart';
import 'package:apptaro/data/repositories/appslides_repository.dart';
import 'package:apptaro/data/repositories/backend_config_repository.dart';
import 'package:apptaro/data/repositories/language_repository.dart';
import 'package:apptaro/domain/models/billing_plan.dart';
import 'package:apptaro/domain/models/billing_summary.dart';
import 'package:apptaro/features/billing/google_play_billing_service.dart';
import 'package:apptaro/features/billing/store_billing_service.dart';

void main() {
  group('GooglePlayBillingService', () {
    test('loads and caches localized Google Play product prices', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);

      final first = await harness.service.loadProducts(<BillingPlan>[_plan()]);
      final second = await harness.service.loadProducts(<BillingPlan>[_plan()]);

      expect(first.single.planKey, 'week');
      expect(first.single.localizedPrice, r'$1.99');
      expect(second, first);
      expect(harness.gateway.queryCalls, 1);
    });

    test('rejects every second operation while a purchase is active', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);

      final purchase = harness.service.purchasePlan(_plan());
      await harness.gateway.purchaseStarted.future;

      await expectLater(
        harness.service.purchasePlan(_plan()),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('already in progress'),
          ),
        ),
      );
      await expectLater(
        harness.service.restorePurchases(),
        throwsA(isA<StateError>()),
      );

      harness.gateway.emit(_purchase(PurchaseStatus.purchased, 'purchase-1'));
      await purchase;
    });

    test('rejects every second operation while restore is active', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);

      final restore = harness.service.restorePurchases();
      await harness.gateway.restoreStarted.future;

      await expectLater(
        harness.service.restorePurchases(),
        throwsA(isA<StateError>()),
      );
      await expectLater(
        harness.service.purchasePlan(_plan()),
        throwsA(isA<StateError>()),
      );

      harness.gateway.emit(_purchase(PurchaseStatus.restored, 'restore-1'));
      await restore;
    });

    test('purchased and restored events complete only matching operations',
        () async {
      final harness = _Harness();
      addTearDown(harness.dispose);

      var purchaseCompleted = false;
      final purchase = harness.service.purchasePlan(_plan())
        ..then((_) => purchaseCompleted = true);
      await harness.gateway.purchaseStarted.future;

      harness.gateway.emit(_purchase(PurchaseStatus.restored, 'ignored-1'));
      await _flushEvents();

      expect(purchaseCompleted, isFalse);
      expect(harness.repository.verifyCalls, 0);

      harness.gateway.emit(_purchase(PurchaseStatus.purchased, 'purchase-2'));
      final purchaseResult = await purchase;

      expect(purchaseResult.transactionReference, 'google_play:purchase-2');
      expect(harness.repository.verifyCalls, 1);

      var restoreCompleted = false;
      final restore = harness.service.restorePurchases()
        ..then((_) => restoreCompleted = true);
      await harness.gateway.restoreStarted.future;

      harness.gateway.emit(_purchase(PurchaseStatus.purchased, 'ignored-2'));
      await _flushEvents();

      expect(restoreCompleted, isFalse);
      expect(harness.repository.verifyCalls, 2);

      harness.gateway.emit(_purchase(PurchaseStatus.restored, 'restore-2'));
      final restoreResult = await restore;

      expect(restoreResult?.transactionReference, 'google_play:restore-2');
      expect(harness.repository.verifyCalls, 3);
      expect(harness.repository.lastRestored, isTrue);
    });

    test('processes a purchased redelivery without an active UI operation',
        () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      await harness.service.initialize();

      harness.gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          'redelivery-1',
          productId: 'one10_readings',
          token: 'redelivery-token',
          pendingCompletePurchase: true,
        ),
      );
      await _flushEvents();

      expect(harness.repository.verifyCalls, 1);
      expect(harness.repository.purchaseTokens, <String>['redelivery-token']);
      expect(harness.gateway.consumeCalls, 1);
      expect(harness.gateway.completeCalls, 1);
    });

    test('processes purchase stream batches sequentially and in order',
        () async {
      final gateway = _FakeStorePurchaseGateway();
      final repository = _BlockingBillingRepository();
      final service = GooglePlayBillingService(
        repository: repository,
        gateway: gateway,
        packageName: 'com.nexwit.tarot',
      );
      addTearDown(() async {
        if (!repository.releaseFirst.isCompleted) {
          repository.releaseFirst.complete();
        }
        await service.dispose();
        await gateway.dispose();
      });
      await service.initialize();

      gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          'batch-1',
          token: 'batch-token-1',
          pendingCompletePurchase: true,
        ),
      );
      await repository.firstStarted.future;
      gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          'batch-2',
          token: 'batch-token-2',
          pendingCompletePurchase: true,
        ),
      );
      await _flushEvents();
      final concurrencyBeforeRelease = repository.maxConcurrent;
      final startsBeforeRelease = List<String>.of(repository.startedTokens);

      repository.releaseFirst.complete();
      await _waitFor(() => repository.completedTokens.length == 2);

      expect(concurrencyBeforeRelease, 1);
      expect(startsBeforeRelease, <String>['batch-token-1']);
      expect(
        repository.startedTokens,
        <String>['batch-token-1', 'batch-token-2'],
      );
      expect(
        repository.completedTokens,
        <String>['batch-token-1', 'batch-token-2'],
      );
      expect(gateway.completeCalls, 2);
    });

    test('continues processing batches after a verification error', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.repository.failingTokens.add('bad-batch-token');
      await harness.service.initialize();

      harness.gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          'bad-batch',
          token: 'bad-batch-token',
          pendingCompletePurchase: true,
        ),
      );
      harness.gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          'good-batch',
          token: 'good-batch-token',
          pendingCompletePurchase: true,
        ),
      );
      await _waitFor(() => harness.repository.verifyCalls == 2);
      await _flushEvents();

      expect(
        harness.repository.purchaseTokens,
        <String>['bad-batch-token', 'good-batch-token'],
      );
      expect(harness.gateway.completeCalls, 1);
    });

    test('orders stream errors behind active batches and keeps queue usable',
        () async {
      final gateway = _FakeStorePurchaseGateway();
      final repository = _BlockingBillingRepository();
      final service = GooglePlayBillingService(
        repository: repository,
        gateway: gateway,
        packageName: 'com.nexwit.tarot',
      );
      addTearDown(() async {
        if (!repository.releaseFirst.isCompleted) {
          repository.releaseFirst.complete();
        }
        await service.dispose();
        await gateway.dispose();
      });

      Object? purchaseOutcome;
      final purchase = service.purchasePlan(_plan());
      final observedPurchase = purchase.then<Object?>(
        (result) {
          purchaseOutcome = result;
          return result;
        },
        onError: (Object error) {
          purchaseOutcome = error;
          return error;
        },
      );
      await gateway.purchaseStarted.future;
      gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          'ordered-purchase',
          token: 'batch-token-1',
        ),
      );
      await repository.firstStarted.future;

      gateway.emitError(StateError('Purchase stream failed.'));
      await _flushEvents();
      final outcomeBeforeRelease = purchaseOutcome;

      repository.releaseFirst.complete();
      final result = await observedPurchase;
      gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          'after-stream-error',
          token: 'after-error-token',
        ),
      );
      await _waitFor(
        () => repository.completedTokens.contains('after-error-token'),
      );

      expect(outcomeBeforeRelease, isNull);
      expect(result, isA<StoreBillingResult>());
      expect(
        (result as StoreBillingResult).transactionReference,
        'google_play:ordered-purchase',
      );
      expect(
        repository.startedTokens,
        <String>['batch-token-1', 'after-error-token'],
      );
      expect(repository.maxConcurrent, 1);
    });

    test('verifies and completes every restored item before one result',
        () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      var restoreResults = 0;
      final restore = harness.service.restorePurchases()
        ..then((_) => restoreResults += 1);
      await harness.gateway.restoreStarted.future;

      harness.gateway.emitAll(<PurchaseDetails>[
        _purchase(
          PurchaseStatus.restored,
          'restore-batch-1',
          token: 'restore-token-1',
          pendingCompletePurchase: true,
        ),
        _purchase(
          PurchaseStatus.restored,
          'restore-batch-2',
          token: 'restore-token-2',
          pendingCompletePurchase: true,
        ),
      ]);
      final result = await restore;

      expect(harness.repository.verifyCalls, 2);
      expect(
        harness.repository.purchaseTokens,
        <String>['restore-token-1', 'restore-token-2'],
      );
      expect(harness.gateway.completeCalls, 2);
      expect(restoreResults, 1);
      expect(result?.transactionReference, 'google_play:restore-batch-2');
    });

    test('ignores stale product errors for an active purchase', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      Object? settled;
      final purchase = harness.service.purchasePlan(_plan());
      final observed = purchase.then<Object?>(
        (result) {
          settled = result;
          return result;
        },
        onError: (Object error) {
          settled = error;
          return error;
        },
      );
      await harness.gateway.purchaseStarted.future;

      harness.gateway.emit(
        _purchase(
          PurchaseStatus.error,
          'stale-error',
          productId: 'monthly_readings',
        ),
      );
      await _flushEvents();

      expect(settled, isNull);

      harness.gateway.emit(
        _purchase(PurchaseStatus.purchased, 'purchase-after-stale'),
      );
      final result = await observed;
      expect(result, isA<StoreBillingResult>());
    });

    test('restore verification failure completes with the backend error',
        () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.repository.verificationError =
          StateError('Backend rejected restored purchase.');
      final restore = harness.service.restorePurchases();
      final expectation = expectLater(
        restore,
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('Backend rejected'),
          ),
        ),
      );
      await harness.gateway.restoreStarted.future;

      harness.gateway.emit(
        _purchase(PurchaseStatus.restored, 'restore-failure'),
      );

      await expectation;
    });

    test('dispose fails a pending operation and rejects future operations',
        () async {
      final harness = _Harness();
      addTearDown(harness.gateway.dispose);

      final purchase = harness.service.purchasePlan(_plan());
      await harness.gateway.purchaseStarted.future;
      final pendingExpectation = expectLater(
        purchase,
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('disposed'),
          ),
        ),
      );

      await harness.service.dispose();

      await pendingExpectation;
      await expectLater(
        harness.service.restorePurchases(),
        throwsA(isA<StateError>()),
      );
    });

    test('fallback references differ for different purchase tokens', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);

      final firstPurchase = harness.service.purchasePlan(_plan());
      await harness.gateway.purchaseStarted.future;
      harness.gateway.emit(
        _purchase(PurchaseStatus.purchased, null, token: 'fallback-token-a'),
      );
      final firstResult = await firstPurchase;

      final secondPurchase = harness.service.purchasePlan(_plan());
      await _waitFor(() => harness.gateway.buyCalls == 2);
      harness.gateway.emit(
        _purchase(PurchaseStatus.purchased, null, token: 'fallback-token-b'),
      );
      final secondResult = await secondPurchase;

      expect(firstResult.transactionReference, startsWith('google_play:'));
      expect(secondResult.transactionReference, startsWith('google_play:'));
      expect(firstResult.transactionReference,
          isNot(secondResult.transactionReference));
      expect(firstResult.transactionReference,
          isNot(contains('fallback-token-a')));
      expect(secondResult.transactionReference,
          isNot(contains('fallback-token-b')));
    });

    test('fallback reference is stable for the same token', () async {
      final firstHarness = _Harness();
      final secondHarness = _Harness();
      addTearDown(firstHarness.dispose);
      addTearDown(secondHarness.dispose);

      final firstPurchase = firstHarness.service.purchasePlan(_plan());
      final secondPurchase = secondHarness.service.purchasePlan(_plan());
      await firstHarness.gateway.purchaseStarted.future;
      await secondHarness.gateway.purchaseStarted.future;
      firstHarness.gateway.emit(
        _purchase(PurchaseStatus.purchased, null, token: 'repeated-token'),
      );
      secondHarness.gateway.emit(
        _purchase(PurchaseStatus.purchased, null, token: 'repeated-token'),
      );

      expect(
        (await firstPurchase).transactionReference,
        (await secondPurchase).transactionReference,
      );
    });
  });
}

class _Harness {
  _Harness()
      : gateway = _FakeStorePurchaseGateway(),
        repository = _FakeBillingRepository() {
    service = GooglePlayBillingService(
      repository: repository,
      gateway: gateway,
      packageName: 'com.nexwit.tarot',
    );
  }

  final _FakeStorePurchaseGateway gateway;
  final _FakeBillingRepository repository;
  late final GooglePlayBillingService service;

  Future<void> dispose() async {
    await service.dispose();
    await gateway.dispose();
  }
}

class _FakeStorePurchaseGateway implements StorePurchaseGateway {
  final StreamController<List<PurchaseDetails>> _updates =
      StreamController<List<PurchaseDetails>>.broadcast(sync: true);

  final Completer<void> purchaseStarted = Completer<void>();
  final Completer<void> restoreStarted = Completer<void>();
  int buyCalls = 0;
  int completeCalls = 0;
  int consumeCalls = 0;
  int queryCalls = 0;

  @override
  Stream<List<PurchaseDetails>> get purchaseStream => _updates.stream;

  @override
  Future<bool> isAvailable() async => true;

  @override
  Future<ProductDetailsResponse> queryProductDetails(
    Set<String> productIds,
  ) async {
    queryCalls += 1;
    return ProductDetailsResponse(
      productDetails: productIds.map(_product).toList(),
      notFoundIDs: const <String>[],
    );
  }

  @override
  Future<bool> buyNonConsumable(ProductDetails product) async {
    buyCalls += 1;
    if (!purchaseStarted.isCompleted) {
      purchaseStarted.complete();
    }
    return true;
  }

  @override
  Future<bool> buyConsumable(ProductDetails product) async {
    buyCalls += 1;
    if (!purchaseStarted.isCompleted) {
      purchaseStarted.complete();
    }
    return true;
  }

  @override
  Future<void> restorePurchases() async {
    if (!restoreStarted.isCompleted) {
      restoreStarted.complete();
    }
  }

  @override
  Future<void> completePurchase(PurchaseDetails purchase) async {
    completeCalls += 1;
  }

  @override
  Future<void> consumePurchase(PurchaseDetails purchase) async {
    consumeCalls += 1;
  }

  void emit(PurchaseDetails purchase) {
    _updates.add(<PurchaseDetails>[purchase]);
  }

  void emitAll(List<PurchaseDetails> purchases) {
    _updates.add(purchases);
  }

  void emitError(Object error) {
    _updates.addError(error);
  }

  Future<void> dispose() async {
    if (!_updates.isClosed) {
      await _updates.close();
    }
  }
}

class _FakeBillingRepository extends AppSlidesRepository {
  _FakeBillingRepository()
      : super(
          api: AppSlidesApiClient(
            backendConfig: BackendConfigRepository(),
            languageRepository: LanguageRepository(),
            clientIdProvider: () async => 'test-client',
          ),
        );

  int verifyCalls = 0;
  bool? lastRestored;
  Object? verificationError;
  final List<String> purchaseTokens = <String>[];
  final Set<String> failingTokens = <String>{};

  @override
  Future<BillingSummary> verifyGooglePlayPurchase({
    required String productId,
    required String purchaseToken,
    required String packageName,
    bool restored = false,
  }) async {
    verifyCalls += 1;
    lastRestored = restored;
    purchaseTokens.add(purchaseToken);
    final error = failingTokens.contains(purchaseToken)
        ? StateError('Verification failed for $purchaseToken.')
        : verificationError;
    if (error != null) {
      throw error;
    }
    return _summary();
  }
}

class _BlockingBillingRepository extends AppSlidesRepository {
  _BlockingBillingRepository()
      : super(
          api: AppSlidesApiClient(
            backendConfig: BackendConfigRepository(),
            languageRepository: LanguageRepository(),
            clientIdProvider: () async => 'test-client',
          ),
        );

  final Completer<void> firstStarted = Completer<void>();
  final Completer<void> releaseFirst = Completer<void>();
  final List<String> startedTokens = <String>[];
  final List<String> completedTokens = <String>[];
  int concurrent = 0;
  int maxConcurrent = 0;

  @override
  Future<BillingSummary> verifyGooglePlayPurchase({
    required String productId,
    required String purchaseToken,
    required String packageName,
    bool restored = false,
  }) async {
    startedTokens.add(purchaseToken);
    concurrent += 1;
    if (concurrent > maxConcurrent) {
      maxConcurrent = concurrent;
    }
    if (purchaseToken == 'batch-token-1') {
      if (!firstStarted.isCompleted) {
        firstStarted.complete();
      }
      await releaseFirst.future;
    }
    completedTokens.add(purchaseToken);
    concurrent -= 1;
    return _summary();
  }
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

ProductDetails _product(String id) {
  return ProductDetails(
    id: id,
    title: 'Weekly',
    description: 'Weekly readings',
    price: r'$1.99',
    rawPrice: 1.99,
    currencyCode: 'USD',
  );
}

PurchaseDetails _purchase(
  PurchaseStatus status,
  String? purchaseId, {
  String productId = 'weekly_readings',
  String token = 'server-token',
  bool pendingCompletePurchase = false,
}) {
  final purchase = PurchaseDetails(
    purchaseID: purchaseId,
    productID: productId,
    verificationData: PurchaseVerificationData(
      localVerificationData: 'local-token',
      serverVerificationData: token,
      source: 'google_play',
    ),
    transactionDate: '1',
    status: status,
  );
  purchase.pendingCompletePurchase = pendingCompletePurchase;
  return purchase;
}

BillingSummary _summary() {
  return const BillingSummary(
    clientId: 'test-client',
    supportUsername: 'support',
    supportMaxUrl: '',
    offerUrl: 'https://example.com/offer',
    testMode: false,
    plans: <BillingPlan>[],
    activeSubscription: null,
    latestValidSubscription: null,
  );
}

Future<void> _flushEvents() async {
  await Future<void>.delayed(Duration.zero);
  await Future<void>.delayed(Duration.zero);
}

Future<void> _waitFor(bool Function() condition) async {
  for (var attempt = 0; attempt < 20; attempt += 1) {
    if (condition()) {
      return;
    }
    await _flushEvents();
  }
  fail('Condition was not reached in time.');
}
