import 'dart:ui' as ui;

import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../l10n/app_language.dart';

class LanguageRepository extends ChangeNotifier {
  static const String _storageKey = 'apptaro.language.v1';

  AppLanguage _current = AppLanguage.english;

  AppLanguage get current => _current;

  Future<void> restore({Locale? deviceLocale}) async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(_storageKey);
    _current = stored == null
        ? AppLanguage.fromLocale(
            deviceLocale ?? ui.PlatformDispatcher.instance.locale)
        : AppLanguage.fromCode(stored);
    notifyListeners();
  }

  Future<void> setLanguage(AppLanguage language) async {
    if (_current == language) {
      return;
    }

    _current = language;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_storageKey, language.code);
    notifyListeners();
  }
}
