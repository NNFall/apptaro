import '../../core/config/app_config.dart';

class ApplePaywallCopy {
  static String planLine({
    required bool isRussian,
    required String planKey,
    required String localizedPrice,
    required int includedReadings,
  }) {
    final interval = switch (planKey) {
      'week' => isRussian ? 'неделю' : 'week',
      'month' => isRussian ? 'месяц' : 'month',
      _ => '',
    };
    final intervalCopy = interval.isEmpty ? '' : ' / $interval';
    final readings = isRussian ? 'раскладов' : 'readings';
    return '$localizedPrice$intervalCopy - $includedReadings $readings';
  }

  static String subscriptionDisclosure({
    required bool isRussian,
    required String privacyPolicyUrl,
  }) {
    final privacy =
        isRussian ? 'Политика конфиденциальности' : 'Privacy Policy';
    final terms = isRussian ? 'Условия использования' : 'Terms of Use';
    final links = '[$privacy]($privacyPolicyUrl) | '
        '[$terms](${AppConfig.appleTermsOfUseUrl})';
    if (isRussian) {
      return 'Подписка продлевается автоматически на выбранный период, пока '
          'не будет отменена. Отменить подписку можно в настройках Apple ID '
          'не позднее чем за 24 часа до продления.\n$links';
    }
    return 'The subscription automatically renews for the selected period '
        'unless canceled. You can cancel in Apple ID settings at least 24 '
        'hours before renewal.\n$links';
  }

  static String checkoutProgress({required bool isRussian}) => isRussian
      ? '_Открываю оплату в App Store..._'
      : '_Opening App Store checkout..._';

  static String restoreProgress({required bool isRussian}) => isRussian
      ? '_Восстанавливаю покупки из App Store..._'
      : '_Restoring purchases from the App Store..._';

  static String restoreSuccess({required bool isRussian}) => isRussian
      ? 'Покупки успешно восстановлены.'
      : 'Purchases restored successfully.';

  static String restoreNoPurchases({required bool isRussian}) => isRussian
      ? 'Покупки для восстановления не найдены.'
      : 'No purchases were found to restore.';

  static String restorePartial({
    required bool isRussian,
    required int failedCount,
  }) =>
      isRussian
          ? 'Покупки восстановлены частично. Не удалось восстановить: '
              '$failedCount.'
          : 'Purchases were partially restored. $failedCount purchases could '
              'not be restored.';

  static String restoreError({
    required bool isRussian,
    required String error,
  }) =>
      isRussian
          ? 'Не удалось восстановить покупки: $error'
          : 'Could not restore purchases: $error';

  static String priceUnavailable({required bool isRussian}) => isRussian
      ? 'Цена временно недоступна в App Store'
      : 'Price is temporarily unavailable from the App Store';

  static String privacyUnavailable({required bool isRussian}) => isRussian
      ? 'Покупки недоступны: ссылка на политику конфиденциальности не настроена.'
      : 'Purchases are unavailable because the Privacy Policy link is not configured.';

  const ApplePaywallCopy._();
}
