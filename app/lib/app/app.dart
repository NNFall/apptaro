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
  const AppSlidesApp({
    super.key,
    this.languageRepository,
  });

  final LanguageRepository? languageRepository;

  @override
  State<AppSlidesApp> createState() => _AppSlidesAppState();
}

class _AppSlidesAppState extends State<AppSlidesApp> {
  late final LanguageRepository _languageRepository =
      widget.languageRepository ?? LanguageRepository();
  late final bool _ownsLanguageRepository = widget.languageRepository == null;
  bool _languageRestored = false;

  @override
  void initState() {
    super.initState();
    unawaited(_restoreLanguage());
  }

  Future<void> _restoreLanguage() async {
    try {
      await _languageRepository.restore();
    } finally {
      if (mounted) {
        setState(() {
          _languageRestored = true;
        });
      }
    }
  }

  @override
  void dispose() {
    if (_ownsLanguageRepository) {
      _languageRepository.dispose();
    }
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
          home: _languageRestored
              ? AppScope(
                  languageRepository: _languageRepository,
                  child: const AppShell(),
                )
              : const Scaffold(
                  body: Center(
                    child: CircularProgressIndicator(),
                  ),
                ),
        );
      },
    );
  }
}
