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
  final Future<SharedPreferences> _prefs = SharedPreferences.getInstance();
  Future<File>? _fileFuture;

  @override
  Future<String?> read() async {
    final file = await _resolveFile();
    if (file.existsSync()) {
      final raw = file.readAsStringSync();
      if (raw.isNotEmpty) {
        return raw;
      }
    }

    final prefs = await _prefs;
    final raw = prefs.getString(_storageKey);
    if (raw != null && raw.isNotEmpty) {
      return raw;
    }

    final legacy = prefs.getString(_legacyStorageKey);
    if (legacy != null && legacy.isNotEmpty) {
      return legacy;
    }

    return null;
  }

  @override
  Future<void> write(String value) async {
    final prefs = await _prefs;
    await prefs.remove(_legacyStorageKey);
    await prefs.setString(_storageKey, value);

    try {
      final file = await _resolveFile();
      file.parent.createSync(recursive: true);
      file.writeAsStringSync(value, flush: true);
    } catch (_) {}
  }

  @override
  Future<void> remove() async {
    final file = await _resolveFile();
    if (file.existsSync()) {
      file.deleteSync();
    }

    final prefs = await _prefs;
    await prefs.remove(_storageKey);
    await prefs.remove(_legacyStorageKey);
  }

  Future<File> _resolveFile() async {
    if (_fileFuture != null) {
      return _fileFuture!;
    }
    _fileFuture = _resolveFileImpl();
    return _fileFuture!;
  }

  Future<File> _resolveFileImpl() async {
    final baseDir = Platform.isAndroid
        ? await getExternalStorageDirectory() ??
            await getApplicationDocumentsDirectory()
        : await getApplicationDocumentsDirectory();
    final targetDir = Directory(
      '${baseDir.path}${Platform.pathSeparator}$_directoryName',
    );
    return File('${targetDir.path}${Platform.pathSeparator}$_filename');
  }
}
