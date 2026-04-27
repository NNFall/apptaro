import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/config/app_config.dart';

class BackendConfigRepository extends ChangeNotifier {
  static const String _storageKey = 'appslides.backend.base_url.v1';

  final SharedPreferencesAsync _storage = SharedPreferencesAsync();

  String _baseUrl = AppConfig.defaultBackendBaseUrl;
  bool _isLoaded = false;
  bool _isRestoring = false;

  String get baseUrl => _baseUrl;
  bool get isLoaded => _isLoaded;
  bool get isRestoring => _isRestoring;

  Future<void> restore() async {
    if (_isLoaded || _isRestoring) {
      return;
    }

    _isRestoring = true;
    notifyListeners();

    try {
      final stored = await _storage.getString(_storageKey);
      final normalized = normalize(stored);
      if (normalized != null) {
        _baseUrl = normalized;
      }
    } finally {
      _isLoaded = true;
      _isRestoring = false;
      notifyListeners();
    }
  }

  Future<void> save(String value) async {
    final normalized = normalize(value);
    if (normalized == null) {
      throw const FormatException('Укажи корректный URL вида http://host:8000');
    }

    _baseUrl = normalized;
    notifyListeners();
    await _storage.setString(_storageKey, normalized);
  }

  Future<void> resetToDefault() async {
    _baseUrl = AppConfig.defaultBackendBaseUrl;
    notifyListeners();
    await _storage.remove(_storageKey);
  }

  static String? normalize(String? value) {
    final trimmed = value?.trim();
    if (trimmed == null || trimmed.isEmpty) {
      return null;
    }

    final parsed = Uri.tryParse(trimmed);
    if (parsed == null || !parsed.hasScheme || parsed.host.isEmpty) {
      return null;
    }

    final buffer = StringBuffer()
      ..write('${parsed.scheme}://${parsed.host}');
    if (parsed.hasPort) {
      buffer.write(':${parsed.port}');
    }
    return buffer.toString();
  }
}
