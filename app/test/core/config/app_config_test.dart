import 'package:apptaro/core/config/app_config.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('defines the Apple billing endpoint and product identity', () {
    expect(
      AppConfig.billingAppleAccountTokenPath,
      '/v1/billing/apple/account-token',
    );
    expect(AppConfig.billingAppleVerifyPath, '/v1/billing/apple/verify');
    expect(AppConfig.appleBundleId, 'com.nexwit.tarot');
  });

  group('AppConfig.shouldRequireAppleBackend', () {
    test('requires the Apple backend for native iOS', () {
      expect(
        AppConfig.shouldRequireAppleBackend(
          isWeb: false,
          targetPlatform: TargetPlatform.iOS,
        ),
        isTrue,
      );
    });

    test('does not require the Apple backend for native macOS', () {
      expect(
        AppConfig.shouldRequireAppleBackend(
          isWeb: false,
          targetPlatform: TargetPlatform.macOS,
        ),
        isFalse,
      );
    });

    test('does not require the Apple backend for native Android', () {
      expect(
        AppConfig.shouldRequireAppleBackend(
          isWeb: false,
          targetPlatform: TargetPlatform.android,
        ),
        isFalse,
      );
    });

    test('does not require the Apple backend on web', () {
      expect(
        AppConfig.shouldRequireAppleBackend(
          isWeb: true,
          targetPlatform: TargetPlatform.iOS,
        ),
        isFalse,
      );
    });
  });

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

    test('accepts a valid explicit HTTPS port', () {
      expect(
        AppConfig.resolveBackendBaseUrl(
          isApplePlatform: true,
          appleBackendBaseUrl: 'https://api.example.test:8443/',
        ),
        'https://api.example.test:8443',
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

    const invalidOrigins = <String>[
      ' https://api.example.test',
      'https://api.example.test ',
      'https://api .example.test',
      'https://user:pass@api.example.test',
      'https://api.example.test/v1',
      'https://api.example.test?debug=true',
      'https://api.example.test#fragment',
      'https://api.example.test:0',
      'https://api.example.test:65536',
      'https://api.example.test:abc',
    ];

    for (final origin in invalidOrigins) {
      test('rejects invalid HTTPS origin: $origin', () {
        expect(
          () => AppConfig.resolveBackendBaseUrl(
            isApplePlatform: true,
            appleBackendBaseUrl: origin,
          ),
          throwsA(isA<ArgumentError>()),
        );
      });
    }
  });
}
