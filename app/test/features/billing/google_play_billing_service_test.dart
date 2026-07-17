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

void main() {
  group('GooglePlayBillingService', () {
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
      expect(harness.repository.verifyCalls, 1);

      harness.gateway.emit(_purchase(PurchaseStatus.restored, 'restore-2'));
      final restoreResult = await restore;

      expect(restoreResult?.transactionReference, 'google_play:restore-2');
      expect(harness.repository.verifyCalls, 2);
      expect(harness.repository.lastRestored, isTrue);
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

    test('uses deterministic reference when purchase id is absent', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);

      final purchase = harness.service.purchasePlan(_plan());
      await harness.gateway.purchaseStarted.future;
      harness.gateway.emit(_purchase(PurchaseStatus.purchased, null));

      final result = await purchase;

      expect(result.transactionReference, 'google_play:weekly_readings');
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

  @override
  Stream<List<PurchaseDetails>> get purchaseStream => _updates.stream;

  @override
  Future<bool> isAvailable() async => true;

  @override
  Future<ProductDetailsResponse> queryProductDetails(
    Set<String> productIds,
  ) async {
    return ProductDetailsResponse(
      productDetails: productIds.map(_product).toList(),
      notFoundIDs: const <String>[],
    );
  }

  @override
  Future<bool> buyNonConsumable(ProductDetails product) async {
    if (!purchaseStarted.isCompleted) {
      purchaseStarted.complete();
    }
    return true;
  }

  @override
  Future<bool> buyConsumable(ProductDetails product) async {
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
  Future<void> completePurchase(PurchaseDetails purchase) async {}

  @override
  Future<void> consumePurchase(PurchaseDetails purchase) async {}

  void emit(PurchaseDetails purchase) {
    _updates.add(<PurchaseDetails>[purchase]);
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

  @override
  Future<BillingSummary> verifyGooglePlayPurchase({
    required String productId,
    required String purchaseToken,
    required String packageName,
    bool restored = false,
  }) async {
    verifyCalls += 1;
    lastRestored = restored;
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

PurchaseDetails _purchase(PurchaseStatus status, String? purchaseId) {
  return PurchaseDetails(
    purchaseID: purchaseId,
    productID: 'weekly_readings',
    verificationData: PurchaseVerificationData(
      localVerificationData: 'local-token',
      serverVerificationData: 'server-token',
      source: 'google_play',
    ),
    transactionDate: '1',
    status: status,
  );
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
