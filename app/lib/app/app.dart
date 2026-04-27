import 'package:flutter/material.dart';

import 'app_scope.dart';
import 'shell.dart';
import 'theme.dart';

class AppSlidesApp extends StatelessWidget {
  const AppSlidesApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AppSlides',
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      home: const AppScope(
        child: AppShell(),
      ),
    );
  }
}
