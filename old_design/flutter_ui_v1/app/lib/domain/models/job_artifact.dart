class JobArtifact {
  const JobArtifact({
    required this.artifactId,
    required this.kind,
    required this.filename,
    required this.mediaType,
    required this.downloadUrl,
  });

  final String artifactId;
  final String kind;
  final String filename;
  final String mediaType;
  final String downloadUrl;

  factory JobArtifact.fromJson(Map<String, dynamic> json) {
    return JobArtifact(
      artifactId: json['artifact_id'] as String,
      kind: json['kind'] as String,
      filename: json['filename'] as String,
      mediaType: json['media_type'] as String,
      downloadUrl: json['download_url'] as String,
    );
  }
}
