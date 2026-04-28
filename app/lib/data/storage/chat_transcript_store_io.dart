import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

abstract class ChatTranscriptStore {
  Future<String?> read();
  Future<void> write(String value);
  Future<void> remove();
}

ChatTranscriptStore createChatTranscriptStore({
  required String storageKey,
  required String legacyStorageKey,
}) {
  return _IoChatTranscriptStore(
    storageKey: storageKey,
    legacyStorageKey: legacyStorageKey,
  );
}

class _IoChatTranscriptStore implements ChatTranscriptStore {
  _IoChatTranscriptStore({
    required String storageKey,
    required String legacyStorageKey,
  })  : _storageKey = storageKey,
        _legacyStorageKey = legacyStorageKey;

  static const String _directoryName = 'appslides_state';
  static const String _filename = 'chat_transcript.json';

  final String _storageKey;
  final String _legacyStorageKey;
  final SharedPreferencesAsync _prefs = SharedPreferencesAsync();

  @override
  Future<String?> read() async {
    final file = await _resolveFile();
    if (await file.exists()) {
      final raw = await file.readAsString();
      if (raw.isNotEmpty) {
        return raw;
      }
    }

    final raw = await _prefs.getString(_storageKey);
    if (raw != null && raw.isNotEmpty) {
      return raw;
    }

    final legacy = await _prefs.getString(_legacyStorageKey);
    if (legacy != null && legacy.isNotEmpty) {
      return legacy;
    }

    return null;
  }

  @override
  Future<void> write(String value) async {
    final file = await _resolveFile();
    await file.parent.create(recursive: true);
    await file.writeAsString(value, flush: true);
    await _prefs.remove(_storageKey);
    await _prefs.remove(_legacyStorageKey);
  }

  @override
  Future<void> remove() async {
    final file = await _resolveFile();
    if (await file.exists()) {
      await file.delete();
    }
    await _prefs.remove(_storageKey);
    await _prefs.remove(_legacyStorageKey);
  }

  Future<File> _resolveFile() async {
    final documentsDir = await getApplicationDocumentsDirectory();
    final targetDir = Directory(
      '${documentsDir.path}${Platform.pathSeparator}$_directoryName',
    );
    return File('${targetDir.path}${Platform.pathSeparator}$_filename');
  }
}
