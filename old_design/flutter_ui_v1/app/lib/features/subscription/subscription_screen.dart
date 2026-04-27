import 'package:flutter/material.dart';

import '../../shared/widgets/section_card.dart';

class SubscriptionScreen extends StatelessWidget {
  const SubscriptionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        const SectionCard(
          title: 'Billing',
          subtitle:
              'Для mobile-версии здесь должен появиться store billing слой, а не прямой перенос Telegram Stars/YooKassa.',
        ),
        const SizedBox(height: 16),
        SectionCard(
          title: 'Что важно не сломать',
          subtitle:
              'Entitlements, restore purchases, проверку receipt/purchase token и синхронизацию лимитов с backend.',
          child: Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              FilledButton(
                onPressed: () {},
                child: const Text('Открыть тарифы'),
              ),
              OutlinedButton(
                onPressed: () {},
                child: const Text('Restore'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
