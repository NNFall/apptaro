import 'dart:convert';
import 'dart:io';

import 'package:apptaro/data/repositories/appslides_repository.dart';
import 'package:apptaro/data/repositories/local_history_repository.dart';
import 'package:apptaro/data/repositories/saved_files_repository.dart';
import 'package:apptaro/domain/models/history_entry.dart';
import 'package:apptaro/domain/models/saved_file_entry.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_preferences_platform_interface/in_memory_shared_preferences_async.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_async_platform_interface.dart';

void main() {
  setUp(() {
    SharedPreferencesAsyncPlatform.instance =
        InMemorySharedPreferencesAsync.empty();
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  test('local history migrates legacy appslides key to apptaro key', () async {
    final entry = HistoryEntry(
      id: 'outline-1',
      type: HistoryEntryType.outline,
      status: HistoryEntryStatus.info,
      title: 'Career reading',
      subtitle: 'What should I focus on?',
      details: 'Cards: 3',
      createdAt: DateTime.utc(2026, 1, 1),
      updatedAt: DateTime.utc(2026, 1, 1),
    );
    SharedPreferencesAsyncPlatform.instance =
        InMemorySharedPreferencesAsync.withData(<String, Object>{
      'appslides.history.entries.v1': jsonEncode(<Map<String, dynamic>>[
        entry.toJson(),
      ]),
    });

    final repository = LocalHistoryRepository();
    await repository.restore();

    expect(repository.entries, hasLength(1));
    expect(repository.entries.first.title, 'Career reading');

    final prefs = SharedPreferencesAsync();
    expect(await prefs.getString('apptaro.history.entries.v1'), isNotNull);
    expect(await prefs.getString('appslides.history.entries.v1'), isNull);
  });

  test('saved files migrate legacy appslides key to apptaro key', () async {
    final tempDir =
        await Directory.systemTemp.createTemp('apptaro_saved_file_');
    addTearDown(() async {
      if (await tempDir.exists()) {
        await tempDir.delete(recursive: true);
      }
    });
    final file = File('${tempDir.path}${Platform.pathSeparator}reading.txt');
    await file.writeAsString('reading');

    final entry = SavedFileEntry(
      id: 'saved-artifact-1',
      sourceType: SavedFileSourceType.presentationArtifact,
      jobId: 'job-1',
      artifactId: 'artifact-1',
      kind: 'txt',
      filename: 'reading.txt',
      mediaType: 'text/plain',
      remoteUrl: 'http://example.test/reading.txt',
      localPath: file.path,
      sizeBytes: 7,
      savedAt: DateTime.utc(2026, 1, 1),
    );
    SharedPreferencesAsyncPlatform.instance =
        InMemorySharedPreferencesAsync.withData(<String, Object>{
      'appslides.saved_files.entries.v1': jsonEncode(<Map<String, dynamic>>[
        entry.toJson(),
      ]),
    });

    final appRepository = AppSlidesRepository();
    addTearDown(appRepository.dispose);
    final repository = SavedFilesRepository(repository: appRepository);
    await repository.restore();

    expect(repository.entries, hasLength(1));
    expect(repository.entries.first.filename, 'reading.txt');

    final prefs = SharedPreferencesAsync();
    expect(await prefs.getString('apptaro.saved_files.entries.v1'), isNotNull);
    expect(await prefs.getString('appslides.saved_files.entries.v1'), isNull);
  });
}
