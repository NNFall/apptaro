import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import '../core/config/app_config.dart';
import '../data/repositories/language_repository.dart';
import '../l10n/app_language.dart';
import '../l10n/app_localizations.dart';
import 'app_scope.dart';
import 'shell.dart';
import 'theme.dart';

class AppSlidesApp extends StatefulWidget {
  const AppSlidesApp({super.key});

  @override
  State<AppSlidesApp> createState() => _AppSlidesAppState();
}

class _AppSlidesAppState extends State<AppSlidesApp> {
  late final LanguageRepository _languageRepository = LanguageRepository();

  @override
  void initState() {
    super.initState();
    unawaited(_languageRepository.restore());
  }

  @override
  void dispose() {
    _languageRepository.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _languageRepository,
      builder: (context, _) {
        return MaterialApp(
          title: AppConfig.appName,
          debugShowCheckedModeBanner: false,
          locale: _languageRepository.current.locale,
          localizationsDelegates: const <LocalizationsDelegate<dynamic>>[
            AppLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
          ],
          supportedLocales:
              AppLanguage.values.map((item) => item.locale).toList(),
          theme: buildAppTheme(),
          home: AppScope(
            languageRepository: _languageRepository,
            child: const AppShell(),
          ),
        );
      },
    );
  }
}
