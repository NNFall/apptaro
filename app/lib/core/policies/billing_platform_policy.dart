import 'package:flutter/foundation.dart';

import '../../domain/models/chat_transcript_entry.dart';
import '../config/app_config.dart';

enum PromoCommandOutcome { unsupported, usage, redeemed }

class AppleLegalLinks {
  const AppleLegalLinks({
    required this.privacyPolicy,
    required this.termsOfUse,
  });

  final Uri privacyPolicy;
  final Uri termsOfUse;
}

class BillingPlatformPolicy {
  const BillingPlatformPolicy({
    required this.isWeb,
    required this.targetPlatform,
  });

  factory BillingPlatformPolicy.current() => BillingPlatformPolicy(
        isWeb: kIsWeb,
        targetPlatform: defaultTargetPlatform,
      );

  static const String _storefrontKey = 'billing_storefront';
  static const String _paywallVersionKey = 'paywall_version';
  static const String _appleStorefront = 'app_store';
  static const int _currentPaywallVersion = 1;
  static const Set<String> _versionedBillingActions = <String>{
    'show_plan_options',
    'start_billing_payment',
  };

  final bool isWeb;
  final TargetPlatform targetPlatform;

  bool get isNativeIos => !isWeb && targetPlatform == TargetPlatform.iOS;
  bool get restorePurchasesVisible => isNativeIos;
  bool get promoSupported => !isNativeIos;

  AppleLegalLinks? appleLegalLinks(String privacyPolicyUrl) {
    if (!isNativeIos) {
      return null;
    }
    return AppleLegalLinks(
      privacyPolicy: AppConfig.resolveApplePrivacyPolicyUrl(privacyPolicyUrl),
      termsOfUse: Uri.parse(AppConfig.appleTermsOfUseUrl),
    );
  }

  Future<PromoCommandOutcome> executePromoCommand({
    required String code,
    required Future<void> Function(String code) redeem,
  }) async {
    if (!promoSupported) {
      return PromoCommandOutcome.unsupported;
    }
    final normalized = code.trim();
    if (normalized.isEmpty) {
      return PromoCommandOutcome.usage;
    }
    await redeem(normalized);
    return PromoCommandOutcome.redeemed;
  }

  Map<String, dynamic> decorateBillingActionPayload(
    Map<String, dynamic> payload,
  ) {
    if (!isNativeIos) {
      return Map<String, dynamic>.of(payload);
    }
    return <String, dynamic>{
      ...payload,
      _storefrontKey: _appleStorefront,
      _paywallVersionKey: _currentPaywallVersion,
    };
  }

  bool allowsPersistedAction({
    required String actionKey,
    required Map<String, dynamic> payload,
  }) {
    if (!isNativeIos || !_versionedBillingActions.contains(actionKey)) {
      return true;
    }
    return payload[_storefrontKey] == _appleStorefront &&
        payload[_paywallVersionKey] == _currentPaywallVersion;
  }

  List<ChatTranscriptEntry> sanitizeTranscriptEntries(
    Iterable<ChatTranscriptEntry> entries,
  ) {
    if (!isNativeIos) {
      return List<ChatTranscriptEntry>.of(entries);
    }

    final sanitized = <ChatTranscriptEntry>[];
    for (final entry in entries) {
      if (entry.sender != ChatTranscriptSender.bot) {
        sanitized.add(entry);
        continue;
      }
      final deniedKeys = <String>{
        for (final row in entry.keyboard)
          for (final action in row)
            if (!allowsPersistedAction(
              actionKey: action.actionKey,
              payload: action.payload,
            ))
              action.actionKey,
      };
      if (deniedKeys.isNotEmpty) {
        if (!_isLegacyBotBillingCopy(entry.text)) {
          sanitized.add(entry.withoutActionKeys(deniedKeys));
        }
        continue;
      }
      if (!_isLegacyBotBillingCopy(entry.text)) {
        sanitized.add(entry);
      }
    }
    return sanitized;
  }

  bool _isCompliantApplePaywallCopy(String text) {
    final normalized = text.toLowerCase();
    return normalized.contains(AppConfig.appleTermsOfUseUrl.toLowerCase()) ||
        normalized.contains('automatically renews') ||
        normalized.contains('продлевается автоматически');
  }

  bool _isLegacyBotBillingCopy(String text) {
    final normalized = text.toLowerCase();
    if (normalized.contains('opening google play checkout') ||
        normalized.contains('открываю оплату google play') ||
        normalized.contains('payment is handled securely by google play') ||
        normalized.contains('opening yookassa checkout') ||
        normalized.contains('opening юkassa checkout') ||
        normalized.contains('открываю оплату yookassa') ||
        normalized.contains('открываю оплату юkassa') ||
        normalized.contains('payment is handled securely by yookassa') ||
        normalized.contains('payment is handled securely by юkassa')) {
      return true;
    }
    final isRubSubscription = text.contains('₽') &&
        (normalized.contains('subscription') ||
            normalized.contains('подписк') ||
            RegExp(
              r'₽\s*/\s*(week|month|недел|месяц)',
              caseSensitive: false,
            ).hasMatch(text));
    return isRubSubscription && !_isCompliantApplePaywallCopy(text);
  }
}
