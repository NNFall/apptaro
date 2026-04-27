enum SavedFileSourceType {
  presentationArtifact,
  conversionArtifact,
}

class SavedFileEntry {
  const SavedFileEntry({
    required this.id,
    required this.sourceType,
    required this.jobId,
    required this.artifactId,
    required this.kind,
    required this.filename,
    required this.mediaType,
    required this.remoteUrl,
    required this.localPath,
    required this.sizeBytes,
    required this.savedAt,
  });

  final String id;
  final SavedFileSourceType sourceType;
  final String jobId;
  final String artifactId;
  final String kind;
  final String filename;
  final String mediaType;
  final String remoteUrl;
  final String localPath;
  final int sizeBytes;
  final DateTime savedAt;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'source_type': sourceType.name,
      'job_id': jobId,
      'artifact_id': artifactId,
      'kind': kind,
      'filename': filename,
      'media_type': mediaType,
      'remote_url': remoteUrl,
      'local_path': localPath,
      'size_bytes': sizeBytes,
      'saved_at': savedAt.toIso8601String(),
    };
  }

  factory SavedFileEntry.fromJson(Map<String, dynamic> json) {
    return SavedFileEntry(
      id: json['id'] as String? ?? '',
      sourceType: _parseSourceType(json['source_type'] as String?),
      jobId: json['job_id'] as String? ?? '',
      artifactId: json['artifact_id'] as String? ?? '',
      kind: json['kind'] as String? ?? 'file',
      filename: json['filename'] as String? ?? 'file',
      mediaType: json['media_type'] as String? ?? 'application/octet-stream',
      remoteUrl: json['remote_url'] as String? ?? '',
      localPath: json['local_path'] as String? ?? '',
      sizeBytes: json['size_bytes'] as int? ?? 0,
      savedAt: DateTime.tryParse(json['saved_at'] as String? ?? '') ?? DateTime.now(),
    );
  }

  static SavedFileSourceType _parseSourceType(String? value) {
    switch (value) {
      case 'presentationArtifact':
        return SavedFileSourceType.presentationArtifact;
      case 'conversionArtifact':
        return SavedFileSourceType.conversionArtifact;
      default:
        return SavedFileSourceType.presentationArtifact;
    }
  }
}
