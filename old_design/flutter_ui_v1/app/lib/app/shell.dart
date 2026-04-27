import 'package:flutter/material.dart';

import '../features/converter/converter_screen.dart';
import '../features/history/history_screen.dart';
import '../features/home/home_screen.dart';
import '../features/presentation/presentation_screen.dart';
import '../features/settings/settings_screen.dart';
import '../features/subscription/subscription_screen.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;

  late final List<_ShellTab> _tabs = <_ShellTab>[
    const _ShellTab(
      title: 'Обзор',
      icon: Icons.dashboard_rounded,
      screen: HomeScreen(),
    ),
    const _ShellTab(
      title: 'Презентации',
      icon: Icons.slideshow_rounded,
      screen: PresentationScreen(),
    ),
    const _ShellTab(
      title: 'Конвертер',
      icon: Icons.swap_horiz_rounded,
      screen: ConverterScreen(),
    ),
    const _ShellTab(
      title: 'История',
      icon: Icons.history_rounded,
      screen: HistoryScreen(),
    ),
    const _ShellTab(
      title: 'Подписка',
      icon: Icons.workspace_premium_rounded,
      screen: SubscriptionScreen(),
    ),
    const _ShellTab(
      title: 'Настройки',
      icon: Icons.tune_rounded,
      screen: SettingsScreen(),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final tab = _tabs[_index];
    return Scaffold(
      appBar: AppBar(
        title: Text(tab.title),
      ),
      body: SafeArea(
        child: IndexedStack(
          index: _index,
          children: _tabs.map((tab) => tab.screen).toList(),
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (index) {
          setState(() {
            _index = index;
          });
        },
        destinations: _tabs
            .map(
              (tab) => NavigationDestination(
                icon: Icon(tab.icon),
                label: tab.title,
              ),
            )
            .toList(),
      ),
    );
  }
}

class _ShellTab {
  const _ShellTab({
    required this.title,
    required this.icon,
    required this.screen,
  });

  final String title;
  final IconData icon;
  final Widget screen;
}
