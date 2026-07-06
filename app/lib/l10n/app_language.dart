import 'package:flutter/widgets.dart';

enum AppLanguage {
  english('en', 'English'),
  russian('ru', 'Русский');

  const AppLanguage(this.code, this.label);

  final String code;
  final String label;

  Locale get locale => Locale(code);

  static AppLanguage fromCode(String? code) {
    final normalized = (code ?? '').toLowerCase().split('-').first;
    return AppLanguage.values.firstWhere(
      (item) => item.code == normalized,
      orElse: () => AppLanguage.english,
    );
  }

  static AppLanguage fromLocale(Locale? locale) {
    return fromCode(locale?.languageCode);
  }
}
