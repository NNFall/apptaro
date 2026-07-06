import 'package:appslides/l10n/app_language.dart';
import 'package:appslides/l10n/app_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('returns English copy for Google Play default language', () {
    final copy = AppLocalizations.forLanguage(AppLanguage.english);

    expect(copy.appTitle, 'AI Tarot Reading');
    expect(copy.askQuestionButton, '🔮 Ask a question');
    expect(copy.languageButton, '🌐 Language');
  });

  test('keeps Russian copy available for manual language switch', () {
    final copy = AppLocalizations.forLanguage(AppLanguage.russian);

    expect(copy.appTitle, 'Таро Расклад');
    expect(copy.askQuestionButton, '🔮 Задать вопрос');
    expect(copy.languageButton, '🌐 Язык');
  });
}
