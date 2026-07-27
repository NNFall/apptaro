import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('image previews prefer the locally cached artifact', () {
    final source =
        File('lib/features/chat/chat_screen.dart').readAsStringSync();

    expect(
      source,
      matches(
        RegExp(
          r'savedEntry:\s*savedFilesRepository\.findByArtifactId\(',
        ),
      ),
    );
    expect(source, contains('localImageProvider(savedEntry?.localPath)'));
  });

  test('network image previews retry transient loading failures', () {
    final source =
        File('lib/features/chat/chat_screen.dart').readAsStringSync();

    expect(source, contains('_maxImageLoadAttempts = 3'));
    expect(source, contains('_scheduleRetry()'));
  });
}
