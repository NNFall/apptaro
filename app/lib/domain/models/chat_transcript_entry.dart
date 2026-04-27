import 'saved_file_entry.dart';

enum ChatTranscriptSender {
  bot,
  user,
}

class ChatTranscriptEntry {
  const ChatTranscriptEntry({
    required this.id,
    required this.sender,
    required this.text,
    required this.sentAt,
    this.attachments = const <ChatTranscriptAttachment>[],
    this.linkPreview,
  });

  final String id;
  final ChatTranscriptSender sender;
  final String text;
  final DateTime sentAt;
  final List<ChatTranscriptAttachment> attachments;
  final ChatTranscriptLinkPreview? linkPreview;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'sender': sender.name,
      'text': text,
      'sent_at': sentAt.toIso8601String(),
      'attachments': attachments.map((item) => item.toJson()).toList(),
      'link_preview': linkPreview?.toJson(),
    };
  }

  factory ChatTranscriptEntry.fromJson(Map<String, dynamic> json) {
    return ChatTranscriptEntry(
      id: json['id'] as String? ?? '',
      sender: _parseSender(json['sender'] as String?),
      text: json['text'] as String? ?? '',
      sentAt:
          DateTime.tryParse(json['sent_at'] as String? ?? '') ?? DateTime.now(),
      attachments: (json['attachments'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map>()
          .map((item) =>
              ChatTranscriptAttachment.fromJson(item.cast<String, dynamic>()))
          .toList(),
      linkPreview: json['link_preview'] is Map<String, dynamic>
          ? ChatTranscriptLinkPreview.fromJson(
              json['link_preview'] as Map<String, dynamic>,
            )
          : json['link_preview'] is Map
              ? ChatTranscriptLinkPreview.fromJson(
                  (json['link_preview'] as Map).cast<String, dynamic>(),
                )
              : null,
    );
  }

  static ChatTranscriptSender _parseSender(String? value) {
    switch (value) {
      case 'user':
        return ChatTranscriptSender.user;
      case 'bot':
      default:
        return ChatTranscriptSender.bot;
    }
  }
}

class ChatTranscriptLinkPreview {
  const ChatTranscriptLinkPreview({
    required this.domain,
    required this.title,
    required this.description,
    required this.url,
  });

  final String domain;
  final String title;
  final String description;
  final String url;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'domain': domain,
      'title': title,
      'description': description,
      'url': url,
    };
  }

  factory ChatTranscriptLinkPreview.fromJson(Map<String, dynamic> json) {
    return ChatTranscriptLinkPreview(
      domain: json['domain'] as String? ?? '',
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      url: json['url'] as String? ?? '',
    );
  }
}

class ChatTranscriptAttachment {
  const ChatTranscriptAttachment({
    required this.jobId,
    required this.artifactId,
    required this.filename,
    required this.kind,
    required this.mediaType,
    required this.remoteUrl,
    required this.sourceType,
    required this.caption,
  });

  final String jobId;
  final String artifactId;
  final String filename;
  final String kind;
  final String mediaType;
  final String remoteUrl;
  final SavedFileSourceType sourceType;
  final String caption;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'job_id': jobId,
      'artifact_id': artifactId,
      'filename': filename,
      'kind': kind,
      'media_type': mediaType,
      'remote_url': remoteUrl,
      'source_type': sourceType.name,
      'caption': caption,
    };
  }

  factory ChatTranscriptAttachment.fromJson(Map<String, dynamic> json) {
    return ChatTranscriptAttachment(
      jobId: json['job_id'] as String? ?? '',
      artifactId: json['artifact_id'] as String? ?? '',
      filename: json['filename'] as String? ?? 'file',
      kind: json['kind'] as String? ?? 'file',
      mediaType: json['media_type'] as String? ?? 'application/octet-stream',
      remoteUrl: json['remote_url'] as String? ?? '',
      sourceType: _parseSourceType(json['source_type'] as String?),
      caption: json['caption'] as String? ?? 'Файл',
    );
  }

  static SavedFileSourceType _parseSourceType(String? value) {
    switch (value) {
      case 'conversionArtifact':
        return SavedFileSourceType.conversionArtifact;
      case 'presentationArtifact':
      default:
        return SavedFileSourceType.presentationArtifact;
    }
  }
}
