import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';

import '../../data/api/appslides_api_client.dart';
import '../../data/repositories/appslides_repository.dart';
import '../../data/repositories/local_history_repository.dart';
import '../../data/repositories/saved_files_repository.dart';
import '../../domain/models/job_artifact.dart';
import '../../domain/models/remote_job.dart';
import '../../domain/models/saved_file_entry.dart';

class ConverterController extends ChangeNotifier {
  ConverterController({
    required AppSlidesRepository repository,
    required LocalHistoryRepository historyRepository,
    required SavedFilesRepository savedFilesRepository,
  })  : _repository = repository,
        _historyRepository = historyRepository,
        _savedFilesRepository = savedFilesRepository {
    _savedFilesRepository.addListener(_handleSavedFilesChanged);
  }

  final AppSlidesRepository _repository;
  final LocalHistoryRepository _historyRepository;
  final SavedFilesRepository _savedFilesRepository;

  static const Map<String, List<String>> _targetsBySource = <String, List<String>>{
    'pdf': <String>['docx'],
    'docx': <String>['pdf'],
    'pptx': <String>['pdf'],
  };

  PickedConversionFile? _selectedFile;
  String? _targetFormat;
  bool _pickingFile = false;
  bool _startingJob = false;
  String? _error;
  RemoteJob? _job;
  final Set<String> _savingArtifactIds = <String>{};
  Timer? _pollTimer;

  PickedConversionFile? get selectedFile => _selectedFile;
  String? get targetFormat => _targetFormat;
  bool get pickingFile => _pickingFile;
  bool get startingJob => _startingJob;
  String? get error => _error;
  RemoteJob? get job => _job;

  List<String> get supportedExtensions => _targetsBySource.keys.toList();

  List<String> get availableTargets {
    final extension = _selectedFile?.extension;
    if (extension == null) {
      return const <String>[];
    }
    return _targetsBySource[extension] ?? const <String>[];
  }

  bool get canStartJob =>
      _selectedFile != null &&
      _targetFormat != null &&
      !_startingJob &&
      !_isJobActive;

  bool get _isJobActive =>
      _job != null &&
      (_job!.status == RemoteJobStatus.queued || _job!.status == RemoteJobStatus.running);

  void reset() {
    _pollTimer?.cancel();
    _selectedFile = null;
    _targetFormat = null;
    _pickingFile = false;
    _startingJob = false;
    _error = null;
    _job = null;
    _savingArtifactIds.clear();
    notifyListeners();
  }

  Future<void> pickFile({
    List<String>? allowedExtensions,
  }) async {
    if (_pickingFile) {
      return;
    }

    _pickingFile = true;
    _error = null;
    notifyListeners();

    try {
      final result = await FilePicker.pickFiles(
        allowMultiple: false,
        withData: true,
        type: FileType.custom,
        allowedExtensions: allowedExtensions ?? supportedExtensions,
      );
      if (result == null || result.files.isEmpty) {
        return;
      }

      final file = result.files.single;
      final extension = (file.extension ?? _extensionFromName(file.name))?.toLowerCase();
      final bytes = file.bytes;
      if (extension == null || !_targetsBySource.containsKey(extension)) {
        _error = 'Поддерживаются только PDF, DOCX и PPTX.';
        return;
      }
      if (bytes == null || bytes.isEmpty) {
        _error = 'Не удалось прочитать файл в память.';
        return;
      }

      _selectedFile = PickedConversionFile(
        name: file.name,
        extension: extension,
        size: file.size,
        bytes: bytes,
      );
      _job = null;
      final targets = _targetsBySource[extension] ?? const <String>[];
      _targetFormat = targets.isEmpty ? null : targets.first;
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _pickingFile = false;
      notifyListeners();
    }
  }

  void setTargetFormat(String? value) {
    _targetFormat = value;
    notifyListeners();
  }

  Future<void> startConversionJob() async {
    final file = _selectedFile;
    final target = _targetFormat;
    if (file == null || target == null || !canStartJob) {
      return;
    }

    _startingJob = true;
    _error = null;
    _pollTimer?.cancel();
    notifyListeners();

    try {
      final created = await _repository.createConversionJob(
        bytes: file.bytes,
        filename: file.name,
        targetFormat: target,
      );
      _job = created;
      _historyRepository.upsertConversionJob(
        jobId: created.jobId,
        sourceFilename: file.name,
        sourceFormat: file.extension,
        targetFormat: target,
        status: created.status,
        updatedAtRaw: created.updatedAt,
        error: created.error,
        artifact: created.artifact,
        links: created.artifact == null
            ? const <String>[]
            : <String>[downloadUrlFor(created.artifact!) ?? created.artifact!.downloadUrl],
      );
      _startPolling(created.jobId);
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _startingJob = false;
      notifyListeners();
    }
  }

  String? downloadUrlFor(JobArtifact artifact) {
    final currentJob = _job;
    if (currentJob == null) {
      return null;
    }
    return _repository.conversionDownloadUri(currentJob.jobId).toString();
  }

  bool isSavingArtifact(String artifactId) => _savingArtifactIds.contains(artifactId);

  String? savedPathFor(String artifactId) {
    return _savedFilesRepository.findByArtifactId(artifactId)?.localPath;
  }

  Future<void> saveArtifact(JobArtifact artifact) async {
    final currentJob = _job;
    if (currentJob == null || _savingArtifactIds.contains(artifact.artifactId)) {
      return;
    }

    final uri = _repository.conversionDownloadUri(currentJob.jobId);
    _savingArtifactIds.add(artifact.artifactId);
    _error = null;
    notifyListeners();

    try {
      final savedEntry = await _savedFilesRepository.downloadAndStore(
        sourceType: SavedFileSourceType.conversionArtifact,
        jobId: currentJob.jobId,
        artifactId: artifact.artifactId,
        kind: artifact.kind,
        filename: artifact.filename,
        mediaType: artifact.mediaType,
        remoteUri: uri,
      );
      _historyRepository.attachConversionLocalFile(
        jobId: currentJob.jobId,
        localPath: savedEntry.localPath,
      );
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _savingArtifactIds.remove(artifact.artifactId);
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _savedFilesRepository.removeListener(_handleSavedFilesChanged);
    super.dispose();
  }

  void _startPolling(String jobId) {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      await _refreshJob(jobId);
    });
    unawaited(_refreshJob(jobId));
  }

  Future<void> _refreshJob(String jobId) async {
    try {
      final refreshed = await _repository.getConversionJob(jobId);
      _job = refreshed;
      final file = _selectedFile;
      _historyRepository.upsertConversionJob(
        jobId: refreshed.jobId,
        sourceFilename: file?.name ?? 'Файл',
        sourceFormat: file?.extension ?? 'unknown',
        targetFormat: _targetFormat ?? 'unknown',
        status: refreshed.status,
        updatedAtRaw: refreshed.updatedAt,
        error: refreshed.error,
        artifact: refreshed.artifact,
        links: refreshed.artifact == null
            ? const <String>[]
            : <String>[downloadUrlFor(refreshed.artifact!) ?? refreshed.artifact!.downloadUrl],
      );
      if (refreshed.isFinished) {
        _pollTimer?.cancel();
      }
      notifyListeners();
    } catch (error) {
      _error = _describeError(error);
      _pollTimer?.cancel();
      notifyListeners();
    }
  }

  String _describeError(Object error) {
    if (error is AppSlidesApiException) {
      return error.message;
    }
    return error.toString();
  }

  static String? _extensionFromName(String name) {
    final dot = name.lastIndexOf('.');
    if (dot < 0 || dot >= name.length - 1) {
      return null;
    }
    return name.substring(dot + 1);
  }

  void _handleSavedFilesChanged() {
    notifyListeners();
  }
}

class PickedConversionFile {
  const PickedConversionFile({
    required this.name,
    required this.extension,
    required this.size,
    required this.bytes,
  });

  final String name;
  final String extension;
  final int size;
  final Uint8List bytes;
}
