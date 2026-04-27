import 'package:flutter/material.dart';

import '../../app/app_scope.dart';
import '../../domain/models/job_artifact.dart';
import '../../domain/models/remote_job.dart';
import '../../shared/widgets/section_card.dart';
import 'converter_controller.dart';

class ConverterScreen extends StatefulWidget {
  const ConverterScreen({super.key});

  @override
  State<ConverterScreen> createState() => _ConverterScreenState();
}

class _ConverterScreenState extends State<ConverterScreen> {
  ConverterController? _controller;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _controller ??= ConverterController(
      repository: AppScope.repositoryOf(context),
      historyRepository: AppScope.historyOf(context),
      savedFilesRepository: AppScope.savedFilesOf(context),
    );
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    if (controller == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final theme = Theme.of(context);
        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          children: [
            const SectionCard(
              title: 'Поддерживаемые направления',
              subtitle: 'PDF -> DOCX, DOCX -> PDF, PPTX -> PDF.',
            ),
            const SizedBox(height: 16),
            SectionCard(
              title: 'Выбор файла',
              subtitle:
                  'Экран уже работает поверх conversion jobs: открывает системный picker, загружает байты файла и запускает backend job.',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  FilledButton.icon(
                    onPressed: controller.pickingFile ? null : controller.pickFile,
                    icon: controller.pickingFile
                        ? const SizedBox.square(
                            dimension: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.upload_file_rounded),
                    label: const Text('Выбрать файл'),
                  ),
                  const SizedBox(height: 16),
                  if (controller.selectedFile case final file?)
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.surface,
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: theme.colorScheme.outlineVariant),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            file.name,
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Формат: ${file.extension.toUpperCase()} · ${_formatFileSize(file.size)}',
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    )
                  else
                    const _ConverterHint(
                      text: 'Выбери локальный PDF, DOCX или PPTX через системный picker.',
                    ),
                ],
              ),
            ),
            if (controller.error case final error?) ...[
              const SizedBox(height: 16),
              SectionCard(
                title: 'Ошибка',
                subtitle: error,
                trailing: Icon(
                  Icons.error_outline_rounded,
                  color: theme.colorScheme.error,
                ),
              ),
            ],
            const SizedBox(height: 16),
            SectionCard(
              title: 'Целевой формат',
              subtitle: controller.selectedFile == null
                  ? 'Сначала выбери исходный файл. После этого приложение покажет допустимый формат конвертации.'
                  : 'Доступные направления строятся автоматически по расширению выбранного файла.',
              child: controller.availableTargets.isEmpty
                  ? const _ConverterHint(
                      text: 'Пока нет доступных направлений конвертации.',
                    )
                  : DropdownButtonFormField<String>(
                      key: ValueKey(
                        'converter-target-${controller.selectedFile?.extension}-${controller.targetFormat}',
                      ),
                      initialValue: controller.targetFormat,
                      decoration: const InputDecoration(
                        labelText: 'Конвертировать в',
                      ),
                      items: controller.availableTargets
                          .map(
                            (value) => DropdownMenuItem<String>(
                              value: value,
                              child: Text(value.toUpperCase()),
                            ),
                          )
                          .toList(),
                      onChanged: controller.setTargetFormat,
                    ),
            ),
            const SizedBox(height: 16),
            SectionCard(
              title: 'Запуск conversion job',
              subtitle:
                  'После старта клиент опрашивает backend и показывает итоговый файл через download URL.',
              child: FilledButton.icon(
                onPressed: controller.canStartJob ? controller.startConversionJob : null,
                icon: controller.startingJob
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.play_arrow_rounded),
                label: const Text('Запустить конвертацию'),
              ),
            ),
            const SizedBox(height: 16),
            _ConversionJobCard(job: controller.job, controller: controller),
          ],
        );
      },
    );
  }
}

class _ConversionJobCard extends StatelessWidget {
  const _ConversionJobCard({
    required this.job,
    required this.controller,
  });

  final RemoteJob? job;
  final ConverterController controller;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (job == null) {
      return const SectionCard(
        title: 'Conversion job',
        subtitle:
            'После запуска здесь появится статус `queued/running/succeeded/failed` и ссылка на итоговый файл.',
      );
    }

    final statusLabel = switch (job!.status) {
      RemoteJobStatus.queued => 'queued',
      RemoteJobStatus.running => 'running',
      RemoteJobStatus.succeeded => 'succeeded',
      RemoteJobStatus.failed => 'failed',
      RemoteJobStatus.unknown => 'unknown',
    };

    return SectionCard(
      title: 'Conversion job',
      subtitle: 'Job ID: ${job!.jobId}',
      trailing: _ConverterStatusPill(
        label: statusLabel,
        color: switch (job!.status) {
          RemoteJobStatus.succeeded => const Color(0xFF2E7D32),
          RemoteJobStatus.failed => theme.colorScheme.error,
          RemoteJobStatus.running => const Color(0xFF0F6E9A),
          RemoteJobStatus.queued => const Color(0xFF8A5A00),
          RemoteJobStatus.unknown => theme.colorScheme.outline,
        },
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Обновлено: ${job!.updatedAt}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          if (job!.error case final error?) ...[
            const SizedBox(height: 12),
            Text(
              error,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.error,
              ),
            ),
          ],
          if (job!.artifact case final artifact?) ...[
            const SizedBox(height: 16),
            _ConversionArtifactTile(
              artifact: artifact,
              url: controller.downloadUrlFor(artifact),
              savedPath: controller.savedPathFor(artifact.artifactId),
              saving: controller.isSavingArtifact(artifact.artifactId),
              onSave: () => controller.saveArtifact(artifact),
            ),
          ] else if (job!.status == RemoteJobStatus.running ||
              job!.status == RemoteJobStatus.queued) ...[
            const SizedBox(height: 16),
            const LinearProgressIndicator(),
          ],
        ],
      ),
    );
  }
}

class _ConversionArtifactTile extends StatelessWidget {
  const _ConversionArtifactTile({
    required this.artifact,
    required this.url,
    required this.savedPath,
    required this.saving,
    required this.onSave,
  });

  final JobArtifact artifact;
  final String? url;
  final String? savedPath;
  final bool saving;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                artifact.kind == 'docx'
                    ? Icons.description_rounded
                    : Icons.picture_as_pdf_rounded,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  artifact.filename,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            url ?? artifact.downloadUrl,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              FilledButton.tonalIcon(
                onPressed: saving || savedPath != null ? null : onSave,
                icon: saving
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Icon(
                        savedPath == null
                            ? Icons.download_rounded
                            : Icons.check_circle_rounded,
                      ),
                label: Text(savedPath == null ? 'Сохранить локально' : 'Сохранено'),
              ),
              if (savedPath case final path?)
                Text(
                  path,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.primary,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ConverterStatusPill extends StatelessWidget {
  const _ConverterStatusPill({
    required this.label,
    required this.color,
  });

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _ConverterHint extends StatelessWidget {
  const _ConverterHint({
    required this.text,
  });

  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Text(
        text,
        style: theme.textTheme.bodyMedium?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}

String _formatFileSize(int bytes) {
  if (bytes < 1024) {
    return '$bytes B';
  }
  if (bytes < 1024 * 1024) {
    return '${(bytes / 1024).toStringAsFixed(1)} KB';
  }
  return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
}
