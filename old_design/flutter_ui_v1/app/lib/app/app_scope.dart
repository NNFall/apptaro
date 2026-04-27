import 'dart:async';

import 'package:flutter/widgets.dart';

import '../data/repositories/appslides_repository.dart';
import '../data/repositories/backend_config_repository.dart';
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

  static SavedFilesRepository savedFilesOf(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<_AppScopeInherited>();
    assert(scope != null, 'AppScope is missing above this context');
    return scope!.savedFilesRepository;
  }

  @override
  State<AppScope> createState() => _AppScopeState();
}

class _AppScopeState extends State<AppScope> {
  late final BackendConfigRepository _backendConfigRepository = BackendConfigRepository();
  late final AppSlidesRepository _repository = AppSlidesRepository(
    backendConfig: _backendConfigRepository,
  );
  late final LocalHistoryRepository _historyRepository = LocalHistoryRepository();
  late final SavedFilesRepository _savedFilesRepository = SavedFilesRepository(
    repository: _repository,
  );

  @override
  void initState() {
    super.initState();
    unawaited(_backendConfigRepository.restore());
    unawaited(_historyRepository.restore());
    unawaited(_savedFilesRepository.restore());
  }

  @override
  void dispose() {
    _backendConfigRepository.dispose();
    _savedFilesRepository.dispose();
    _historyRepository.dispose();
    _repository.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return _AppScopeInherited(
      backendConfigRepository: _backendConfigRepository,
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
    required this.historyRepository,
    required this.repository,
    required this.savedFilesRepository,
    required super.child,
  });

  final BackendConfigRepository backendConfigRepository;
  final LocalHistoryRepository historyRepository;
  final AppSlidesRepository repository;
  final SavedFilesRepository savedFilesRepository;

  @override
  bool updateShouldNotify(_AppScopeInherited oldWidget) {
    return backendConfigRepository != oldWidget.backendConfigRepository ||
        repository != oldWidget.repository ||
        historyRepository != oldWidget.historyRepository ||
        savedFilesRepository != oldWidget.savedFilesRepository;
  }
}
