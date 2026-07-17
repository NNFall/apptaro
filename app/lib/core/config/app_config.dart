import 'package:flutter/foundation.dart';

class AppConfig {
  static const String appName = 'AI Tarot Reading';
  static const String fixedBackendBaseUrl = 'http://185.171.83.116:8022';
  static const String appleBackendBaseUrl =
      String.fromEnvironment('APPLE_BACKEND_BASE_URL');
  static const String supportMaxUrl =
      'https://max.ru/u/f9LHodD0cOL1NLfuFBoMvvVMSgRmsLKspQSSM1d9_6ZR68W1oT3zfN20xA8';
  static const String healthPath = '/v1/health';
  static const String templatesPath = '/v1/templates/presentation';
  static const String outlinePath = '/v1/presentations/outline';
  static const String outlineRevisePath = '/v1/presentations/outline/revise';
  static const String renderPath = '/v1/presentations/render';
  static const String presentationJobsPath = '/v1/presentations/jobs';
  static const String conversionJobsPath = '/v1/conversions/jobs';
  static const String billingSummaryPath = '/v1/billing/summary';
  static const String billingGooglePlayVerifyPath =
      '/v1/billing/google-play/verify';
  static const String billingPromoRedeemPath = '/v1/billing/promo/redeem';
  static const String androidPackageName = 'com.nexwit.tarot';

  static String presentationJobPath(String jobId) =>
      '$presentationJobsPath/$jobId';

  static String presentationDownloadPath(String jobId, String format) =>
      '${presentationJobPath(jobId)}/download/$format';

  static String conversionJobPath(String jobId) => '$conversionJobsPath/$jobId';

  static String conversionDownloadPath(String jobId) =>
      '${conversionJobPath(jobId)}/download';

  static bool shouldRequireAppleBackend({
    required bool isWeb,
    required TargetPlatform targetPlatform,
  }) =>
      !isWeb && targetPlatform == TargetPlatform.iOS;

  static String resolveBackendBaseUrl({
    required bool isApplePlatform,
    required String appleBackendBaseUrl,
  }) {
    if (!isApplePlatform) {
      return fixedBackendBaseUrl;
    }

    if (appleBackendBaseUrl.isEmpty) {
      throw StateError(
        'APPLE_BACKEND_BASE_URL is required for Apple builds.',
      );
    }

    if (appleBackendBaseUrl != appleBackendBaseUrl.trim() ||
        RegExp(r'\s').hasMatch(appleBackendBaseUrl)) {
      throw _invalidAppleBackendUrl(appleBackendBaseUrl);
    }

    final uri = Uri.tryParse(appleBackendBaseUrl);
    var validPort = true;
    if (uri != null && uri.hasPort) {
      try {
        validPort = uri.port >= 1 && uri.port <= 65535;
      } on FormatException {
        validPort = false;
      }
    }

    if (uri == null ||
        !uri.isAbsolute ||
        uri.scheme != 'https' ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        (uri.path.isNotEmpty && uri.path != '/') ||
        uri.hasQuery ||
        uri.hasFragment ||
        !validPort) {
      throw _invalidAppleBackendUrl(appleBackendBaseUrl);
    }

    return uri.replace(path: '').toString();
  }

  static ArgumentError _invalidAppleBackendUrl(String value) {
    return ArgumentError.value(
      value,
      'APPLE_BACKEND_BASE_URL',
      'Apple builds require exactly one HTTPS origin.',
    );
  }

  static String get defaultBackendBaseUrl => resolveBackendBaseUrl(
        isApplePlatform: shouldRequireAppleBackend(
          isWeb: kIsWeb,
          targetPlatform: defaultTargetPlatform,
        ),
        appleBackendBaseUrl: appleBackendBaseUrl,
      );

  const AppConfig._();
}
