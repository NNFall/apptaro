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
  return _SharedPrefsChatTranscriptStore(
    storageKey: storageKey,
    legacyStorageKeys: legacyStorageKeys,
  );
}

class _SharedPrefsChatTranscriptStore implements ChatTranscriptStore {
  _SharedPrefsChatTranscriptStore({
    required String storageKey,
    required List<String> legacyStorageKeys,
  })  : _storageKey = storageKey,
        _legacyStorageKeys = legacyStorageKeys;

  final String _storageKey;
  final List<String> _legacyStorageKeys;
  final Future<SharedPreferences> _storage = SharedPreferences.getInstance();

  @override
  Future<String?> read() async {
    final storage = await _storage;
    final raw = storage.getString(_storageKey);
    if (raw != null && raw.isNotEmpty) {
      return raw;
    }

    for (final legacyKey in _legacyStorageKeys) {
      final legacy = storage.getString(legacyKey);
      if (legacy != null && legacy.isNotEmpty) {
        return legacy;
      }
    }

    return null;
  }

  @override
  Future<void> write(String value) async {
    final storage = await _storage;
    await storage.setString(_storageKey, value);
    for (final legacyKey in _legacyStorageKeys) {
      await storage.remove(legacyKey);
    }
  }

  @override
  Future<void> remove() async {
    final storage = await _storage;
    await storage.remove(_storageKey);
    for (final legacyKey in _legacyStorageKeys) {
      await storage.remove(legacyKey);
    }
  }
}
