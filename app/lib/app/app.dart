import 'package:flutter/material.dart';

import '../core/config/app_config.dart';
import 'app_scope.dart';
import 'shell.dart';
import 'theme.dart';

class AppSlidesApp extends StatelessWidget {
  const AppSlidesApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: AppConfig.appName,
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      home: const AppScope(
        child: AppShell(),
      ),
    );
  }
}
