import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../data/api/appslides_api_client.dart';
import '../../data/repositories/appslides_repository.dart';
import '../../data/repositories/local_history_repository.dart';
import '../../data/repositories/saved_files_repository.dart';
import '../../domain/models/job_artifact.dart';
import '../../domain/models/outline_result.dart';
import '../../domain/models/presentation_template.dart';
import '../../domain/models/remote_job.dart';
import '../../domain/models/saved_file_entry.dart';

class PresentationController extends ChangeNotifier {
  PresentationController({
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

  final List<int> slideOptions = const <int>[4, 5, 6, 7, 8, 9, 10];

  List<PresentationTemplate> _templates = const <PresentationTemplate>[];
  String _topic = '';
  int _slidesTotal = 7;
  String _title = '';
  List<String> _outline = const <String>[];
  int? _selectedDesignId;
  bool _generatePdf = true;
  bool _loadingTemplates = false;
  bool _generatingOutline = false;
  bool _revisingOutline = false;
  bool _startingJob = false;
  String? _error;
  RemoteJob? _job;
  final Set<String> _savingArtifactIds = <String>{};
  Timer? _pollTimer;

  List<PresentationTemplate> get templates => _templates;
  String get topic => _topic;
  int get slidesTotal => _slidesTotal;
  String get title => _title;
  List<String> get outline => _outline;
  int? get selectedDesignId => _selectedDesignId;
  bool get generatePdf => _generatePdf;
  bool get loadingTemplates => _loadingTemplates;
  bool get generatingOutline => _generatingOutline;
  bool get revisingOutline => _revisingOutline;
  bool get startingJob => _startingJob;
  String? get error => _error;
  RemoteJob? get job => _job;

  bool get canGenerateOutline => _topic.trim().length >= 3 && !_generatingOutline;
  bool get hasOutline => _outline.isNotEmpty && _title.trim().isNotEmpty;
  bool get canStartJob =>
      hasOutline && _selectedDesignId != null && !_startingJob && !_isJobActive;
  bool get _isJobActive =>
      _job != null &&
      (_job!.status == RemoteJobStatus.queued || _job!.status == RemoteJobStatus.running);

  Future<void> initialize() async {
    if (_templates.isNotEmpty || _loadingTemplates) {
      return;
    }
    await refreshTemplates();
  }

  Future<void> refreshTemplates() async {
    _loadingTemplates = true;
    _error = null;
    notifyListeners();

    try {
      final items = await _repository.fetchTemplates();
      _templates = items;
      _selectedDesignId ??= _firstAvailableDesignId(items);
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _loadingTemplates = false;
      notifyListeners();
    }
  }

  void setTopic(String value) {
    _topic = value;
    notifyListeners();
  }

  void setSlidesTotal(int value) {
    _slidesTotal = value;
    notifyListeners();
  }

  void setTitle(String value) {
    _title = value;
    notifyListeners();
  }

  void setGeneratePdf(bool value) {
    _generatePdf = value;
    notifyListeners();
  }

  void selectDesign(int designId) {
    _selectedDesignId = designId;
    notifyListeners();
  }

  void updateOutlineItem(int index, String value) {
    if (index < 0 || index >= _outline.length) {
      return;
    }
    final updated = List<String>.from(_outline);
    updated[index] = value;
    _outline = updated;
    notifyListeners();
  }

  Future<void> generateOutline() async {
    if (!canGenerateOutline) {
      return;
    }

    _generatingOutline = true;
    _error = null;
    notifyListeners();

    try {
      final result = await _repository.generateOutline(
        topic: _topic.trim(),
        slidesTotal: _slidesTotal,
      );
      _applyOutlineResult(result);
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _generatingOutline = false;
      notifyListeners();
    }
  }

  Future<void> reviseOutline(String comment) async {
    if (!hasOutline || comment.trim().isEmpty || _revisingOutline) {
      return;
    }

    _revisingOutline = true;
    _error = null;
    notifyListeners();

    try {
      final result = await _repository.reviseOutline(
        topic: _topic.trim(),
        slidesTotal: _slidesTotal,
        outline: _outline,
        comment: comment.trim(),
        title: _title.trim(),
      );
      _applyOutlineResult(result);
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _revisingOutline = false;
      notifyListeners();
    }
  }

  Future<void> startPresentationJob() async {
    if (!canStartJob) {
      return;
    }

    _startingJob = true;
    _error = null;
    _pollTimer?.cancel();
    notifyListeners();

    try {
      final created = await _repository.createPresentationJob(
        topic: _topic.trim(),
        title: _title.trim(),
        outline: _outline.where((item) => item.trim().isNotEmpty).toList(),
        designId: _selectedDesignId!,
        generatePdf: _generatePdf,
      );
      _job = created;
      _startPolling(created.jobId);
    } catch (error) {
      _error = _describeError(error);
    } finally {
      _startingJob = false;
      notifyListeners();
    }
  }

  Uri? downloadUriFor(JobArtifact artifact) {
    final currentJob = _job;
    if (currentJob == null) {
      return null;
    }
    if (artifact.kind == 'pptx' || artifact.kind == 'pdf') {
      return _repository.presentationDownloadUri(
        currentJob.jobId,
        format: artifact.kind,
      );
    }
    return null;
  }

  String? downloadUrlFor(JobArtifact artifact) => downloadUriFor(artifact)?.toString();

  bool isSavingArtifact(String artifactId) => _savingArtifactIds.contains(artifactId);

  String? savedPathFor(String artifactId) {
    return _savedFilesRepository.findByArtifactId(artifactId)?.localPath;
  }

  Future<void> saveArtifact(JobArtifact artifact) async {
    final currentJob = _job;
    final uri = downloadUriFor(artifact);
    if (currentJob == null || uri == null || _savingArtifactIds.contains(artifact.artifactId)) {
      return;
    }

    _savingArtifactIds.add(artifact.artifactId);
    _error = null;
    notifyListeners();

    try {
      final savedEntry = await _savedFilesRepository.downloadAndStore(
        sourceType: SavedFileSourceType.presentationArtifact,
        jobId: currentJob.jobId,
        artifactId: artifact.artifactId,
        kind: artifact.kind,
        filename: artifact.filename,
        mediaType: artifact.mediaType,
        remoteUri: uri,
      );
      _historyRepository.attachPresentationLocalFile(
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

  void _applyOutlineResult(OutlineResult result) {
    _title = result.title;
    _outline = List<String>.from(result.outline);
    _historyRepository.recordOutline(
      topic: _topic.trim(),
      title: result.title,
      slidesTotal: result.slidesTotal,
      outlineItems: result.outline.length,
    );
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
      final refreshed = await _repository.getPresentationJob(jobId);
      _job = refreshed;
      _historyRepository.upsertPresentationJob(
        jobId: refreshed.jobId,
        title: _title.trim().isEmpty ? 'Без названия' : _title.trim(),
        designId: _selectedDesignId,
        status: refreshed.status,
        updatedAtRaw: refreshed.updatedAt,
        error: refreshed.error,
        artifacts: refreshed.artifacts,
        links: refreshed.artifacts
            .map((artifact) => downloadUrlFor(artifact) ?? artifact.downloadUrl)
            .where((value) => value.isNotEmpty)
            .toList(),
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

  int? _firstAvailableDesignId(List<PresentationTemplate> items) {
    for (final item in items) {
      if (item.templateAvailable) {
        return item.id;
      }
    }
    return null;
  }

  String _describeError(Object error) {
    if (error is AppSlidesApiException) {
      return error.message;
    }
    return error.toString();
  }

  void _handleSavedFilesChanged() {
    notifyListeners();
  }
}
