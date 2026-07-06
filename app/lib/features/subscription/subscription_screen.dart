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
              'The Google Play version uses store billing instead of Telegram Stars or YooKassa redirects.',
        ),
        const SizedBox(height: 16),
        SectionCard(
          title: 'What must stay intact',
          subtitle:
              'Entitlements, purchase restore, purchase-token validation, and backend limit synchronization.',
          child: Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              FilledButton(
                onPressed: () {},
                child: const Text('Open plans'),
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
