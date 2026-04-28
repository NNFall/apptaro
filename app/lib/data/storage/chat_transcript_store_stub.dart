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
  return _SharedPrefsChatTranscriptStore(
    storageKey: storageKey,
    legacyStorageKey: legacyStorageKey,
  );
}

class _SharedPrefsChatTranscriptStore implements ChatTranscriptStore {
  _SharedPrefsChatTranscriptStore({
    required String storageKey,
    required String legacyStorageKey,
  })  : _storageKey = storageKey,
        _legacyStorageKey = legacyStorageKey;

  final String _storageKey;
  final String _legacyStorageKey;
  final SharedPreferencesAsync _storage = SharedPreferencesAsync();

  @override
  Future<String?> read() async {
    final raw = await _storage.getString(_storageKey);
    if (raw != null && raw.isNotEmpty) {
      return raw;
    }

    final legacy = await _storage.getString(_legacyStorageKey);
    if (legacy != null && legacy.isNotEmpty) {
      return legacy;
    }

    return null;
  }

  @override
  Future<void> write(String value) async {
    await _storage.setString(_storageKey, value);
    await _storage.remove(_legacyStorageKey);
  }

  @override
  Future<void> remove() async {
    await _storage.remove(_storageKey);
    await _storage.remove(_legacyStorageKey);
  }
}
