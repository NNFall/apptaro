import 'package:flutter/material.dart';

import '../../app/app_scope.dart';
import '../../core/config/app_config.dart';
import '../../shared/widgets/section_card.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _testing = false;
  String? _message;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        const SectionCard(
          title: 'Backend endpoint',
          subtitle:
              'Приложение всегда подключается к удаленному серверу apptaro. Локальное переключение URL отключено.',
        ),
        const SizedBox(height: 16),
        SectionCard(
          title: 'Active server',
          subtitle: AppConfig.defaultBackendBaseUrl,
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton(
                onPressed: _testing ? null : _testConnection,
                child: Text(_testing ? 'Проверка...' : 'Проверить /v1/health'),
              ),
            ],
          ),
        ),
        if (_message case final message?) ...[
          const SizedBox(height: 16),
          SectionCard(
            title: 'Результат',
            subtitle: message,
          ),
        ],
      ],
    );
  }

  Future<void> _testConnection() async {
    setState(() {
      _testing = true;
      _message = null;
    });

    try {
      final healthy = await AppScope.repositoryOf(context).healthcheck();
      setState(() {
        _message = healthy
            ? 'Backend ответил: /v1/health -> ok'
            : 'Backend ответил, но статус не ok';
      });
    } catch (error) {
      setState(() {
        _message = error.toString();
      });
    } finally {
      setState(() {
        _testing = false;
      });
    }
  }
}
