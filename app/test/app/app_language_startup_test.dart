import 'dart:async';

import 'package:apptaro/app/app.dart';
import 'package:apptaro/data/repositories/language_repository.dart';
import 'package:apptaro/l10n/app_language.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_preferences_platform_interface/in_memory_shared_preferences_async.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_async_platform_interface.dart';

void main() {
  tearDown(() {
    SharedPreferencesAsyncPlatform.instance = null;
  });

  testWidgets('restores the saved language before seeding the chat',
      (tester) async {
    SharedPreferences.setMockInitialValues(<String, Object>{
      'apptaro.language.v1': 'ru',
    });
    SharedPreferencesAsyncPlatform.instance =
        InMemorySharedPreferencesAsync.empty();
    final languageRepository = _DelayedLanguageRepository();

    await tester.pumpWidget(
      AppSlidesApp(languageRepository: languageRepository),
    );
    for (var index = 0; index < 10; index++) {
      await tester.pump(const Duration(milliseconds: 500));
    }

    expect(find.text('Menu'), findsNothing);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);

    languageRepository.completeRestore(AppLanguage.russian);
    for (var index = 0; index < 10; index++) {
      await tester.pump(const Duration(milliseconds: 500));
    }

    expect(find.text('Menu'), findsNothing);
  });
}

class _DelayedLanguageRepository extends LanguageRepository {
  final Completer<AppLanguage> _restoreCompleter = Completer<AppLanguage>();
  AppLanguage _language = AppLanguage.english;

  @override
  AppLanguage get current => _language;

  @override
  Future<void> restore({Locale? deviceLocale}) async {
    _language = await _restoreCompleter.future;
    notifyListeners();
  }

  void completeRestore(AppLanguage language) {
    _restoreCompleter.complete(language);
  }
}
