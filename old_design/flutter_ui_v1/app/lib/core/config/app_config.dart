import 'package:flutter/foundation.dart';

class AppConfig {
  static const String appName = 'AppSlides';
  static const String healthPath = '/v1/health';
  static const String templatesPath = '/v1/templates/presentation';
  static const String outlinePath = '/v1/presentations/outline';
  static const String outlineRevisePath = '/v1/presentations/outline/revise';
  static const String renderPath = '/v1/presentations/render';
  static const String presentationJobsPath = '/v1/presentations/jobs';
  static const String conversionJobsPath = '/v1/conversions/jobs';

  static String presentationJobPath(String jobId) => '$presentationJobsPath/$jobId';

  static String presentationDownloadPath(String jobId, String format) =>
      '${presentationJobPath(jobId)}/download/$format';

  static String conversionJobPath(String jobId) => '$conversionJobsPath/$jobId';

  static String conversionDownloadPath(String jobId) =>
      '${conversionJobPath(jobId)}/download';

  static String get defaultBackendBaseUrl {
    const fromEnv = String.fromEnvironment('APPSLIDES_BACKEND_URL');
    if (fromEnv.isNotEmpty) {
      return fromEnv;
    }
    if (kIsWeb) {
      return 'http://localhost:8000';
    }
    return switch (defaultTargetPlatform) {
      TargetPlatform.android => 'http://10.0.2.2:8000',
      _ => 'http://localhost:8000',
    };
  }

  const AppConfig._();
}
