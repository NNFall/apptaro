class AppConfig {
  static const String appName = 'Таро Расклад';
  static const String fixedBackendBaseUrl = 'http://185.171.83.116:8010';
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
  static const String billingPaymentsPath = '/v1/billing/payments';
  static const String billingPromoRedeemPath = '/v1/billing/promo/redeem';
  static const String billingCancelSubscriptionPath =
      '/v1/billing/subscription/cancel';

  static String presentationJobPath(String jobId) =>
      '$presentationJobsPath/$jobId';

  static String presentationDownloadPath(String jobId, String format) =>
      '${presentationJobPath(jobId)}/download/$format';

  static String conversionJobPath(String jobId) => '$conversionJobsPath/$jobId';

  static String conversionDownloadPath(String jobId) =>
      '${conversionJobPath(jobId)}/download';

  static String billingPaymentPath(String paymentId) =>
      '$billingPaymentsPath/$paymentId';

  static String get defaultBackendBaseUrl => fixedBackendBaseUrl;

  const AppConfig._();
}
