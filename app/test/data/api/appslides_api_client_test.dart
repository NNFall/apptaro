import 'dart:async';
import 'dart:convert';

import 'package:apptaro/data/api/appslides_api_client.dart';
import 'package:apptaro/data/repositories/backend_config_repository.dart';
import 'package:apptaro/data/repositories/language_repository.dart';
import 'package:apptaro/l10n/app_language.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('sends selected app language header to backend', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final languageRepository = LanguageRepository();
    await languageRepository.restore();
    await languageRepository.setLanguage(AppLanguage.russian);
    final recordingClient = _RecordingClient();
    final backendConfig = BackendConfigRepository();
    final client = AppSlidesApiClient(
      client: recordingClient,
      backendConfig: backendConfig,
      languageRepository: languageRepository,
      clientIdProvider: () async => 'at_test1234',
    );

    await client.healthcheck();

    expect(recordingClient.lastRequest?.headers['X-Apptaro-Client-Id'],
        'at_test1234');
    expect(recordingClient.lastRequest?.headers['X-Apptaro-Language'], 'ru');
    expect(
        recordingClient.lastRequest?.headers
            .containsKey('X-AppSlides-Client-Id'),
        isFalse);
  });

  test('requests an Apple app account token from the billing endpoint',
      () async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final recordingClient = _RecordingClient(
      responseBody:
          '{"app_account_token":"123e4567-e89b-12d3-a456-426614174000"}',
    );
    final client = AppSlidesApiClient(
      client: recordingClient,
      backendConfig: BackendConfigRepository(),
      languageRepository: LanguageRepository(),
      clientIdProvider: () async => 'at_test1234',
    );

    final token = await client.fetchAppleAppAccountToken();

    expect(token, '123e4567-e89b-12d3-a456-426614174000');
    expect(recordingClient.lastRequest?.method, 'POST');
    expect(
      recordingClient.lastRequest?.url.path,
      '/v1/billing/apple/account-token',
    );
    expect(recordingClient.lastJsonBody, <String, dynamic>{});
  });

  test('posts Apple transaction diagnostics and parses BillingSummary',
      () async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final recordingClient = _RecordingClient(
      responseBody: jsonEncode(_billingSummaryJson('verified-client')),
    );
    final client = AppSlidesApiClient(
      client: recordingClient,
      backendConfig: BackendConfigRepository(),
      languageRepository: LanguageRepository(),
      clientIdProvider: () async => 'at_test1234',
    );

    final summary = await client.verifyApplePurchase(
      transactionId: '2000000123456789',
      productId: 'weekly_readings',
      operation: 'restore',
      clientSignedData: 'header.payload.signature',
    );

    expect(summary.clientId, 'verified-client');
    expect(recordingClient.lastRequest?.method, 'POST');
    expect(
      recordingClient.lastRequest?.url.path,
      '/v1/billing/apple/verify',
    );
    expect(recordingClient.lastJsonBody, <String, dynamic>{
      'transaction_id': '2000000123456789',
      'product_id': 'weekly_readings',
      'operation': 'restore',
      'client_signed_data': 'header.payload.signature',
    });
  });
}

class _RecordingClient extends http.BaseClient {
  _RecordingClient({this.responseBody = '{"status":"ok"}'});

  final String responseBody;
  http.BaseRequest? lastRequest;
  Map<String, dynamic>? lastJsonBody;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    lastRequest = request;
    if (request is http.Request && request.body.isNotEmpty) {
      lastJsonBody = (jsonDecode(request.body) as Map).cast<String, dynamic>();
    }
    final bytes = utf8.encode(responseBody);
    return http.StreamedResponse(
      Stream<List<int>>.value(bytes),
      200,
      headers: const <String, String>{
        'content-type': 'application/json; charset=utf-8',
      },
    );
  }
}

Map<String, dynamic> _billingSummaryJson(String clientId) {
  return <String, dynamic>{
    'client_id': clientId,
    'support_username': 'support',
    'support_max_url': '',
    'offer_url': 'https://example.com/offer',
    'test_mode': false,
    'plans': <dynamic>[],
    'active_subscription': null,
    'latest_valid_subscription': null,
  };
}
