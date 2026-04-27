import 'job_artifact.dart';

enum RemoteJobStatus {
  queued,
  running,
  succeeded,
  failed,
  unknown,
}

class RemoteJob {
  const RemoteJob({
    required this.jobId,
    required this.jobType,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
    required this.error,
    required this.result,
  });

  final String jobId;
  final String jobType;
  final RemoteJobStatus status;
  final String createdAt;
  final String updatedAt;
  final String? error;
  final Map<String, dynamic>? result;

  bool get isFinished =>
      status == RemoteJobStatus.succeeded || status == RemoteJobStatus.failed;

  bool get isSuccessful => status == RemoteJobStatus.succeeded;

  factory RemoteJob.fromJson(Map<String, dynamic> json) {
    final rawResult = json['result'];
    return RemoteJob(
      jobId: json['job_id'] as String,
      jobType: json['job_type'] as String,
      status: _parseStatus(json['status'] as String?),
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
      error: json['error'] as String?,
      result: rawResult is Map<String, dynamic>
          ? rawResult
          : rawResult is Map
              ? rawResult.cast<String, dynamic>()
              : null,
    );
  }

  List<JobArtifact> get artifacts {
    final rawArtifacts = result?['artifacts'];
    if (rawArtifacts is! List) {
      return const <JobArtifact>[];
    }
    return rawArtifacts
        .whereType<Map>()
        .map((item) => JobArtifact.fromJson(item.cast<String, dynamic>()))
        .toList();
  }

  JobArtifact? get artifact {
    final rawArtifact = result?['artifact'];
    if (rawArtifact is Map<String, dynamic>) {
      return JobArtifact.fromJson(rawArtifact);
    }
    if (rawArtifact is Map) {
      return JobArtifact.fromJson(rawArtifact.cast<String, dynamic>());
    }
    return null;
  }

  static RemoteJobStatus _parseStatus(String? value) {
    switch (value) {
      case 'queued':
        return RemoteJobStatus.queued;
      case 'running':
        return RemoteJobStatus.running;
      case 'succeeded':
        return RemoteJobStatus.succeeded;
      case 'failed':
        return RemoteJobStatus.failed;
      default:
        return RemoteJobStatus.unknown;
    }
  }
}
