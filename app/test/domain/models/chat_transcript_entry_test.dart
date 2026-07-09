import 'package:flutter_test/flutter_test.dart';
import 'package:apptaro/domain/models/chat_transcript_entry.dart';

void main() {
  test('removes obsolete chat action keys while preserving valid actions', () {
    final entry = ChatTranscriptEntry(
      id: 'message-1',
      sender: ChatTranscriptSender.bot,
      text: 'Menu',
      sentAt: DateTime.utc(2026, 7, 9),
      keyboard: const <List<ChatTranscriptAction>>[
        <ChatTranscriptAction>[
          ChatTranscriptAction(
            label: 'Language',
            actionKey: 'show_language_menu',
            showAsUserMessage: false,
          ),
          ChatTranscriptAction(
            label: 'Ask',
            actionKey: 'begin_presentation_topic',
            showAsUserMessage: true,
          ),
        ],
        <ChatTranscriptAction>[
          ChatTranscriptAction(
            label: 'Settings',
            actionKey: 'show_settings',
            showAsUserMessage: true,
          ),
          ChatTranscriptAction(
            label: 'History',
            actionKey: 'show_history',
            showAsUserMessage: true,
          ),
          ChatTranscriptAction(
            label: 'Files',
            actionKey: 'show_files',
            showAsUserMessage: true,
          ),
        ],
      ],
    );

    final sanitized = entry.withoutActionKeys(const <String>{
      'show_language_menu',
      'set_language',
      'show_settings',
      'show_history',
      'show_files',
    });

    expect(sanitized.keyboard, hasLength(1));
    expect(sanitized.keyboard.single, hasLength(1));
    expect(sanitized.keyboard.single.single.actionKey, 'begin_presentation_topic');
  });
}
