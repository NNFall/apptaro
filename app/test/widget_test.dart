import 'package:appslides/features/home/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Home screen smoke test', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: HomeScreen(),
        ),
      ),
    );

    expect(find.text('apptaro'), findsOneWidget);
    expect(find.textContaining('3 карты в раскладе'), findsOneWidget);
  });
}
