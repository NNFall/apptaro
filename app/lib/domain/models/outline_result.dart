import 'job_artifact.dart';

class OutlineResult {
  const OutlineResult({
    required this.title,
    required this.outline,
    required this.slidesTotal,
    required this.contentSlides,
    required this.teaserMode,
    required this.teaserText,
    required this.teaserArtifacts,
  });

  final String title;
  final List<String> outline;
  final int slidesTotal;
  final int contentSlides;
  final bool teaserMode;
  final String? teaserText;
  final List<JobArtifact> teaserArtifacts;

  factory OutlineResult.fromJson(Map<String, dynamic> json) {
    final rawTeaserArtifacts =
        json['teaser_artifacts'] as List<dynamic>? ?? const <dynamic>[];
    return OutlineResult(
      title: json['title'] as String,
      outline: (json['outline'] as List<dynamic>).cast<String>(),
      slidesTotal: json['slides_total'] as int,
      contentSlides: json['content_slides'] as int,
      teaserMode: json['teaser_mode'] == true,
      teaserText: json['teaser_text'] as String?,
      teaserArtifacts: rawTeaserArtifacts
          .whereType<Map>()
          .map((item) => JobArtifact.fromJson(item.cast<String, dynamic>()))
          .toList(growable: false),
    );
  }
}
