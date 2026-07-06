import 'package:apptaro/l10n/app_language.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('resolves supported locale code from full device locale', () {
    expect(
        AppLanguage.fromLocale(const Locale('ru', 'RU')), AppLanguage.russian);
    expect(
        AppLanguage.fromLocale(const Locale('en', 'US')), AppLanguage.english);
  });

  test('falls back to English for unsupported locale code', () {
    expect(AppLanguage.fromCode('de'), AppLanguage.english);
    expect(
        AppLanguage.fromLocale(const Locale('es', 'ES')), AppLanguage.english);
  });
}
