import 'dart:async';

import 'package:flutter/widgets.dart';

import '../data/repositories/appslides_repository.dart';
import '../data/repositories/backend_config_repository.dart';
import '../data/repositories/chat_transcript_repository.dart';
import '../data/repositories/client_session_repository.dart';
import '../data/repositories/local_history_repository.dart';
import '../data/repositories/saved_files_repository.dart';

class AppScope extends StatefulWidget {
  const AppScope({
    super.key,
    required this.child,
  });

  final Widget child;

  static AppSlidesRepository repositoryOf(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<_AppScopeInherited>();
    assert(scope != null, 'AppScope is missing above this context');
    return scope!.repository;
  }

  static LocalHistoryRepository historyOf(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<_AppScopeInherited>();
    assert(scope != null, 'AppScope is missing above this context');
    return scope!.historyRepository;
  }

  static BackendConfigRepository backendConfigOf(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<_AppScopeInherited>();
    assert(scope != null, 'AppScope is missing above this context');
    return scope!.backendConfigRepository;
  }

  static ClientSessionRepository clientSessionOf(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<_AppScopeInherited>();
    assert(scope != null, 'AppScope is missing above this context');
    return scope!.clientSessionRepository;
  }

  static SavedFilesRepository savedFilesOf(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<_AppScopeInherited>();
    assert(scope != null, 'AppScope is missing above this context');
    return scope!.savedFilesRepository;
  }

  static ChatTranscriptRepository transcriptOf(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<_AppScopeInherited>();
    assert(scope != null, 'AppScope is missing above this context');
    return scope!.chatTranscriptRepository;
  }

  @override
  State<AppScope> createState() => _AppScopeState();
}

class _AppScopeState extends State<AppScope> {
  late final BackendConfigRepository _backendConfigRepository = BackendConfigRepository();
  late final ClientSessionRepository _clientSessionRepository =
      ClientSessionRepository();
  late final AppSlidesRepository _repository = AppSlidesRepository(
    backendConfig: _backendConfigRepository,
    clientSession: _clientSessionRepository,
  );
  late final LocalHistoryRepository _historyRepository = LocalHistoryRepository();
  late final SavedFilesRepository _savedFilesRepository = SavedFilesRepository(
    repository: _repository,
  );
  late final ChatTranscriptRepository _chatTranscriptRepository =
      ChatTranscriptRepository();

  @override
  void initState() {
    super.initState();
    unawaited(_backendConfigRepository.restore());
    unawaited(_clientSessionRepository.restore());
    unawaited(_historyRepository.restore());
    unawaited(_savedFilesRepository.restore());
    unawaited(_chatTranscriptRepository.restore());
  }

  @override
  void dispose() {
    _backendConfigRepository.dispose();
    _clientSessionRepository.dispose();
    _savedFilesRepository.dispose();
    _historyRepository.dispose();
    _chatTranscriptRepository.dispose();
    _repository.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return _AppScopeInherited(
      backendConfigRepository: _backendConfigRepository,
      chatTranscriptRepository: _chatTranscriptRepository,
      clientSessionRepository: _clientSessionRepository,
      historyRepository: _historyRepository,
      repository: _repository,
      savedFilesRepository: _savedFilesRepository,
      child: widget.child,
    );
  }
}

class _AppScopeInherited extends InheritedWidget {
  const _AppScopeInherited({
    required this.backendConfigRepository,
    required this.chatTranscriptRepository,
    required this.clientSessionRepository,
    required this.historyRepository,
    required this.repository,
    required this.savedFilesRepository,
    required super.child,
  });

  final BackendConfigRepository backendConfigRepository;
  final ChatTranscriptRepository chatTranscriptRepository;
  final ClientSessionRepository clientSessionRepository;
  final LocalHistoryRepository historyRepository;
  final AppSlidesRepository repository;
  final SavedFilesRepository savedFilesRepository;

  @override
  bool updateShouldNotify(_AppScopeInherited oldWidget) {
    return backendConfigRepository != oldWidget.backendConfigRepository ||
        chatTranscriptRepository != oldWidget.chatTranscriptRepository ||
        clientSessionRepository != oldWidget.clientSessionRepository ||
        repository != oldWidget.repository ||
        historyRepository != oldWidget.historyRepository ||
        savedFilesRepository != oldWidget.savedFilesRepository;
  }
}
