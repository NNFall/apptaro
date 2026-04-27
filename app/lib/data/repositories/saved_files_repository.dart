import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:open_filex/open_filex.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../domain/models/saved_file_entry.dart';
import '../storage/local_file_store.dart';
import 'appslides_repository.dart';

class SavedFilesRepository extends ChangeNotifier {
  SavedFilesRepository({
    required AppSlidesRepository repository,
  })  : _repository = repository,
        _fileStore = createLocalFileStore();

  static const String _storageKey = 'appslides.saved_files.entries.v1';
  static const int _maxEntries = 50;

  final AppSlidesRepository _repository;
  final LocalFileStore _fileStore;
  final SharedPreferencesAsync _storage = SharedPreferencesAsync();
  final List<SavedFileEntry> _entries = <SavedFileEntry>[];

  bool _isLoaded = false;
  bool _isRestoring = false;

  List<SavedFileEntry> get entries => List<SavedFileEntry>.unmodifiable(_entries);
  bool get isLoaded => _isLoaded;
  bool get isRestoring => _isRestoring;

  SavedFileEntry? findByArtifactId(String artifactId) {
    for (final entry in _entries) {
      if (entry.artifactId == artifactId) {
        return entry;
      }
    }
    return null;
  }

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
          final restored = <SavedFileEntry>[];
          for (final item in decoded.whereType<Map>()) {
            final entry = SavedFileEntry.fromJson(item.cast<String, dynamic>());
            if (await _fileStore.exists(entry.localPath)) {
              restored.add(entry);
            }
          }
          _entries
            ..clear()
            ..addAll(restored);
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

  Future<SavedFileEntry> downloadAndStore({
    required SavedFileSourceType sourceType,
    required String jobId,
    required String artifactId,
    required String kind,
    required String filename,
    required String mediaType,
    required Uri remoteUri,
  }) async {
    final existing = findByArtifactId(artifactId);
    if (existing != null && await _fileStore.exists(existing.localPath)) {
      return existing;
    }

    final bytes = await _repository.downloadBytes(remoteUri);
    final storedFile = await _fileStore.save(
      bytes: bytes,
      filename: filename,
      uniqueHint: artifactId,
    );

    final entry = SavedFileEntry(
      id: 'saved-$artifactId',
      sourceType: sourceType,
      jobId: jobId,
      artifactId: artifactId,
      kind: kind,
      filename: filename,
      mediaType: mediaType,
      remoteUrl: remoteUri.toString(),
      localPath: storedFile.path,
      sizeBytes: storedFile.sizeBytes,
      savedAt: DateTime.now(),
    );

    _upsert(entry);
    await _persist();
    notifyListeners();
    return entry;
  }

  Future<String?> openEntry(SavedFileEntry entry) async {
    if (!await _fileStore.exists(entry.localPath)) {
      return 'Файл больше не найден на устройстве.';
    }

    final result = await OpenFilex.open(entry.localPath);
    if (result.type == ResultType.done) {
      return null;
    }

    final message = result.message.trim();
    if (message.isEmpty) {
      return 'Не удалось открыть файл.';
    }
    return message;
  }

  Future<bool> deleteEntry(SavedFileEntry entry) async {
    await _fileStore.delete(entry.localPath);
    final index = _entries.indexWhere((item) => item.id == entry.id);
    if (index < 0) {
      return false;
    }

    _entries.removeAt(index);
    await _persist();
    notifyListeners();
    return true;
  }

  void _upsert(SavedFileEntry entry) {
    final index = _entries.indexWhere((item) => item.artifactId == entry.artifactId);
    if (index >= 0) {
      _entries.removeAt(index);
    }
    _entries.insert(0, entry);
    if (_entries.length > _maxEntries) {
      _entries.removeRange(_maxEntries, _entries.length);
    }
  }

  Future<void> _persist() async {
    final payload = _entries.map((entry) => entry.toJson()).toList();
    await _storage.setString(_storageKey, jsonEncode(payload));
  }
}
