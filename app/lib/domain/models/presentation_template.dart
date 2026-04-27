class PresentationTemplate {
  const PresentationTemplate({
    required this.id,
    required this.name,
    required this.templatePath,
    required this.previewPath,
    required this.templateAvailable,
    required this.previewAvailable,
  });

  final int id;
  final String name;
  final String? templatePath;
  final String? previewPath;
  final bool templateAvailable;
  final bool previewAvailable;

  factory PresentationTemplate.fromJson(Map<String, dynamic> json) {
    return PresentationTemplate(
      id: json['id'] as int,
      name: json['name'] as String,
      templatePath: json['template_path'] as String?,
      previewPath: json['preview_path'] as String?,
      templateAvailable: json['template_available'] as bool,
      previewAvailable: json['preview_available'] as bool,
    );
  }
}
