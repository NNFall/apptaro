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
  final Future<SharedPreferences> _storage = SharedPreferences.getInstance();

  @override
  Future<String?> read() async {
    final storage = await _storage;
    final raw = storage.getString(_storageKey);
    if (raw != null && raw.isNotEmpty) {
      return raw;
    }

    final legacy = storage.getString(_legacyStorageKey);
    if (legacy != null && legacy.isNotEmpty) {
      return legacy;
    }

    return null;
  }

  @override
  Future<void> write(String value) async {
    final storage = await _storage;
    await storage.setString(_storageKey, value);
    await storage.remove(_legacyStorageKey);
  }

  @override
  Future<void> remove() async {
    final storage = await _storage;
    await storage.remove(_storageKey);
    await storage.remove(_legacyStorageKey);
  }
}
