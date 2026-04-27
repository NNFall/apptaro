class OutlineResult {
  const OutlineResult({
    required this.title,
    required this.outline,
    required this.slidesTotal,
    required this.contentSlides,
  });

  final String title;
  final List<String> outline;
  final int slidesTotal;
  final int contentSlides;

  factory OutlineResult.fromJson(Map<String, dynamic> json) {
    return OutlineResult(
      title: json['title'] as String,
      outline: (json['outline'] as List<dynamic>).cast<String>(),
      slidesTotal: json['slides_total'] as int,
      contentSlides: json['content_slides'] as int,
    );
  }
}
