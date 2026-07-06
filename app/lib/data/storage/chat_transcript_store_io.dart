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
  required List<String> legacyStorageKeys,
}) {
  return _IoChatTranscriptStore(
    storageKey: storageKey,
    legacyStorageKeys: legacyStorageKeys,
  );
}

class _IoChatTranscriptStore implements ChatTranscriptStore {
  _IoChatTranscriptStore({
    required String storageKey,
    required List<String> legacyStorageKeys,
  })  : _storageKey = storageKey,
        _legacyStorageKeys = legacyStorageKeys;

  static const String _directoryName = 'apptaro_state';
  static const String _legacyDirectoryName = 'appslides_state';
  static const String _filename = 'chat_transcript.json';

  final String _storageKey;
  final List<String> _legacyStorageKeys;
  final Future<SharedPreferences> _prefs = SharedPreferences.getInstance();
  Future<File>? _fileFuture;
  Future<File>? _legacyFileFuture;

  @override
  Future<String?> read() async {
    final file = await _resolveFile();
    if (file.existsSync()) {
      final raw = file.readAsStringSync();
      if (raw.isNotEmpty) {
        return raw;
      }
    }

    final legacyFile = await _resolveLegacyFile();
    if (legacyFile.existsSync()) {
      final raw = legacyFile.readAsStringSync();
      if (raw.isNotEmpty) {
        try {
          file.parent.createSync(recursive: true);
          file.writeAsStringSync(raw, flush: true);
          legacyFile.deleteSync();
        } catch (_) {}
        return raw;
      }
    }

    final prefs = await _prefs;
    final raw = prefs.getString(_storageKey);
    if (raw != null && raw.isNotEmpty) {
      return raw;
    }

    for (final legacyKey in _legacyStorageKeys) {
      final legacy = prefs.getString(legacyKey);
      if (legacy != null && legacy.isNotEmpty) {
        return legacy;
      }
    }

    return null;
  }

  @override
  Future<void> write(String value) async {
    final prefs = await _prefs;
    for (final legacyKey in _legacyStorageKeys) {
      await prefs.remove(legacyKey);
    }
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
    final legacyFile = await _resolveLegacyFile();
    if (legacyFile.existsSync()) {
      legacyFile.deleteSync();
    }

    final prefs = await _prefs;
    await prefs.remove(_storageKey);
    for (final legacyKey in _legacyStorageKeys) {
      await prefs.remove(legacyKey);
    }
  }

  Future<File> _resolveFile() async {
    if (_fileFuture != null) {
      return _fileFuture!;
    }
    _fileFuture = _resolveFileImpl();
    return _fileFuture!;
  }

  Future<File> _resolveFileImpl() async {
    return _resolveFileInDirectory(_directoryName);
  }

  Future<File> _resolveLegacyFile() async {
    if (_legacyFileFuture != null) {
      return _legacyFileFuture!;
    }
    _legacyFileFuture = _resolveFileInDirectory(_legacyDirectoryName);
    return _legacyFileFuture!;
  }

  Future<File> _resolveFileInDirectory(String directoryName) async {
    final baseDir = Platform.isAndroid
        ? await getExternalStorageDirectory() ??
            await getApplicationDocumentsDirectory()
        : await getApplicationDocumentsDirectory();
    final targetDir = Directory(
      '${baseDir.path}${Platform.pathSeparator}$directoryName',
    );
    return File('${targetDir.path}${Platform.pathSeparator}$_filename');
  }
}
