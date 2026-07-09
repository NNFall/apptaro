import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('chat screen does not expose legacy presentation file labels', () {
    final source =
        File('lib/features/chat/chat_screen.dart').readAsStringSync();

    expect(source, contains('Google Play version'));
    expect(source, isNot(contains("return isRussian ? 'Файл (PPTX)'")));
    expect(source, isNot(contains("return isRussian ? 'Документ (DOCX)'")));
    expect(source, isNot(contains("'File (PPTX)'")));
    expect(source, isNot(contains("'Document (DOCX)'")));
    expect(source, isNot(contains('callback = () => _startConversionFlow')));
    expect(source, isNot(contains('ConverterController')));
    expect(source, isNot(contains('_handleConverterUpdates')));
    expect(source, isNot(contains('File conversion is queued')));
    expect(source, isNot(contains('Conversion result')));
  });

  test('language switch is a header modal, not a main chat button', () {
    final source =
        File('lib/features/chat/chat_screen.dart').readAsStringSync();

    expect(source, contains('onLanguagePressed: _showLanguageMenu'));
    expect(source, contains('showModalBottomSheet<void>'));
    expect(source, contains('class _LanguageTile'));
    expect(source, isNot(contains("actionKey: 'show_language_menu'")));
    expect(source, isNot(contains("case 'show_language_menu'")));
    expect(source, isNot(contains("case 'set_language'")));
    expect(source, isNot(contains("case 'show_settings'")));
    expect(source, isNot(contains("case 'show_history'")));
    expect(source, isNot(contains("case 'show_files'")));
  });
}
