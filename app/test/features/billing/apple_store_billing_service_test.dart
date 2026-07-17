import 'dart:async';

import 'package:apptaro/data/api/appslides_api_client.dart';
import 'package:apptaro/data/repositories/appslides_repository.dart';
import 'package:apptaro/data/repositories/backend_config_repository.dart';
import 'package:apptaro/data/repositories/language_repository.dart';
import 'package:apptaro/domain/models/billing_plan.dart';
import 'package:apptaro/domain/models/billing_summary.dart';
import 'package:apptaro/features/billing/apple_store_billing_service.dart';
import 'package:apptaro/features/billing/store_billing_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

void main() {
  group('AppleStoreBillingService', () {
    test('uses at least one second as the production restore settlement delay',
        () {
      expect(
        AppleStoreBillingService.defaultRestoreSettlementDelay,
        greaterThanOrEqualTo(const Duration(seconds: 1)),
      );
    });

    test('maps every billing plan to its App Store product', () {
      expect(AppleStoreBillingService.productIdForPlan(_plan('week')),
          'weekly_readings');
      expect(AppleStoreBillingService.productIdForPlan(_plan('month')),
          'monthly_readings');
      expect(AppleStoreBillingService.productIdForPlan(_plan('one10')),
          'one10_readings');
      expect(AppleStoreBillingService.productIdForPlan(_plan('one40')),
          'one40_readings');
    });

    test('attaches backend app account token to the StoreKit purchase',
        () async {
      final harness = _Harness();
      addTearDown(harness.dispose);

      final purchase = harness.service.purchasePlan(_plan('week'));
      await harness.gateway.purchaseStarted.future;

      expect(harness.repository.accountTokenCalls, 1);
      expect(harness.gateway.lastAppAccountToken, _appAccountToken);
      expect(harness.gateway.lastProduct?.id, 'weekly_readings');

      harness.gateway.emit(_purchase(PurchaseStatus.purchased, 'tx-token'));
      await purchase;
    });

    test('rejects malformed app account token before starting StoreKit',
        () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.repository.appAccountToken = 'not-a-canonical-uuid';

      await expectLater(
        harness.service.purchasePlan(_plan('week')),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('canonical UUID'),
          ),
        ),
      );

      expect(harness.gateway.lastProduct, isNull);
      expect(harness.gateway.purchaseStarted.isCompleted, isFalse);
    });

    test('verifies with backend before completing a purchased transaction',
        () async {
      final repository = _BlockingAppleRepository();
      final gateway = _FakeAppleStorePurchaseGateway();
      final service = AppleStoreBillingService(
        repository: repository,
        gateway: gateway,
      );
      addTearDown(() async {
        if (!repository.releaseVerification.isCompleted) {
          repository.releaseVerification.complete();
        }
        await service.dispose();
        await gateway.dispose();
      });

      final purchase = service.purchasePlan(_plan('week'));
      await gateway.purchaseStarted.future;
      gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          'tx-ordered',
          signedData: 'signed-ordered',
          pendingCompletePurchase: true,
        ),
      );
      await repository.verificationStarted.future;

      expect(gateway.completeCalls, 0);
      expect(repository.lastOperation, 'purchase');
      expect(repository.lastTransactionId, 'tx-ordered');
      expect(repository.lastProductId, 'weekly_readings');
      expect(repository.lastClientSignedData, 'signed-ordered');

      repository.releaseVerification.complete();
      final result = await purchase;

      expect(gateway.completeCalls, 1);
      expect(result.transactionReference, 'app_store:tx-ordered');
    });

    test('does not complete a transaction rejected by the backend', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      harness.repository.verificationError =
          StateError('Apple verification is temporarily unavailable.');

      final purchase = harness.service.purchasePlan(_plan('week'));
      final expectation = expectLater(
        purchase,
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('temporarily unavailable'),
          ),
        ),
      );
      await harness.gateway.purchaseStarted.future;
      harness.gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          'tx-rejected',
          pendingCompletePurchase: true,
        ),
      );

      await expectation;
      expect(harness.gateway.completeCalls, 0);
    });

    test('rejects a StoreKit transaction without a transaction id', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);

      final purchase = harness.service.purchasePlan(_plan('week'));
      final expectation = expectLater(
        purchase,
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            contains('transaction id'),
          ),
        ),
      );
      await harness.gateway.purchaseStarted.future;
      harness.gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          null,
          pendingCompletePurchase: true,
        ),
      );

      await expectation;
      expect(harness.repository.verifyCalls, 0);
      expect(harness.gateway.completeCalls, 0);
    });

    test('marks restored transactions as restore and completes every item',
        () async {
      final harness = _Harness();
      addTearDown(harness.dispose);

      final restore = harness.service.restorePurchases();
      await harness.gateway.restoreStarted.future;
      harness.gateway.emitAll(<PurchaseDetails>[
        _purchase(
          PurchaseStatus.restored,
          'restore-1',
          signedData: 'signed-restore-1',
          pendingCompletePurchase: true,
        ),
        _purchase(
          PurchaseStatus.restored,
          'restore-2',
          productId: 'monthly_readings',
          signedData: 'signed-restore-2',
          pendingCompletePurchase: true,
        ),
      ]);

      final result = await restore;

      expect(harness.repository.operations, <String>['restore', 'restore']);
      expect(harness.repository.transactionIds,
          <String>['restore-1', 'restore-2']);
      expect(harness.gateway.completeCalls, 2);
      expect(result?.transactionReference, 'app_store:restore-2');
    });

    test('aggregates restored purchases from separate stream batches',
        () async {
      final harness = _Harness(
        restoreSettlementDelay: const Duration(milliseconds: 80),
      );
      addTearDown(harness.dispose);

      final restore = harness.service.restorePurchases();
      await harness.gateway.restoreStarted.future;
      harness.gateway.emit(
        _purchase(
          PurchaseStatus.restored,
          'restore-batch-1',
          pendingCompletePurchase: true,
        ),
      );
      await Future<void>.delayed(const Duration(milliseconds: 20));
      harness.gateway.emit(
        _purchase(
          PurchaseStatus.restored,
          'restore-batch-2',
          productId: 'monthly_readings',
          pendingCompletePurchase: true,
        ),
      );

      final result = await restore;

      expect(
        harness.repository.transactionIds,
        <String>['restore-batch-1', 'restore-batch-2'],
      );
      expect(harness.repository.operations, <String>['restore', 'restore']);
      expect(harness.gateway.completeCalls, 2);
      expect(result?.transactionReference, 'app_store:restore-batch-2');
    });

    test('processes a restored redelivery after UI restore settlement',
        () async {
      final harness = _Harness(
        restoreSettlementDelay: const Duration(milliseconds: 20),
      );
      addTearDown(harness.dispose);
      var uiCompletions = 0;

      final restore = harness.service.restorePurchases()
        ..then((_) => uiCompletions += 1);
      await harness.gateway.restoreStarted.future;
      harness.gateway.emit(
        _purchase(
          PurchaseStatus.restored,
          'restore-settled',
          pendingCompletePurchase: true,
        ),
      );
      final result = await restore;
      expect(result?.transactionReference, 'app_store:restore-settled');

      harness.gateway.emit(
        _purchase(
          PurchaseStatus.restored,
          'restore-redelivery',
          pendingCompletePurchase: true,
        ),
      );
      await _waitFor(() => harness.repository.verifyCalls == 2);

      expect(uiCompletions, 1);
      expect(
        harness.repository.transactionIds,
        <String>['restore-settled', 'restore-redelivery'],
      );
      expect(harness.repository.operations, <String>['restore', 'restore']);
      expect(harness.gateway.completeCalls, 2);
    });

    test('processes a redelivered purchase without an active operation',
        () async {
      final harness = _Harness();
      addTearDown(harness.dispose);
      await harness.service.initialize();

      harness.gateway.emit(
        _purchase(
          PurchaseStatus.purchased,
          'redelivery-1',
          productId: 'one10_readings',
          signedData: 'redelivered-jws',
          pendingCompletePurchase: true,
        ),
      );
      await _waitFor(() => harness.gateway.completeCalls == 1);

      expect(harness.repository.operations, <String>['purchase']);
      expect(harness.repository.transactionIds, <String>['redelivery-1']);
      expect(harness.repository.clientSignedData, <String>['redelivered-jws']);
    });

    test('rejects overlapping purchase and restore operations', () async {
      final harness = _Harness();
      addTearDown(harness.dispose);

      final purchase = harness.service.purchasePlan(_plan('week'));
      await harness.gateway.purchaseStarted.future;

      await expectLater(
        harness.service.purchasePlan(_plan('month')),
        throwsA(isA<StateError>()),
      );
      await expectLater(
        harness.service.restorePurchases(),
        throwsA(isA<StateError>()),
      );

      harness.gateway.emit(_purchase(PurchaseStatus.purchased, 'tx-finish'));
      await purchase;
    });

    test('serializes purchase stream batches and keeps the queue usable',
        () async {
      final repository = _SerialAppleRepository();
      final gateway = _FakeAppleStorePurchaseGateway();
      final service = AppleStoreBillingService(
        repository: repository,
        gateway: gateway,
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
        _purchase(PurchaseStatus.purchased, 'batch-1', signedData: 'jws-1'),
      );
      await repository.firstStarted.future;
      gateway.emit(
        _purchase(PurchaseStatus.purchased, 'batch-2', signedData: 'jws-2'),
      );
      await _flushEvents();

      expect(repository.startedTransactions, <String>['batch-1']);
      expect(repository.maxConcurrent, 1);

      repository.releaseFirst.complete();
      await _waitFor(() => repository.completedTransactions.length == 2);

      expect(
        repository.completedTransactions,
        <String>['batch-1', 'batch-2'],
      );
      expect(repository.maxConcurrent, 1);
    });

    test('dispose fails a pending operation and rejects future operations',
        () async {
      final harness = _Harness();
      addTearDown(harness.gateway.dispose);

      final purchase = harness.service.purchasePlan(_plan('week'));
      await harness.gateway.purchaseStarted.future;
      final expectation = expectLater(
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

      await expectation;
      await expectLater(
        harness.service.restorePurchases(),
        throwsA(isA<StateError>()),
      );
    });
  });
}

class _Harness {
  _Harness({
    Duration restoreSettlementDelay =
        AppleStoreBillingService.defaultRestoreSettlementDelay,
  })  : gateway = _FakeAppleStorePurchaseGateway(),
        repository = _FakeAppleRepository() {
    service = AppleStoreBillingService(
      repository: repository,
      gateway: gateway,
      restoreSettlementDelay: restoreSettlementDelay,
    );
  }

  final _FakeAppleStorePurchaseGateway gateway;
  final _FakeAppleRepository repository;
  late final AppleStoreBillingService service;

  Future<void> dispose() async {
    await service.dispose();
    await gateway.dispose();
  }
}

class _FakeAppleStorePurchaseGateway implements AppleStorePurchaseGateway {
  final StreamController<List<PurchaseDetails>> _updates =
      StreamController<List<PurchaseDetails>>.broadcast(sync: true);

  final Completer<void> purchaseStarted = Completer<void>();
  final Completer<void> restoreStarted = Completer<void>();
  String? lastAppAccountToken;
  ProductDetails? lastProduct;
  int completeCalls = 0;

  @override
  Stream<List<PurchaseDetails>> get purchaseStream => _updates.stream;

  @override
  Future<bool> isAvailable() async => true;

  @override
  Future<ProductDetailsResponse> queryProductDetails(
      Set<String> productIds) async {
    return ProductDetailsResponse(
      productDetails: productIds.map(_product).toList(),
      notFoundIDs: const <String>[],
    );
  }

  @override
  Future<bool> buyProduct(
    ProductDetails product, {
    required String appAccountToken,
    required bool consumable,
  }) async {
    lastProduct = product;
    lastAppAccountToken = appAccountToken;
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

  void emit(PurchaseDetails purchase) {
    _updates.add(<PurchaseDetails>[purchase]);
  }

  void emitAll(List<PurchaseDetails> purchases) {
    _updates.add(purchases);
  }

  Future<void> dispose() async {
    if (!_updates.isClosed) {
      await _updates.close();
    }
  }
}

class _FakeAppleRepository extends AppSlidesRepository {
  _FakeAppleRepository()
      : super(
          api: AppSlidesApiClient(
            backendConfig: BackendConfigRepository(),
            languageRepository: LanguageRepository(),
            clientIdProvider: () async => 'test-client',
          ),
        );

  int accountTokenCalls = 0;
  int verifyCalls = 0;
  String appAccountToken = _appAccountToken;
  Object? verificationError;
  final List<String> operations = <String>[];
  final List<String> transactionIds = <String>[];
  final List<String> clientSignedData = <String>[];

  @override
  Future<String> fetchAppleAppAccountToken() async {
    accountTokenCalls += 1;
    return appAccountToken;
  }

  @override
  Future<BillingSummary> verifyApplePurchase({
    required String transactionId,
    required String productId,
    required String operation,
    required String clientSignedData,
  }) async {
    verifyCalls += 1;
    operations.add(operation);
    transactionIds.add(transactionId);
    this.clientSignedData.add(clientSignedData);
    if (verificationError case final error?) {
      throw error;
    }
    return _summary(transactionId);
  }
}

class _BlockingAppleRepository extends _FakeAppleRepository {
  final Completer<void> verificationStarted = Completer<void>();
  final Completer<void> releaseVerification = Completer<void>();
  String? lastOperation;
  String? lastTransactionId;
  String? lastProductId;
  String? lastClientSignedData;

  @override
  Future<BillingSummary> verifyApplePurchase({
    required String transactionId,
    required String productId,
    required String operation,
    required String clientSignedData,
  }) async {
    lastOperation = operation;
    lastTransactionId = transactionId;
    lastProductId = productId;
    lastClientSignedData = clientSignedData;
    if (!verificationStarted.isCompleted) {
      verificationStarted.complete();
    }
    await releaseVerification.future;
    return super.verifyApplePurchase(
      transactionId: transactionId,
      productId: productId,
      operation: operation,
      clientSignedData: clientSignedData,
    );
  }
}

class _SerialAppleRepository extends _FakeAppleRepository {
  final Completer<void> firstStarted = Completer<void>();
  final Completer<void> releaseFirst = Completer<void>();
  final List<String> startedTransactions = <String>[];
  final List<String> completedTransactions = <String>[];
  int concurrent = 0;
  int maxConcurrent = 0;

  @override
  Future<BillingSummary> verifyApplePurchase({
    required String transactionId,
    required String productId,
    required String operation,
    required String clientSignedData,
  }) async {
    startedTransactions.add(transactionId);
    concurrent += 1;
    if (concurrent > maxConcurrent) {
      maxConcurrent = concurrent;
    }
    if (transactionId == 'batch-1') {
      if (!firstStarted.isCompleted) {
        firstStarted.complete();
      }
      await releaseFirst.future;
    }
    completedTransactions.add(transactionId);
    concurrent -= 1;
    return _summary(transactionId);
  }
}

const String _appAccountToken = '123e4567-e89b-12d3-a456-426614174000';

BillingPlan _plan(String key) {
  return BillingPlan(
    key: key,
    title: key,
    priceRub: 199,
    limit: 15,
    days: key == 'month' ? 30 : 7,
    recurring: key == 'week' || key == 'month',
    googleProductId: '',
  );
}

ProductDetails _product(String id) {
  return ProductDetails(
    id: id,
    title: id,
    description: id,
    price: r'$1.99',
    rawPrice: 1.99,
    currencyCode: 'USD',
  );
}

PurchaseDetails _purchase(
  PurchaseStatus status,
  String? transactionId, {
  String productId = 'weekly_readings',
  String signedData = 'signed-jws',
  bool pendingCompletePurchase = false,
}) {
  final purchase = PurchaseDetails(
    purchaseID: transactionId,
    productID: productId,
    verificationData: PurchaseVerificationData(
      localVerificationData: signedData,
      serverVerificationData: signedData,
      source: 'app_store',
    ),
    transactionDate: '1',
    status: status,
  );
  purchase.pendingCompletePurchase = pendingCompletePurchase;
  return purchase;
}

BillingSummary _summary(String clientId) {
  return BillingSummary(
    clientId: clientId,
    supportUsername: 'support',
    supportMaxUrl: '',
    offerUrl: 'https://example.com/offer',
    testMode: false,
    plans: const <BillingPlan>[],
    activeSubscription: null,
    latestValidSubscription: null,
  );
}

Future<void> _flushEvents() async {
  await Future<void>.delayed(Duration.zero);
  await Future<void>.delayed(Duration.zero);
}

Future<void> _waitFor(bool Function() condition) async {
  for (var attempt = 0; attempt < 100; attempt += 1) {
    if (condition()) {
      return;
    }
    await Future<void>.delayed(const Duration(milliseconds: 5));
  }
  fail('Condition was not reached in time.');
}
