enum HistoryEntryType {
  outline,
  presentationJob,
  conversionJob,
}

enum HistoryEntryStatus {
  info,
  queued,
  running,
  succeeded,
  failed,
}

class HistoryEntry {
  const HistoryEntry({
    required this.id,
    required this.type,
    required this.status,
    required this.title,
    required this.subtitle,
    required this.details,
    required this.createdAt,
    required this.updatedAt,
    this.links = const <String>[],
  });

  final String id;
  final HistoryEntryType type;
  final HistoryEntryStatus status;
  final String title;
  final String subtitle;
  final String details;
  final DateTime createdAt;
  final DateTime updatedAt;
  final List<String> links;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'type': type.name,
      'status': status.name,
      'title': title,
      'subtitle': subtitle,
      'details': details,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'links': links,
    };
  }

  factory HistoryEntry.fromJson(Map<String, dynamic> json) {
    return HistoryEntry(
      id: json['id'] as String? ?? '',
      type: _parseType(json['type'] as String?),
      status: _parseStatus(json['status'] as String?),
      title: json['title'] as String? ?? 'Без названия',
      subtitle: json['subtitle'] as String? ?? '',
      details: json['details'] as String? ?? '',
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ?? DateTime.now(),
      links: (json['links'] as List<dynamic>? ?? const <dynamic>[]).cast<String>(),
    );
  }

  HistoryEntry copyWith({
    HistoryEntryType? type,
    HistoryEntryStatus? status,
    String? title,
    String? subtitle,
    String? details,
    DateTime? createdAt,
    DateTime? updatedAt,
    List<String>? links,
  }) {
    return HistoryEntry(
      id: id,
      type: type ?? this.type,
      status: status ?? this.status,
      title: title ?? this.title,
      subtitle: subtitle ?? this.subtitle,
      details: details ?? this.details,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      links: links ?? this.links,
    );
  }

  static HistoryEntryType _parseType(String? value) {
    switch (value) {
      case 'outline':
        return HistoryEntryType.outline;
      case 'presentationJob':
        return HistoryEntryType.presentationJob;
      case 'conversionJob':
        return HistoryEntryType.conversionJob;
      default:
        return HistoryEntryType.outline;
    }
  }

  static HistoryEntryStatus _parseStatus(String? value) {
    switch (value) {
      case 'info':
        return HistoryEntryStatus.info;
      case 'queued':
        return HistoryEntryStatus.queued;
      case 'running':
        return HistoryEntryStatus.running;
      case 'succeeded':
        return HistoryEntryStatus.succeeded;
      case 'failed':
        return HistoryEntryStatus.failed;
      default:
        return HistoryEntryStatus.info;
    }
  }
}
