import 'package:apptaro/data/repositories/language_repository.dart';
import 'package:apptaro/l10n/app_language.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  test('uses device locale when user has not selected language', () async {
    final repository = LanguageRepository();

    await repository.restore(deviceLocale: const Locale('ru', 'RU'));

    expect(repository.current, AppLanguage.russian);
  });

  test('persists manually selected language over device locale', () async {
    final repository = LanguageRepository();
    await repository.restore(deviceLocale: const Locale('ru', 'RU'));

    await repository.setLanguage(AppLanguage.english);

    final restored = LanguageRepository();
    await restored.restore(deviceLocale: const Locale('ru', 'RU'));

    expect(restored.current, AppLanguage.english);
  });
}
