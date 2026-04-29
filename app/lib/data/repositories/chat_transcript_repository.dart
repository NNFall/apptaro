import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../../domain/models/chat_transcript_entry.dart';
import '../storage/chat_transcript_store.dart';

class ChatTranscriptRepository extends ChangeNotifier {
  static const String _storageKey = 'appslides.chat.transcript.v2';
  static const String _legacyStorageKey = 'appslides.chat.transcript.v1';
  static const int _maxEntries = 250;

  final ChatTranscriptStore _store = createChatTranscriptStore(
    storageKey: _storageKey,
    legacyStorageKey: _legacyStorageKey,
  );
  final List<ChatTranscriptEntry> _entries = <ChatTranscriptEntry>[];

  bool _isLoaded = false;
  bool _isRestoring = false;
  Future<void>? _restoreFuture;
  Future<void> _persistQueue = Future<void>.value();
  String _composerModeKey = 'idle';
  ChatTranscriptTemplatePreview? _pendingTemplate;

  List<ChatTranscriptEntry> get entries =>
      List<ChatTranscriptEntry>.unmodifiable(_entries);
  bool get isLoaded => _isLoaded;
  bool get isRestoring => _isRestoring;
  String get composerModeKey => _composerModeKey;
  ChatTranscriptTemplatePreview? get pendingTemplate => _pendingTemplate;

  Future<void> restore() {
    if (_isLoaded) {
      return Future<void>.value();
    }
    if (_restoreFuture != null) {
      return _restoreFuture!;
    }

    _restoreFuture = _restoreImpl();
    return _restoreFuture!;
  }

  Future<void> _restoreImpl() async {
    _isRestoring = true;
    notifyListeners();

    try {
      final raw = await _store.read();
      if (raw == null || raw.isEmpty) {
        _entries.clear();
        _composerModeKey = 'idle';
        _pendingTemplate = null;
      } else {
        final decoded = jsonDecode(raw);
        if (decoded is List) {
          final parsedEntries = decoded
              .whereType<Map>()
              .map((item) =>
                  ChatTranscriptEntry.fromJson(item.cast<String, dynamic>()))
              .toList(growable: false);
          _applyDecodedEntries(parsedEntries);
          _composerModeKey = 'idle';
          _pendingTemplate = null;
        } else if (decoded is Map) {
          final map = decoded.cast<String, dynamic>();
          final parsedEntries = (map['entries'] as List<dynamic>? ??
                  const <dynamic>[])
              .whereType<Map>()
              .map((item) =>
                  ChatTranscriptEntry.fromJson(item.cast<String, dynamic>()))
              .toList(growable: false);
          _applyDecodedEntries(parsedEntries);
          final mode = map['composer_mode'] as String?;
          _composerModeKey = (mode == null || mode.isEmpty) ? 'idle' : mode;
          _pendingTemplate = map['pending_template'] is Map<String, dynamic>
              ? ChatTranscriptTemplatePreview.fromJson(
                  map['pending_template'] as Map<String, dynamic>,
                )
              : map['pending_template'] is Map
                  ? ChatTranscriptTemplatePreview.fromJson(
                      (map['pending_template'] as Map).cast<String, dynamic>(),
                    )
                  : null;
        } else {
          _entries.clear();
          _composerModeKey = 'idle';
          _pendingTemplate = null;
        }
      }
    } catch (_) {
      _entries.clear();
      _composerModeKey = 'idle';
      _pendingTemplate = null;
    } finally {
      _isLoaded = true;
      _isRestoring = false;
      _restoreFuture = null;
      notifyListeners();
    }
  }

  Future<void> saveSnapshot({
    required List<ChatTranscriptEntry> entries,
    required String composerModeKey,
    ChatTranscriptTemplatePreview? pendingTemplate,
  }) async {
    _entries
      ..clear()
      ..addAll(entries.take(_maxEntries));
    _composerModeKey = composerModeKey;
    _pendingTemplate = pendingTemplate;
    await _persist();
    notifyListeners();
  }

  Future<void> clear() async {
    _entries.clear();
    _composerModeKey = 'idle';
    _pendingTemplate = null;
    await _store.remove();
    notifyListeners();
  }

  Future<void> _persist() async {
    final payload = <String, dynamic>{
      'entries':
          _entries.map((entry) => entry.toJson()).toList(growable: false),
      'composer_mode': _composerModeKey,
      'pending_template': _pendingTemplate?.toJson(),
    };
    final encoded = jsonEncode(payload);
    _persistQueue = _persistQueue
        .catchError((Object _) {})
        .then((_) => _store.write(encoded));
    try {
      await _persistQueue;
    } catch (_) {
      _persistQueue = Future<void>.value();
      rethrow;
    }
  }

  void _applyDecodedEntries(List<ChatTranscriptEntry> parsedEntries) {
    _entries
      ..clear()
      ..addAll(parsedEntries);
  }
}
