import 'presentation_template.dart';
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
    this.keyboard = const <List<ChatTranscriptAction>>[],
    this.attachments = const <ChatTranscriptAttachment>[],
    this.templatePreviewTemplates = const <ChatTranscriptTemplatePreview>[],
    this.linkPreview,
  });

  final String id;
  final ChatTranscriptSender sender;
  final String text;
  final DateTime sentAt;
  final List<List<ChatTranscriptAction>> keyboard;
  final List<ChatTranscriptAttachment> attachments;
  final List<ChatTranscriptTemplatePreview> templatePreviewTemplates;
  final ChatTranscriptLinkPreview? linkPreview;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'sender': sender.name,
      'text': text,
      'sent_at': sentAt.toIso8601String(),
      'keyboard': keyboard
          .map((row) => row.map((item) => item.toJson()).toList(growable: false))
          .toList(growable: false),
      'attachments': attachments.map((item) => item.toJson()).toList(),
      'template_preview_templates': templatePreviewTemplates
          .map((item) => item.toJson())
          .toList(growable: false),
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
      keyboard: (json['keyboard'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<List>()
          .map(
            (row) => row
                .whereType<Map>()
                .map((item) => ChatTranscriptAction.fromJson(item.cast<String, dynamic>()))
                .toList(growable: false),
          )
          .toList(growable: false),
      attachments: (json['attachments'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map>()
          .map((item) =>
              ChatTranscriptAttachment.fromJson(item.cast<String, dynamic>()))
          .toList(growable: false),
      templatePreviewTemplates:
          (json['template_preview_templates'] as List<dynamic>? ??
                  const <dynamic>[])
              .whereType<Map>()
              .map(
                (item) => ChatTranscriptTemplatePreview.fromJson(
                  item.cast<String, dynamic>(),
                ),
              )
              .toList(growable: false),
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

class ChatTranscriptAction {
  const ChatTranscriptAction({
    required this.label,
    required this.actionKey,
    required this.showAsUserMessage,
    this.payload = const <String, dynamic>{},
  });

  final String label;
  final String actionKey;
  final bool showAsUserMessage;
  final Map<String, dynamic> payload;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'label': label,
      'action_key': actionKey,
      'show_as_user_message': showAsUserMessage,
      'payload': payload,
    };
  }

  factory ChatTranscriptAction.fromJson(Map<String, dynamic> json) {
    return ChatTranscriptAction(
      label: json['label'] as String? ?? '',
      actionKey: json['action_key'] as String? ?? '',
      showAsUserMessage: json['show_as_user_message'] as bool? ?? true,
      payload: json['payload'] is Map<String, dynamic>
          ? json['payload'] as Map<String, dynamic>
          : json['payload'] is Map
              ? (json['payload'] as Map).cast<String, dynamic>()
              : const <String, dynamic>{},
    );
  }
}

class ChatTranscriptTemplatePreview {
  const ChatTranscriptTemplatePreview({
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

  factory ChatTranscriptTemplatePreview.fromPresentationTemplate(
    PresentationTemplate template,
  ) {
    return ChatTranscriptTemplatePreview(
      id: template.id,
      name: template.name,
      templatePath: template.templatePath,
      previewPath: template.previewPath,
      templateAvailable: template.templateAvailable,
      previewAvailable: template.previewAvailable,
    );
  }

  PresentationTemplate toPresentationTemplate() {
    return PresentationTemplate(
      id: id,
      name: name,
      templatePath: templatePath,
      previewPath: previewPath,
      templateAvailable: templateAvailable,
      previewAvailable: previewAvailable,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'name': name,
      'template_path': templatePath,
      'preview_path': previewPath,
      'template_available': templateAvailable,
      'preview_available': previewAvailable,
    };
  }

  factory ChatTranscriptTemplatePreview.fromJson(Map<String, dynamic> json) {
    return ChatTranscriptTemplatePreview(
      id: json['id'] as int? ?? 0,
      name: json['name'] as String? ?? '',
      templatePath: json['template_path'] as String?,
      previewPath: json['preview_path'] as String?,
      templateAvailable: json['template_available'] as bool? ?? false,
      previewAvailable: json['preview_available'] as bool? ?? false,
    );
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
