import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ClientSessionRepository extends ChangeNotifier {
  static const String _storageKey = 'appslides.client_id.v1';

  final SharedPreferencesAsync _storage = SharedPreferencesAsync();
  final Random _random = Random.secure();

  String? _clientId;
  bool _isLoaded = false;
  bool _isRestoring = false;

  String? get clientId => _clientId;
  bool get isLoaded => _isLoaded;

  Future<void> restore() async {
    if (_isLoaded || _isRestoring) {
      return;
    }

    _isRestoring = true;
    notifyListeners();

    try {
      final stored = await _storage.getString(_storageKey);
      _clientId = _normalize(stored) ?? _generateClientId();
      await _storage.setString(_storageKey, _clientId!);
    } finally {
      _isLoaded = true;
      _isRestoring = false;
      notifyListeners();
    }
  }

  Future<String> getOrCreateClientId() async {
    if (!_isLoaded) {
      await restore();
    }
    final value = _clientId ?? _generateClientId();
    _clientId = value;
    return value;
  }

  String _generateClientId() {
    final timestamp = DateTime.now().millisecondsSinceEpoch.toRadixString(36);
    final buffer = StringBuffer('appslides_')..write(timestamp)..write('_');
    for (var index = 0; index < 18; index++) {
      buffer.write(_random.nextInt(16).toRadixString(16));
    }
    return buffer.toString();
  }

  String? _normalize(String? value) {
    final trimmed = value?.trim();
    if (trimmed == null || trimmed.length < 8) {
      return null;
    }
    return trimmed;
  }
}
