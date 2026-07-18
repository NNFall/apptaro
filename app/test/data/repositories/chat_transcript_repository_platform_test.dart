import 'dart:convert';

import 'package:apptaro/core/policies/billing_platform_policy.dart';
import 'package:apptaro/data/repositories/chat_transcript_repository.dart';
import 'package:apptaro/data/storage/chat_transcript_store.dart';
import 'package:apptaro/domain/models/chat_transcript_entry.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
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
      unrelatedWithLegacyAction.toJson(),
      compliantPaywall.toJson(),
    ],
    'composer_mode': 'idle',
  });

  test('native iOS migration removes stale paywalls and preserves history',
      () async {
    final repository = ChatTranscriptRepository(
      store: _MemoryTranscriptStore(encoded),
      billingPlatformPolicy: iosPolicy,
    );
    addTearDown(repository.dispose);

    await repository.restore();

    expect(
      repository.entries.map((entry) => entry.id),
      <String>['history', 'mixed-history', 'app-store-paywall'],
    );
    expect(
      repository.entries[1].keyboard.single.map((action) => action.actionKey),
      <String>['show_help'],
    );
    expect(
      repository.entries.last.keyboard.single.single.actionKey,
      'start_billing_payment',
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
        'mixed-history',
        'app-store-paywall',
      ],
    );
  });
}

ChatTranscriptEntry _entry({
  required String id,
  required String text,
  String? actionKey,
  Map<String, dynamic> payload = const <String, dynamic>{},
}) {
  return ChatTranscriptEntry(
    id: id,
    sender: ChatTranscriptSender.bot,
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
