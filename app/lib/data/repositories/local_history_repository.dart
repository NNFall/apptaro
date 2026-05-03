import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../domain/models/history_entry.dart';
import '../../domain/models/job_artifact.dart';
import '../../domain/models/remote_job.dart';

class LocalHistoryRepository extends ChangeNotifier {
  static const String _storageKey = 'appslides.history.entries.v1';
  static const int _maxEntries = 100;

  final SharedPreferencesAsync _storage = SharedPreferencesAsync();
  final List<HistoryEntry> _entries = <HistoryEntry>[];
  bool _isLoaded = false;
  bool _isRestoring = false;

  List<HistoryEntry> get entries => List<HistoryEntry>.unmodifiable(_entries);
  bool get isLoaded => _isLoaded;
  bool get isRestoring => _isRestoring;

  Future<void> restore() async {
    if (_isLoaded || _isRestoring) {
      return;
    }

    _isRestoring = true;
    notifyListeners();

    try {
      final raw = await _storage.getString(_storageKey);
      if (raw == null || raw.isEmpty) {
        _entries.clear();
      } else {
        final decoded = jsonDecode(raw);
        if (decoded is List) {
          _entries
            ..clear()
            ..addAll(
              decoded.whereType<Map>().map((item) =>
                  HistoryEntry.fromJson(item.cast<String, dynamic>())),
            );
        }
      }
    } catch (_) {
      _entries.clear();
    } finally {
      _isLoaded = true;
      _isRestoring = false;
      notifyListeners();
    }
  }

  Future<void> clear() async {
    _entries.clear();
    notifyListeners();
    await _storage.remove(_storageKey);
  }

  void recordOutline({
    required String topic,
    required String title,
    required int slidesTotal,
    required int outlineItems,
  }) {
    final now = DateTime.now();
    _entries.insert(
      0,
      HistoryEntry(
        id: 'outline-${now.microsecondsSinceEpoch}',
        type: HistoryEntryType.outline,
        status: HistoryEntryStatus.info,
        title: title,
        subtitle: topic,
        details: 'Карт: 3, пунктов расклада: $outlineItems',
        createdAt: now,
        updatedAt: now,
      ),
    );
    _trim();
    _schedulePersist();
    notifyListeners();
  }

  void upsertPresentationJob({
    required String jobId,
    required String title,
    required int? designId,
    required RemoteJobStatus status,
    required String updatedAtRaw,
    String? error,
    List<JobArtifact> artifacts = const <JobArtifact>[],
    List<String> links = const <String>[],
  }) {
    final now = DateTime.now();
    final index =
        _entries.indexWhere((entry) => entry.id == 'presentation-$jobId');
    final existingLinks = index >= 0 ? _entries[index].links : const <String>[];
    final entry = HistoryEntry(
      id: 'presentation-$jobId',
      type: HistoryEntryType.presentationJob,
      status: _mapRemoteStatus(status),
      title: title,
      subtitle: 'Render job $jobId',
      details: _buildPresentationDetails(
        designId: designId,
        status: status,
        updatedAtRaw: updatedAtRaw,
        error: error,
        artifacts: artifacts,
      ),
      createdAt: index >= 0 ? _entries[index].createdAt : now,
      updatedAt: now,
      links: _mergeLinks(existingLinks, links),
    );

    if (index >= 0) {
      _entries.removeAt(index);
    }
    _entries.insert(0, entry);
    _trim();
    _schedulePersist();
    notifyListeners();
  }

  void upsertConversionJob({
    required String jobId,
    required String sourceFilename,
    required String sourceFormat,
    required String targetFormat,
    required RemoteJobStatus status,
    required String updatedAtRaw,
    String? error,
    JobArtifact? artifact,
    List<String> links = const <String>[],
  }) {
    final now = DateTime.now();
    final index =
        _entries.indexWhere((entry) => entry.id == 'conversion-$jobId');
    final existingLinks = index >= 0 ? _entries[index].links : const <String>[];
    final entry = HistoryEntry(
      id: 'conversion-$jobId',
      type: HistoryEntryType.conversionJob,
      status: _mapRemoteStatus(status),
      title: sourceFilename,
      subtitle: 'Conversion job $jobId',
      details: _buildConversionDetails(
        sourceFormat: sourceFormat,
        targetFormat: targetFormat,
        status: status,
        updatedAtRaw: updatedAtRaw,
        error: error,
        artifact: artifact,
      ),
      createdAt: index >= 0 ? _entries[index].createdAt : now,
      updatedAt: now,
      links: _mergeLinks(existingLinks, links),
    );

    if (index >= 0) {
      _entries.removeAt(index);
    }
    _entries.insert(0, entry);
    _trim();
    _schedulePersist();
    notifyListeners();
  }

  void attachPresentationLocalFile({
    required String jobId,
    required String localPath,
  }) {
    _attachLink('presentation-$jobId', localPath);
  }

  void attachConversionLocalFile({
    required String jobId,
    required String localPath,
  }) {
    _attachLink('conversion-$jobId', localPath);
  }

  void detachLocalFile(String localPath) {
    final normalizedPath = localPath.trim();
    if (normalizedPath.isEmpty) {
      return;
    }

    var changed = false;
    for (var index = 0; index < _entries.length; index++) {
      final entry = _entries[index];
      if (!entry.links.contains(normalizedPath)) {
        continue;
      }

      _entries[index] = entry.copyWith(
        links: entry.links.where((link) => link != normalizedPath).toList(),
        updatedAt: DateTime.now(),
      );
      changed = true;
    }

    if (!changed) {
      return;
    }

    _schedulePersist();
    notifyListeners();
  }

  void _trim() {
    if (_entries.length <= _maxEntries) {
      return;
    }
    _entries.removeRange(_maxEntries, _entries.length);
  }

  void _schedulePersist() {
    unawaited(_persist());
  }

  Future<void> _persist() async {
    final payload = _entries.map((entry) => entry.toJson()).toList();
    await _storage.setString(_storageKey, jsonEncode(payload));
  }

  void _attachLink(String entryId, String link) {
    final normalizedLink = link.trim();
    if (normalizedLink.isEmpty) {
      return;
    }

    final index = _entries.indexWhere((entry) => entry.id == entryId);
    if (index < 0) {
      return;
    }

    final entry = _entries[index];
    final mergedLinks = _mergeLinks(entry.links, <String>[normalizedLink]);
    _entries[index] = entry.copyWith(
      links: mergedLinks,
      updatedAt: DateTime.now(),
    );
    _schedulePersist();
    notifyListeners();
  }

  List<String> _mergeLinks(
    List<String> existing,
    List<String> incoming,
  ) {
    final merged = <String>[];
    for (final link in <String>[...existing, ...incoming]) {
      final normalized = link.trim();
      if (normalized.isEmpty || merged.contains(normalized)) {
        continue;
      }
      merged.add(normalized);
    }
    return merged;
  }

  static HistoryEntryStatus _mapRemoteStatus(RemoteJobStatus status) {
    switch (status) {
      case RemoteJobStatus.queued:
        return HistoryEntryStatus.queued;
      case RemoteJobStatus.running:
        return HistoryEntryStatus.running;
      case RemoteJobStatus.succeeded:
        return HistoryEntryStatus.succeeded;
      case RemoteJobStatus.failed:
        return HistoryEntryStatus.failed;
      case RemoteJobStatus.unknown:
        return HistoryEntryStatus.info;
    }
  }

  static String _buildPresentationDetails({
    required int? designId,
    required RemoteJobStatus status,
    required String updatedAtRaw,
    required String? error,
    required List<JobArtifact> artifacts,
  }) {
    final buffer = StringBuffer();
    if (designId != null) {
      buffer.write('Дизайн: $designId. ');
    }
    buffer.write('Статус: ${status.name}. ');
    buffer.write('Backend updated_at: $updatedAtRaw.');
    if (artifacts.isNotEmpty) {
      buffer.write(
          ' Файлы: ${artifacts.map((item) => item.filename).join(', ')}.');
    }
    if (error != null && error.isNotEmpty) {
      buffer.write(' Ошибка: $error');
    }
    return buffer.toString();
  }

  static String _buildConversionDetails({
    required String sourceFormat,
    required String targetFormat,
    required RemoteJobStatus status,
    required String updatedAtRaw,
    required String? error,
    required JobArtifact? artifact,
  }) {
    final buffer = StringBuffer();
    buffer.write(
        '${sourceFormat.toUpperCase()} -> ${targetFormat.toUpperCase()}. ');
    buffer.write('Статус: ${status.name}. ');
    buffer.write('Backend updated_at: $updatedAtRaw.');
    if (artifact != null) {
      buffer.write(' Результат: ${artifact.filename}.');
    }
    if (error != null && error.isNotEmpty) {
      buffer.write(' Ошибка: $error');
    }
    return buffer.toString();
  }
}
