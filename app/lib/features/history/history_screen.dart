import 'package:flutter/material.dart';

import '../../app/app_scope.dart';
import '../../data/repositories/local_history_repository.dart';
import '../../data/repositories/saved_files_repository.dart';
import '../../domain/models/history_entry.dart';
import '../../domain/models/saved_file_entry.dart';
import '../../shared/widgets/section_card.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final Set<String> _busySavedEntryIds = <String>{};

  @override
  Widget build(BuildContext context) {
    final history = AppScope.historyOf(context);
    final savedFiles = AppScope.savedFilesOf(context);

    return AnimatedBuilder(
      animation: Listenable.merge(<Listenable>[history, savedFiles]),
      builder: (context, _) {
        final entries = history.entries;
        final savedEntries = savedFiles.entries;
        final restoringHistory = history.isRestoring && !history.isLoaded;
        final restoringSavedFiles =
            savedFiles.isRestoring && !savedFiles.isLoaded;

        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          children: [
            SectionCard(
              title: 'Local history',
              subtitle:
                  'Requests and job events are stored locally on this device and survive app restarts.',
              trailing: OutlinedButton(
                onPressed: entries.isEmpty ? null : () async => history.clear(),
                child: const Text('Clear'),
              ),
            ),
            const SizedBox(height: 16),
            SectionCard(
              title: 'Saved files',
              subtitle: savedEntries.isEmpty
                  ? 'Saved tarot images and text readings will appear here.'
                  : 'Files are stored in the app sandbox and stay available without another backend request.',
            ),
            const SizedBox(height: 16),
            if (restoringSavedFiles)
              const SectionCard(
                title: 'Loading file index',
                subtitle: 'The app is restoring locally saved results.',
                child: Padding(
                  padding: EdgeInsets.only(top: 16),
                  child: LinearProgressIndicator(),
                ),
              )
            else if (savedEntries.isEmpty)
              const SectionCard(
                title: 'No local files yet',
                subtitle: 'Save a tarot reading result to show it here.',
              )
            else
              ...savedEntries.map(
                (entry) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _SavedFileCard(
                    entry: entry,
                    busy: _busySavedEntryIds.contains(entry.id),
                    onOpen: () => _openSavedFile(savedFiles, entry),
                    onDelete: () => _deleteSavedFile(
                      savedFiles: savedFiles,
                      history: history,
                      entry: entry,
                    ),
                  ),
                ),
              ),
            const SizedBox(height: 16),
            if (restoringHistory)
              const SectionCard(
                title: 'Loading history',
                subtitle:
                    'The app is restoring local records from persistent storage.',
                child: Padding(
                  padding: EdgeInsets.only(top: 16),
                  child: LinearProgressIndicator(),
                ),
              )
            else if (entries.isEmpty)
              const SectionCard(
                title: 'History is empty',
                subtitle:
                    'Ask a question or generate a reading to create records.',
              )
            else
              ...entries.map(
                (entry) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _HistoryEntryCard(entry: entry),
                ),
              ),
          ],
        );
      },
    );
  }

  Future<void> _openSavedFile(
    SavedFilesRepository savedFiles,
    SavedFileEntry entry,
  ) async {
    await _runSavedFileAction(
      entry.id,
      () async {
        final error = await savedFiles.openEntry(entry);
        if (!mounted || error == null) {
          return;
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error)),
        );
      },
    );
  }

  Future<void> _deleteSavedFile({
    required SavedFilesRepository savedFiles,
    required LocalHistoryRepository history,
    required SavedFileEntry entry,
  }) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Delete local file?'),
          content: Text(
            'File `${entry.filename}` will be removed from local app storage.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('Delete'),
            ),
          ],
        );
      },
    );

    if (confirmed != true) {
      return;
    }

    await _runSavedFileAction(
      entry.id,
      () async {
        final deleted = await savedFiles.deleteEntry(entry);
        if (!mounted) {
          return;
        }

        if (deleted) {
          history.detachLocalFile(entry.localPath);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Deleted ${entry.filename}')),
          );
          return;
        }

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not delete the file.')),
        );
      },
    );
  }

  Future<void> _runSavedFileAction(
    String entryId,
    Future<void> Function() action,
  ) async {
    if (_busySavedEntryIds.contains(entryId)) {
      return;
    }

    setState(() {
      _busySavedEntryIds.add(entryId);
    });

    try {
      await action();
    } finally {
      if (mounted) {
        setState(() {
          _busySavedEntryIds.remove(entryId);
        });
      }
    }
  }
}

class _SavedFileCard extends StatelessWidget {
  const _SavedFileCard({
    required this.entry,
    required this.busy,
    required this.onOpen,
    required this.onDelete,
  });

  final SavedFileEntry entry;
  final bool busy;
  final Future<void> Function() onOpen;
  final Future<void> Function() onDelete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sourceLabel = switch (entry.sourceType) {
      SavedFileSourceType.presentationArtifact => 'tarot reading',
      SavedFileSourceType.conversionArtifact => 'saved file',
    };

    return SectionCard(
      title: entry.filename,
      subtitle:
          '${entry.kind.toUpperCase()} - ${_formatFileSize(entry.sizeBytes)} - $sourceLabel',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            entry.localPath,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.primary,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'Job: ${entry.jobId}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Saved: ${entry.savedAt.toLocal()}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.tonalIcon(
                onPressed: busy ? null : () => onOpen(),
                icon: busy
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.open_in_new_rounded),
                label: const Text('Open'),
              ),
              OutlinedButton.icon(
                onPressed: busy ? null : () => onDelete(),
                icon: const Icon(Icons.delete_outline_rounded),
                label: const Text('Delete'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _HistoryEntryCard extends StatelessWidget {
  const _HistoryEntryCard({
    required this.entry,
  });

  final HistoryEntry entry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SectionCard(
      title: entry.title,
      subtitle: entry.subtitle,
      trailing: _HistoryStatusChip(status: entry.status),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            entry.details,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Updated: ${entry.updatedAt.toLocal()}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          if (entry.links.isNotEmpty) ...[
            const SizedBox(height: 10),
            ...entry.links.map(
              (link) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(
                  link,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.primary,
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _HistoryStatusChip extends StatelessWidget {
  const _HistoryStatusChip({
    required this.status,
  });

  final HistoryEntryStatus status;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = switch (status) {
      HistoryEntryStatus.info => theme.colorScheme.primary,
      HistoryEntryStatus.queued => const Color(0xFF8A5A00),
      HistoryEntryStatus.running => const Color(0xFF0F6E9A),
      HistoryEntryStatus.succeeded => const Color(0xFF2E7D32),
      HistoryEntryStatus.failed => theme.colorScheme.error,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        status.name,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w700,
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
