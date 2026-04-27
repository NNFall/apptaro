import 'package:flutter/foundation.dart';

import '../../core/config/app_config.dart';

class BackendConfigRepository extends ChangeNotifier {
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
      _baseUrl = AppConfig.defaultBackendBaseUrl;
    } finally {
      _isLoaded = true;
      _isRestoring = false;
      notifyListeners();
    }
  }

  Future<void> save(String value) async {
    final normalized = normalize(value);
    if (normalized == null || normalized != AppConfig.defaultBackendBaseUrl) {
      throw UnsupportedError(
        'Backend endpoint зафиксирован на сервере AppSlides и не меняется из приложения.',
      );
    }
  }

  Future<void> resetToDefault() async {
    _baseUrl = AppConfig.defaultBackendBaseUrl;
    notifyListeners();
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
