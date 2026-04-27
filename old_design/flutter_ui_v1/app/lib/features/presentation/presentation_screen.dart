import 'package:flutter/material.dart';

import '../../app/app_scope.dart';
import '../../domain/models/job_artifact.dart';
import '../../domain/models/presentation_template.dart';
import '../../domain/models/remote_job.dart';
import '../../shared/widgets/section_card.dart';
import 'presentation_controller.dart';

class PresentationScreen extends StatefulWidget {
  const PresentationScreen({super.key});

  @override
  State<PresentationScreen> createState() => _PresentationScreenState();
}

class _PresentationScreenState extends State<PresentationScreen> {
  late final TextEditingController _topicController;
  late final TextEditingController _titleController;
  late final TextEditingController _reviseController;
  PresentationController? _controller;

  @override
  void initState() {
    super.initState();
    _topicController = TextEditingController();
    _titleController = TextEditingController();
    _reviseController = TextEditingController();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_controller != null) {
      return;
    }
    _controller = PresentationController(
      repository: AppScope.repositoryOf(context),
      historyRepository: AppScope.historyOf(context),
      savedFilesRepository: AppScope.savedFilesOf(context),
    )..initialize();
    _controller!.addListener(_syncTextFields);
  }

  @override
  void dispose() {
    _controller?.removeListener(_syncTextFields);
    _controller?.dispose();
    _topicController.dispose();
    _titleController.dispose();
    _reviseController.dispose();
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
            SectionCard(
              title: 'Новая презентация',
              subtitle:
                  'Экран уже работает поверх backend API: получает шаблоны, строит outline, правит его и запускает render job.',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: _topicController,
                    minLines: 2,
                    maxLines: 4,
                    textInputAction: TextInputAction.done,
                    decoration: const InputDecoration(
                      labelText: 'Тема презентации',
                      hintText: 'Например: Почему Марс интересен для будущих миссий',
                    ),
                    onChanged: controller.setTopic,
                  ),
                  const SizedBox(height: 16),
                  DropdownButtonFormField<int>(
                    key: ValueKey('slides-total-${controller.slidesTotal}'),
                    initialValue: controller.slidesTotal,
                    decoration: const InputDecoration(
                      labelText: 'Количество слайдов',
                    ),
                    items: controller.slideOptions
                        .map(
                          (value) => DropdownMenuItem<int>(
                            value: value,
                            child: Text('$value слайдов'),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value != null) {
                        controller.setSlidesTotal(value);
                      }
                    },
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: [
                      FilledButton.icon(
                        onPressed: controller.canGenerateOutline
                            ? controller.generateOutline
                            : null,
                        icon: controller.generatingOutline
                            ? const SizedBox.square(
                                dimension: 16,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.auto_awesome_rounded),
                        label: const Text('Сгенерировать outline'),
                      ),
                      OutlinedButton.icon(
                        onPressed: controller.loadingTemplates
                            ? null
                            : controller.refreshTemplates,
                        icon: const Icon(Icons.grid_view_rounded),
                        label: const Text('Обновить шаблоны'),
                      ),
                    ],
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
              title: 'План и заголовок',
              subtitle: controller.hasOutline
                  ? 'Можно вручную поправить заголовок и отдельные пункты outline перед запуском рендера.'
                  : 'Сначала сгенерируй outline по теме. После этого здесь появится редактируемый план.',
              child: controller.hasOutline
                  ? Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        TextField(
                          controller: _titleController,
                          decoration: const InputDecoration(
                            labelText: 'Заголовок презентации',
                          ),
                          onChanged: controller.setTitle,
                        ),
                        const SizedBox(height: 16),
                        for (var index = 0; index < controller.outline.length; index++) ...[
                          TextFormField(
                            key: ValueKey('outline-$index-${controller.outline[index]}'),
                            initialValue: controller.outline[index],
                            decoration: InputDecoration(
                              labelText: 'Слайд ${index + 1}',
                            ),
                            onChanged: (value) => controller.updateOutlineItem(index, value),
                          ),
                          const SizedBox(height: 12),
                        ],
                        const SizedBox(height: 4),
                        TextField(
                          controller: _reviseController,
                          minLines: 2,
                          maxLines: 3,
                          decoration: const InputDecoration(
                            labelText: 'Комментарий для пересборки outline',
                            hintText: 'Например: сделай акцент на практических выводах и убери общий вводный слайд',
                          ),
                        ),
                        const SizedBox(height: 12),
                        OutlinedButton.icon(
                          onPressed: controller.revisingOutline
                              ? null
                              : () async {
                                  final comment = _reviseController.text;
                                  await controller.reviseOutline(comment);
                                },
                          icon: controller.revisingOutline
                              ? const SizedBox.square(
                                  dimension: 16,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Icon(Icons.tune_rounded),
                          label: const Text('Пересобрать outline'),
                        ),
                      ],
                    )
                  : const _EmptyState(
                      icon: Icons.notes_rounded,
                      text: 'План пока пуст. Сгенерируй outline, чтобы открыть редактор.',
                    ),
            ),
            const SizedBox(height: 16),
            SectionCard(
              title: 'Дизайн и render',
              subtitle:
                  'Выбери шаблон и формат результата. Пока файл ещё не сохраняется на устройство, но job и download URLs уже работают.',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _TemplatesStrip(
                    templates: controller.templates,
                    loading: controller.loadingTemplates,
                    selectedId: controller.selectedDesignId,
                    onSelected: controller.selectDesign,
                  ),
                  const SizedBox(height: 16),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Сразу собирать PDF'),
                    subtitle: const Text('Если выключить, backend отдаст только PPTX.'),
                    value: controller.generatePdf,
                    onChanged: controller.setGeneratePdf,
                  ),
                  const SizedBox(height: 8),
                  FilledButton.icon(
                    onPressed: controller.canStartJob ? controller.startPresentationJob : null,
                    icon: controller.startingJob
                        ? const SizedBox.square(
                            dimension: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.play_arrow_rounded),
                    label: const Text('Запустить render job'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _JobCard(job: controller.job, controller: controller),
          ],
        );
      },
    );
  }

  void _syncTextFields() {
    final controller = _controller;
    if (controller == null) {
      return;
    }
    if (_titleController.text != controller.title) {
      _titleController.value = _titleController.value.copyWith(
        text: controller.title,
        selection: TextSelection.collapsed(offset: controller.title.length),
      );
    }
  }
}

class _TemplatesStrip extends StatelessWidget {
  const _TemplatesStrip({
    required this.templates,
    required this.loading,
    required this.selectedId,
    required this.onSelected,
  });

  final List<PresentationTemplate> templates;
  final bool loading;
  final int? selectedId;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (loading && templates.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 24),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (templates.isEmpty) {
      return const _EmptyState(
        icon: Icons.grid_view_rounded,
        text: 'Каталог шаблонов пока не загружен.',
      );
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: templates.map((template) {
          final selected = template.id == selectedId;
          return Padding(
            padding: const EdgeInsets.only(right: 12),
            child: InkWell(
              borderRadius: BorderRadius.circular(20),
              onTap: template.templateAvailable ? () => onSelected(template.id) : null,
              child: Ink(
                width: 212,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(20),
                  color: selected
                      ? theme.colorScheme.primaryContainer
                      : theme.colorScheme.surface,
                  border: Border.all(
                    color: selected
                        ? theme.colorScheme.primary
                        : theme.colorScheme.outlineVariant,
                    width: selected ? 1.5 : 1,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            template.name,
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        if (selected)
                          Icon(
                            Icons.check_circle_rounded,
                            color: theme.colorScheme.primary,
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      template.templateAvailable
                          ? 'Шаблон доступен'
                          : 'Файл шаблона недоступен',
                      style: theme.textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      template.previewAvailable
                          ? 'Preview найден на backend'
                          : 'Preview пока отсутствует',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Container(
                      height: 96,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(16),
                        gradient: LinearGradient(
                          colors: selected
                              ? const [Color(0xFF123C58), Color(0xFFDC8359)]
                              : const [Color(0xFFF2E4D8), Color(0xFFE7D0BD)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                      ),
                      alignment: Alignment.center,
                      child: Icon(
                        Icons.slideshow_rounded,
                        size: 34,
                        color: selected ? Colors.white : theme.colorScheme.primary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _JobCard extends StatelessWidget {
  const _JobCard({
    required this.job,
    required this.controller,
  });

  final RemoteJob? job;
  final PresentationController controller;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (job == null) {
      return const SectionCard(
        title: 'Render job',
        subtitle:
            'После запуска здесь появится статус `queued/running/succeeded/failed` и ссылки на итоговые файлы.',
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
      title: 'Render job',
      subtitle: 'Job ID: ${job!.jobId}',
      trailing: _StatusPill(
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
          if (job!.artifacts.isNotEmpty) ...[
            const SizedBox(height: 16),
            ...job!.artifacts.map(
              (artifact) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _ArtifactTile(
                  artifact: artifact,
                  url: controller.downloadUrlFor(artifact),
                  savedPath: controller.savedPathFor(artifact.artifactId),
                  saving: controller.isSavingArtifact(artifact.artifactId),
                  onSave: () => controller.saveArtifact(artifact),
                ),
              ),
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

class _ArtifactTile extends StatelessWidget {
  const _ArtifactTile({
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
                artifact.kind == 'pdf'
                    ? Icons.picture_as_pdf_rounded
                    : Icons.slideshow_rounded,
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

class _StatusPill extends StatelessWidget {
  const _StatusPill({
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

class _EmptyState extends StatelessWidget {
  const _EmptyState({
    required this.icon,
    required this.text,
  });

  final IconData icon;
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
      child: Row(
        children: [
          Icon(icon, color: theme.colorScheme.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
