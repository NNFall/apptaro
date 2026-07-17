import 'package:apptaro/core/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('AppConfig.resolveBackendBaseUrl', () {
    test('preserves the existing backend URL outside Apple builds', () {
      expect(
        AppConfig.resolveBackendBaseUrl(
          isApplePlatform: false,
          appleBackendBaseUrl: '',
        ),
        AppConfig.fixedBackendBaseUrl,
      );
    });

    test('accepts an absolute HTTPS URL for an Apple build', () {
      expect(
        AppConfig.resolveBackendBaseUrl(
          isApplePlatform: true,
          appleBackendBaseUrl: 'https://api.example.test/',
        ),
        'https://api.example.test',
      );
    });

    test('rejects a missing Apple backend URL', () {
      expect(
        () => AppConfig.resolveBackendBaseUrl(
          isApplePlatform: true,
          appleBackendBaseUrl: '',
        ),
        throwsA(isA<StateError>()),
      );
    });

    test('rejects a non-HTTPS Apple backend URL', () {
      expect(
        () => AppConfig.resolveBackendBaseUrl(
          isApplePlatform: true,
          appleBackendBaseUrl: 'http://api.example.test',
        ),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('rejects a relative Apple backend URL', () {
      expect(
        () => AppConfig.resolveBackendBaseUrl(
          isApplePlatform: true,
          appleBackendBaseUrl: '/v1',
        ),
        throwsA(isA<ArgumentError>()),
      );
    });
  });
}
