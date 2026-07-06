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
}

class _RecordingClient extends http.BaseClient {
  http.BaseRequest? lastRequest;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    lastRequest = request;
    final bytes = utf8.encode('{"status":"ok"}');
    return http.StreamedResponse(
      Stream<List<int>>.value(bytes),
      200,
      headers: const <String, String>{
        'content-type': 'application/json; charset=utf-8',
      },
    );
  }
}
