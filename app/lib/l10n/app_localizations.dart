import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

import 'app_language.dart';

class AppLocalizations {
  const AppLocalizations._(this.language);

  final AppLanguage language;

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  static AppLocalizations forLanguage(AppLanguage language) {
    return AppLocalizations._(language);
  }

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations) ??
        AppLocalizations.forLanguage(AppLanguage.english);
  }

  String get appTitle => switch (language) {
        AppLanguage.english => 'Tarot Reading',
        AppLanguage.russian => 'Таро Расклад',
      };

  String get askQuestionButton => switch (language) {
        AppLanguage.english => '🔮 Ask a question',
        AppLanguage.russian => '🔮 Задать вопрос',
      };

  String get languageButton => switch (language) {
        AppLanguage.english => '🌐 Language',
        AppLanguage.russian => '🌐 Язык',
      };
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) {
    return AppLanguage.values.any((item) => item.code == locale.languageCode);
  }

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(
      AppLocalizations.forLanguage(AppLanguage.fromLocale(locale)),
    );
  }

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}
