import 'package:flutter/material.dart';

import '../features/chat/chat_screen.dart';

class AppShell extends StatelessWidget {
  const AppShell({super.key});

  @override
  Widget build(BuildContext context) {
    return const ChatScreen();
  }
}
