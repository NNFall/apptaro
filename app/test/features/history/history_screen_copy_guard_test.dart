import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('history screen copy stays tarot-specific', () {
    final source =
        File('lib/features/history/history_screen.dart').readAsStringSync();

    expect(source, contains('Saved tarot images and text readings'));
    expect(source, contains('Save a tarot reading result'));
    expect(source, contains('tarot reading'));
    expect(source, isNot(contains('PPTX')));
    expect(source, isNot(contains('DOCX')));
    expect(source, isNot(contains('conversion result')));
    expect(source, isNot(contains('conversion job')));
    expect(source, isNot(contains("=> 'presentation'")));
    expect(source, isNot(contains("=> 'conversion'")));
  });
}
