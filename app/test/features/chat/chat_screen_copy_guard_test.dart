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
  });
}
