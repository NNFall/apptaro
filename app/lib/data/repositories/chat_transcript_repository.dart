import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../domain/models/chat_transcript_entry.dart';

class ChatTranscriptRepository extends ChangeNotifier {
  static const String _storageKey = 'appslides.chat.transcript.v1';
  static const int _maxEntries = 250;
  static final RegExp _mojibakePattern = RegExp(
    r'рџ|в[њљ†Ђ™]|(?:Р.|С.){2,}|[ЃЉЊЎџћќўї]',
  );

  final SharedPreferencesAsync _storage = SharedPreferencesAsync();
  final List<ChatTranscriptEntry> _entries = <ChatTranscriptEntry>[];

  bool _isLoaded = false;
  bool _isRestoring = false;

  List<ChatTranscriptEntry> get entries =>
      List<ChatTranscriptEntry>.unmodifiable(_entries);
  bool get isLoaded => _isLoaded;
  bool get isRestoring => _isRestoring;

  Future<void> restore() async {
    if (_isLoaded || _isRestoring) {
      return;
    }

    _isRestoring = true;
    notifyListeners();

    try {
      final raw = await _storage.getString(_storageKey);
      if (raw == null || raw.isEmpty) {
        _entries.clear();
      } else {
        final decoded = jsonDecode(raw);
        if (decoded is List) {
          final parsedEntries = decoded
              .whereType<Map>()
              .map((item) =>
                  ChatTranscriptEntry.fromJson(item.cast<String, dynamic>()))
              .toList(growable: false);

          if (parsedEntries.any(_containsMojibake)) {
            _entries.clear();
            await _storage.remove(_storageKey);
          } else {
            _entries
              ..clear()
              ..addAll(parsedEntries);
          }
        }
      }
    } catch (_) {
      _entries.clear();
    } finally {
      _isLoaded = true;
      _isRestoring = false;
      notifyListeners();
    }
  }

  Future<void> replaceAll(List<ChatTranscriptEntry> entries) async {
    _entries
      ..clear()
      ..addAll(entries.take(_maxEntries));
    await _persist();
    notifyListeners();
  }

  Future<void> clear() async {
    _entries.clear();
    await _storage.remove(_storageKey);
    notifyListeners();
  }

  Future<void> _persist() async {
    final payload = _entries.map((entry) => entry.toJson()).toList();
    await _storage.setString(_storageKey, jsonEncode(payload));
  }

  bool _containsMojibake(ChatTranscriptEntry entry) {
    if (_looksMojibake(entry.text)) {
      return true;
    }

    return entry.attachments.any(
      (attachment) =>
          _looksMojibake(attachment.filename) ||
          _looksMojibake(attachment.caption),
    );
  }

  bool _looksMojibake(String value) {
    if (value.isEmpty) {
      return false;
    }
    return _mojibakePattern.hasMatch(value);
  }
}
