import 'dart:convert';

import 'package:apptaro/core/policies/billing_platform_policy.dart';
import 'package:apptaro/data/repositories/chat_transcript_repository.dart';
import 'package:apptaro/data/storage/chat_transcript_store.dart';
import 'package:apptaro/domain/models/chat_transcript_entry.dart';
import 'package:apptaro/domain/models/saved_file_entry.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const migratedCopyEn =
      'Purchase options were updated. Open Balance to view current App Store offers.';
  const migratedCopyRu =
      'Варианты покупки обновлены. Откройте Баланс, чтобы посмотреть актуальные предложения App Store.';
  final unrelated = _entry(id: 'history', text: 'Your saved tarot reading.');
  final legacyPaywall = _entry(
    id: 'legacy-paywall',
    text: '199 ₽ / week - 15 readings',
    actionKey: 'start_billing_payment',
    payload: const <String, dynamic>{'plan_key': 'week'},
  );
  final legacyProgress = _entry(
    id: 'legacy-progress',
    text: '_Opening Google Play checkout..._',
  );
  final legacyYooKassaProgress = _entry(
    id: 'legacy-yookassa-progress',
    text: '_Opening YooKassa checkout..._',
  );
  final unrelatedWithLegacyAction = ChatTranscriptEntry(
    id: 'mixed-history',
    sender: ChatTranscriptSender.bot,
    text: 'Your saved tarot reading is still available.',
    sentAt: DateTime.utc(2026, 7, 18),
    keyboard: const <List<ChatTranscriptAction>>[
      <ChatTranscriptAction>[
        ChatTranscriptAction(
          label: 'Help',
          actionKey: 'show_help',
          showAsUserMessage: true,
        ),
        ChatTranscriptAction(
          label: 'Old payment',
          actionKey: 'start_billing_payment',
          showAsUserMessage: true,
          payload: <String, dynamic>{'plan_key': 'week'},
        ),
      ],
    ],
  );
  final mixedBotHistory = _entry(
    id: 'mixed-bot-history',
    text: 'Your reading said: "My reading cost 199 ₽ and mentioned a '
        'Google Play payment through YooKassa."',
  );
  const iosPolicy = BillingPlatformPolicy(
    isWeb: false,
    targetPlatform: TargetPlatform.iOS,
  );
  final compliantPaywall = _entry(
    id: 'app-store-paywall',
    text: r'$4.99 / week - 15 readings',
    actionKey: 'start_billing_payment',
    payload: iosPolicy.decorateBillingActionPayload(
      const <String, dynamic>{'plan_key': 'week'},
    ),
  );
  final encoded = jsonEncode(<String, dynamic>{
    'entries': <Map<String, dynamic>>[
      unrelated.toJson(),
      legacyPaywall.toJson(),
      legacyProgress.toJson(),
      legacyYooKassaProgress.toJson(),
      unrelatedWithLegacyAction.toJson(),
      mixedBotHistory.toJson(),
      compliantPaywall.toJson(),
    ],
    'composer_mode': 'idle',
  });

  test('native iOS migration rewrites stale paywalls and preserves history',
      () async {
    final repository = ChatTranscriptRepository(
      store: _MemoryTranscriptStore(encoded),
      billingPlatformPolicy: iosPolicy,
    );
    addTearDown(repository.dispose);

    await repository.restore();

    expect(
      repository.entries.map((entry) => entry.id),
      <String>[
        'history',
        'legacy-paywall',
        'legacy-progress',
        'legacy-yookassa-progress',
        'mixed-history',
        'mixed-bot-history',
        'app-store-paywall',
      ],
    );
    expect(repository.entries[1].text, migratedCopyEn);
    expect(repository.entries[1].keyboard, isEmpty);
    expect(repository.entries[2].text, migratedCopyEn);
    expect(repository.entries[3].text, migratedCopyEn);
    expect(repository.entries[4].text, migratedCopyEn);
    expect(
      repository.entries[4].keyboard.single.map((action) => action.actionKey),
      <String>['show_help'],
    );
    expect(
      repository.entries.last.keyboard.single.single.actionKey,
      'start_billing_payment',
    );
  });

  test('rewrites embedded legacy disclosure when stale action identifies it',
      () async {
    final entry = _entry(
      id: 'embedded-disclosure',
      text: 'Reading note before checkout. Payment is handled securely by '
          'Google Play. By continuing, you agree to old terms. Keep reading.',
      actionKey: 'start_billing_payment',
      payload: const <String, dynamic>{'plan_key': 'week'},
    );
    final repository = _repositoryForEntries(<ChatTranscriptEntry>[entry]);
    addTearDown(repository.dispose);

    await repository.restore();

    expect(repository.entries, hasLength(1));
    expect(repository.entries.single.id, entry.id);
    expect(repository.entries.single.text, migratedCopyEn);
    expect(repository.entries.single.keyboard, isEmpty);
  });

  test(
      'stale-only action rewrite preserves attachments and all record metadata',
      () async {
    final entry = ChatTranscriptEntry(
      id: 'stale-with-metadata',
      sender: ChatTranscriptSender.bot,
      text: '199 ₽ / week - old purchase option',
      sentAt: DateTime.utc(2025, 12, 31, 22, 15),
      keyboard: const <List<ChatTranscriptAction>>[
        <ChatTranscriptAction>[
          ChatTranscriptAction(
            label: 'Old payment',
            actionKey: 'start_billing_payment',
            showAsUserMessage: true,
            payload: <String, dynamic>{'plan_key': 'week'},
          ),
        ],
      ],
      attachments: const <ChatTranscriptAttachment>[
        ChatTranscriptAttachment(
          jobId: 'job-1',
          artifactId: 'artifact-1',
          filename: 'reading.pdf',
          kind: 'pdf',
          mediaType: 'application/pdf',
          remoteUrl: 'https://example.test/reading.pdf',
          sourceType: SavedFileSourceType.presentationArtifact,
          caption: 'Saved reading',
        ),
      ],
      templatePreviewTemplates: const <ChatTranscriptTemplatePreview>[
        ChatTranscriptTemplatePreview(
          id: 7,
          name: 'Moon spread',
          templatePath: '/templates/moon.pptx',
          previewPath: '/previews/moon.png',
          templateAvailable: true,
          previewAvailable: true,
        ),
      ],
      linkPreview: const ChatTranscriptLinkPreview(
        domain: 'example.test',
        title: 'Reading details',
        description: 'Your saved reading',
        url: 'https://example.test/reading',
      ),
    );
    final repository = _repositoryForEntries(<ChatTranscriptEntry>[entry]);
    addTearDown(repository.dispose);

    await repository.restore();

    final restored = repository.entries.single;
    expect(restored.id, entry.id);
    expect(restored.sender, entry.sender);
    expect(restored.sentAt, entry.sentAt);
    expect(restored.text, migratedCopyEn);
    expect(restored.keyboard, isEmpty);
    expect(restored.attachments.single.toJson(),
        entry.attachments.single.toJson());
    expect(
      restored.templatePreviewTemplates.single.toJson(),
      entry.templatePreviewTemplates.single.toJson(),
    );
    expect(restored.linkPreview?.toJson(), entry.linkPreview?.toJson());
  });

  test('rewrites exact Russian standalone process copy with localized text',
      () async {
    final entry = _entry(
      id: 'legacy-progress-ru',
      text: '_Открываю оплату Google Play..._',
    );
    final repository = _repositoryForEntries(<ChatTranscriptEntry>[entry]);
    addTearDown(repository.dispose);

    await repository.restore();

    expect(repository.entries, hasLength(1));
    expect(repository.entries.single.id, entry.id);
    expect(repository.entries.single.text, migratedCopyRu);
  });

  test('native iOS preserves user-authored store and currency text verbatim',
      () async {
    final userEntries = <ChatTranscriptEntry>[
      _entry(
        id: 'user-rub',
        sender: ChatTranscriptSender.user,
        text: 'My reading cost 199 ₽',
        actionKey: 'start_billing_payment',
        payload: const <String, dynamic>{'plan_key': 'week'},
      ),
      _entry(
        id: 'user-stores',
        sender: ChatTranscriptSender.user,
        text: 'I mentioned Google Play and YooKassa in my question.',
      ),
    ];
    final repository = ChatTranscriptRepository(
      store: _MemoryTranscriptStore(
        jsonEncode(<String, dynamic>{
          'entries': userEntries.map((entry) => entry.toJson()).toList(),
          'composer_mode': 'idle',
        }),
      ),
      billingPlatformPolicy: iosPolicy,
    );
    addTearDown(repository.dispose);

    await repository.restore();

    expect(
      repository.entries.map((entry) => entry.toJson()),
      userEntries.map((entry) => entry.toJson()),
    );
  });

  test('native iOS preserves bot subscription and ruble discussion verbatim',
      () async {
    final botEntries = <ChatTranscriptEntry>[
      _entry(
        id: 'bot-rub-en',
        text: 'You asked whether the subscription costs 199 ₽; here is your '
            'reading...',
      ),
      _entry(
        id: 'bot-rub-ru',
        text: 'Вы спросили, стоит ли подписка 199 ₽; вот ваш расклад...',
      ),
    ];
    final repository = ChatTranscriptRepository(
      store: _MemoryTranscriptStore(
        jsonEncode(<String, dynamic>{
          'entries': botEntries.map((entry) => entry.toJson()).toList(),
          'composer_mode': 'idle',
        }),
      ),
      billingPlatformPolicy: iosPolicy,
    );
    addTearDown(repository.dispose);

    await repository.restore();

    expect(
      repository.entries.map((entry) => entry.toJson()),
      botEntries.map((entry) => entry.toJson()),
    );
  });

  test('Android migration preserves legacy paywalls and unrelated history',
      () async {
    final repository = ChatTranscriptRepository(
      store: _MemoryTranscriptStore(encoded),
      billingPlatformPolicy: const BillingPlatformPolicy(
        isWeb: false,
        targetPlatform: TargetPlatform.android,
      ),
    );
    addTearDown(repository.dispose);

    await repository.restore();

    expect(
      repository.entries.map((entry) => entry.id),
      <String>[
        'history',
        'legacy-paywall',
        'legacy-progress',
        'legacy-yookassa-progress',
        'mixed-history',
        'mixed-bot-history',
        'app-store-paywall',
      ],
    );
  });
}

ChatTranscriptEntry _entry({
  required String id,
  required String text,
  ChatTranscriptSender sender = ChatTranscriptSender.bot,
  String? actionKey,
  Map<String, dynamic> payload = const <String, dynamic>{},
}) {
  return ChatTranscriptEntry(
    id: id,
    sender: sender,
    text: text,
    sentAt: DateTime.utc(2026, 7, 18),
    keyboard: actionKey == null
        ? const <List<ChatTranscriptAction>>[]
        : <List<ChatTranscriptAction>>[
            <ChatTranscriptAction>[
              ChatTranscriptAction(
                label: 'Buy',
                actionKey: actionKey,
                showAsUserMessage: true,
                payload: payload,
              ),
            ],
          ],
  );
}

class _MemoryTranscriptStore implements ChatTranscriptStore {
  _MemoryTranscriptStore(this.value);

  String? value;

  @override
  Future<String?> read() async => value;

  @override
  Future<void> remove() async => value = null;

  @override
  Future<void> write(String value) async => this.value = value;
}

ChatTranscriptRepository _repositoryForEntries(
  List<ChatTranscriptEntry> entries,
) {
  return ChatTranscriptRepository(
    store: _MemoryTranscriptStore(
      jsonEncode(<String, dynamic>{
        'entries': entries.map((entry) => entry.toJson()).toList(),
        'composer_mode': 'idle',
      }),
    ),
    billingPlatformPolicy: const BillingPlatformPolicy(
      isWeb: false,
      targetPlatform: TargetPlatform.iOS,
    ),
  );
}
