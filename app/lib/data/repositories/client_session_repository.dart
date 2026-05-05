import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ClientSessionRepository extends ChangeNotifier {
  static const String _storageKey = 'apptaro.client_id.v1';
  static const List<String> _legacyStorageKeys = <String>[
    'appslides.client_id.v1',
  ];

  final SharedPreferencesAsync _storage = SharedPreferencesAsync();
  final Random _random = Random.secure();

  String? _clientId;
  bool _isLoaded = false;
  Future<void>? _restoreFuture;

  String? get clientId => _clientId;
  bool get isLoaded => _isLoaded;

  Future<void> restore() async {
    if (_isLoaded) {
      return;
    }
    if (_restoreFuture != null) {
      return _restoreFuture;
    }

    final future = _restoreInternal();
    _restoreFuture = future;
    try {
      await future;
    } finally {
      if (identical(_restoreFuture, future)) {
        _restoreFuture = null;
      }
    }
  }

  Future<String> getOrCreateClientId() async {
    if (!_isLoaded) {
      await restore();
    }
    if (_clientId == null) {
      _clientId = _generateClientId();
      await _storage.setString(_storageKey, _clientId!);
    }
    return _clientId!;
  }

  Future<void> _restoreInternal() async {
    notifyListeners();
    try {
      final stored = await _readStoredClientId();
      _clientId = _normalize(stored) ?? _generateClientId();
      await _storage.setString(_storageKey, _clientId!);
      for (final legacyKey in _legacyStorageKeys) {
        await _storage.remove(legacyKey);
      }
    } finally {
      _isLoaded = true;
      notifyListeners();
    }
  }

  Future<String?> _readStoredClientId() async {
    final direct = await _storage.getString(_storageKey);
    if (direct != null && direct.trim().isNotEmpty) {
      return direct;
    }

    for (final legacyKey in _legacyStorageKeys) {
      final legacy = await _storage.getString(legacyKey);
      if (legacy != null && legacy.trim().isNotEmpty) {
        return legacy;
      }
    }
    return null;
  }

  String _generateClientId() {
    final timestamp = DateTime.now().millisecondsSinceEpoch.toRadixString(36);
    final buffer = StringBuffer('apptaro_')..write(timestamp)..write('_');
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
    if (trimmed.startsWith('apptaro_')) {
      return trimmed;
    }
    if (trimmed.startsWith('appslides_')) {
      final suffix = trimmed.substring('appslides_'.length);
      return suffix.isEmpty ? null : 'apptaro_$suffix';
    }
    return 'apptaro_$trimmed';
  }
}
