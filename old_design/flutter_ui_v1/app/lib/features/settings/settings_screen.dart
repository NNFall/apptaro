import 'package:flutter/material.dart';

import '../../app/app_scope.dart';
import '../../core/config/app_config.dart';
import '../../data/api/appslides_api_client.dart';
import '../../data/repositories/backend_config_repository.dart';
import '../../shared/widgets/section_card.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _controller;
  BackendConfigRepository? _config;
  bool _saving = false;
  bool _testing = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final config = AppScope.backendConfigOf(context);
    if (_config == config) {
      return;
    }
    _config?.removeListener(_syncFromConfig);
    _config = config;
    _controller.text = config.baseUrl;
    config.addListener(_syncFromConfig);
  }

  @override
  void dispose() {
    _config?.removeListener(_syncFromConfig);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final config = _config;
    if (config == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return AnimatedBuilder(
      animation: config,
      builder: (context, _) {
        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          children: [
            const SectionCard(
              title: 'Конфиг клиента',
              subtitle:
                  'Команда `flutter run` не завершается сама по себе: это живая dev-сессия с hot reload. Для остановки используй `q` в терминале.',
            ),
            const SizedBox(height: 16),
            SectionCard(
              title: 'Backend endpoint',
              subtitle:
                  'Для Android-эмулятора по умолчанию используется `10.0.2.2`, для web/desktop/iOS simulator — `localhost`. Для телефона укажи LAN IP компьютера.',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: _controller,
                    keyboardType: TextInputType.url,
                    decoration: const InputDecoration(
                      labelText: 'Base URL',
                      hintText: 'http://192.168.1.10:8000',
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Текущий endpoint: ${config.baseUrl}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      FilledButton(
                        onPressed: _saving ? null : _save,
                        child: Text(_saving ? 'Сохранение...' : 'Сохранить'),
                      ),
                      OutlinedButton(
                        onPressed: _testing ? null : _testConnection,
                        child: Text(_testing ? 'Проверка...' : 'Проверить'),
                      ),
                      OutlinedButton(
                        onPressed: _saving ? null : _resetToDefault,
                        child: const Text('Сбросить'),
                      ),
                    ],
                  ),
                  if (_message case final message?) ...[
                    const SizedBox(height: 12),
                    Text(
                      message,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 16),
            const SectionCard(
              title: 'Подсказки',
              subtitle:
                  'Android emulator: `http://10.0.2.2:8000`. Windows/web: `http://localhost:8000`. Телефон в одной сети: `http://<LAN-IP-ПК>:8000`.',
            ),
            const SizedBox(height: 16),
            SectionCard(
              title: 'Default endpoint',
              subtitle: AppConfig.defaultBackendBaseUrl,
            ),
          ],
        );
      },
    );
  }

  Future<void> _save() async {
    final config = _config;
    if (config == null) {
      return;
    }

    setState(() {
      _saving = true;
      _message = null;
    });

    try {
      await config.save(_controller.text);
      setState(() {
        _message = 'Endpoint сохранен.';
      });
    } catch (error) {
      setState(() {
        _message = _describeError(error);
      });
    } finally {
      setState(() {
        _saving = false;
      });
    }
  }

  Future<void> _resetToDefault() async {
    final config = _config;
    if (config == null) {
      return;
    }

    setState(() {
      _saving = true;
      _message = null;
    });

    try {
      await config.resetToDefault();
      _controller.text = config.baseUrl;
      setState(() {
        _message = 'Endpoint сброшен на значение по умолчанию.';
      });
    } finally {
      setState(() {
        _saving = false;
      });
    }
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
        _message = _describeError(error);
      });
    } finally {
      setState(() {
        _testing = false;
      });
    }
  }

  void _syncFromConfig() {
    final config = _config;
    if (config == null) {
      return;
    }
    if (_controller.text != config.baseUrl) {
      _controller.value = _controller.value.copyWith(
        text: config.baseUrl,
        selection: TextSelection.collapsed(offset: config.baseUrl.length),
      );
    }
  }

  String _describeError(Object error) {
    if (error is AppSlidesApiException) {
      return error.message;
    }
    if (error is FormatException) {
      return error.message;
    }
    return error.toString();
  }
}
