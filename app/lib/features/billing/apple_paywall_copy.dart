import '../../core/config/app_config.dart';

class ApplePaywallCopy {
  static String planLine({
    required bool isRussian,
    required String planKey,
    required bool recurring,
    required String localizedPrice,
    required int includedReadings,
  }) {
    final interval = switch (planKey) {
      'week' => isRussian ? 'неделю' : 'week',
      'month' => isRussian ? 'месяц' : 'month',
      _ => '',
    };
    final intervalCopy = recurring && interval.isNotEmpty ? ' / $interval' : '';
    final readings = isRussian ? 'раскладов' : 'readings';
    final purchaseType = recurring
        ? ''
        : isRussian
            ? ' (разовая покупка)'
            : ' (one-time reading pack)';
    return '$localizedPrice$intervalCopy - $includedReadings $readings$purchaseType';
  }

  static String subscriptionDisclosure({
    required bool isRussian,
    String? privacyPolicyUrl,
  }) {
    final disclosure = isRussian
        ? 'Подписка продлевается автоматически на выбранный период, пока '
            'не будет отменена. Отменить подписку можно в настройках Apple ID '
            'не позднее чем за 24 часа до продления.'
        : 'The subscription automatically renews for the selected period '
            'unless canceled. You can cancel in Apple ID settings at least 24 '
            'hours before renewal.';
    if (privacyPolicyUrl == null) {
      return disclosure;
    }
    return '$disclosure\n${purchaseLegalLinks(
      isRussian: isRussian,
      privacyPolicyUrl: privacyPolicyUrl,
    )}';
  }

  static String purchaseLegalLinks({
    required bool isRussian,
    required String privacyPolicyUrl,
  }) {
    final privacy =
        isRussian ? 'Политика конфиденциальности' : 'Privacy Policy';
    final terms = isRussian ? 'Условия использования' : 'Terms of Use';
    return '[$privacy]($privacyPolicyUrl) | '
        '[$terms](${AppConfig.appleTermsOfUseUrl})';
  }

  static String paywallTitle({
    required bool isRussian,
    required bool offersSubscriptions,
    required bool offersReadingPacks,
  }) {
    if (offersSubscriptions && offersReadingPacks) {
      return isRussian
          ? '**Выбери подписку или пакет раскладов** 👇'
          : '**Choose a subscription or reading pack** 👇';
    }
    if (offersSubscriptions) {
      return isRussian
          ? '**Выбери подписку** 👇'
          : '**Choose a subscription** 👇';
    }
    return isRussian
        ? '**Выбери пакет раскладов** 👇'
        : '**Choose a reading pack** 👇';
  }

  static String subscriptionSectionTitle({required bool isRussian}) => isRussian
      ? '**Автопродлеваемые подписки**'
      : '**Auto-renewing subscriptions**';

  static String readingPackSectionTitle({required bool isRussian}) =>
      isRussian ? '**Разовые пакеты раскладов**' : '**One-time reading packs**';

  static String planButtonLabel({
    required bool isRussian,
    required bool recurring,
    required String planLine,
  }) {
    final action = recurring
        ? (isRussian ? 'Подписаться' : 'Subscribe')
        : (isRussian ? 'Купить пакет' : 'Buy reading pack');
    return '$action • $planLine';
  }

  static String purchaseSuccess({
    required bool isRussian,
    required bool recurring,
    required String planLine,
    required int remainingReadings,
    required String validUntil,
    required String subscriptionDisclosure,
  }) {
    if (!recurring) {
      return isRussian
          ? '**Пакет раскладов добавлен.** ✅\n\n'
              '**Последний пакет раскладов:** $planLine\n'
              '**Всего доступно раскладов:** $remainingReadings'
          : '**Reading pack added.** ✅\n\n'
              '**Latest reading pack:** $planLine\n'
              '**Total readings available:** $remainingReadings';
    }
    return isRussian
        ? '**Подписка оформлена.** ✅\n\n'
            '**Тариф подписки:** $planLine\n'
            '**Статус подписки:** активна\n'
            '**Доступ по подписке до:** $validUntil\n'
            '**Всего доступно раскладов:** $remainingReadings\n\n'
            '$subscriptionDisclosure'
        : '**Subscription activated.** ✅\n\n'
            '**Subscription plan:** $planLine\n'
            '**Subscription status:** Active\n'
            '**Subscription access until:** $validUntil\n'
            '**Total readings available:** $remainingReadings\n\n'
            '$subscriptionDisclosure';
  }

  static String subscriptionStatusUpdating({
    required bool isRussian,
    required String planLine,
    required int remainingReadings,
  }) {
    return isRussian
        ? '**Платёж подтверждён; статус подписки обновляется.** ✅\n\n'
            '**Купленный тариф подписки:** $planLine\n'
            '**Всего доступно раскладов:** $remainingReadings'
        : '**Payment confirmed; subscription status is updating.** ✅\n\n'
            '**Purchased subscription plan:** $planLine\n'
            '**Total readings available:** $remainingReadings';
  }

  static String activeBalance({
    required bool isRussian,
    required bool recurring,
    required bool autoRenew,
    required String planLine,
    required int remainingReadings,
    required String validUntil,
    required String subscriptionDisclosure,
  }) {
    if (!recurring) {
      return isRussian
          ? '**✅ Доступны кредиты на расклады**\n'
              '**Последний пакет раскладов:** $planLine\n'
              '**Всего доступно раскладов:** $remainingReadings'
          : '**✅ Reading credits available**\n'
              '**Latest reading pack:** $planLine\n'
              '**Total readings available:** $remainingReadings';
    }
    if (!autoRenew) {
      return isRussian
          ? '**Статус подписки:** отключена; доступ сохраняется до окончания срока\n'
              '**Тариф подписки:** $planLine\n'
              '**Доступ по подписке до:** $validUntil\n'
              '**Всего доступно раскладов:** $remainingReadings'
          : '**Subscription status:** Canceled; access remains available until expiry\n'
              '**Subscription plan:** $planLine\n'
              '**Subscription access until:** $validUntil\n'
              '**Total readings available:** $remainingReadings';
    }
    return isRussian
        ? '**Статус подписки:** активна\n'
            '**Тариф подписки:** $planLine\n'
            '**Доступ по подписке до:** $validUntil\n'
            '**Всего доступно раскладов:** $remainingReadings\n\n'
            '$subscriptionDisclosure'
        : '**Subscription status:** Active\n'
            '**Subscription plan:** $planLine\n'
            '**Subscription access until:** $validUntil\n'
            '**Total readings available:** $remainingReadings\n\n'
            '$subscriptionDisclosure';
  }

  static String canceledSubscriptionBalance({
    required bool isRussian,
    required String planLine,
    required int remainingReadings,
    required String validUntil,
  }) {
    return isRussian
        ? '**❌ Подписка отключена**\n'
            '**Тариф подписки:** $planLine\n'
            '**Доступ по подписке до:** $validUntil\n'
            '**Всего доступно раскладов:** $remainingReadings'
        : '**❌ Subscription canceled**\n'
            '**Subscription plan:** $planLine\n'
            '**Subscription access until:** $validUntil\n'
            '**Total readings available:** $remainingReadings';
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
