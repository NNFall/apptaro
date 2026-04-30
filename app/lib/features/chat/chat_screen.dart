import 'dart:async';
import 'dart:math' as math;

import 'package:app_links/app_links.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/app_scope.dart';
import '../../core/config/app_config.dart';
import '../../data/repositories/backend_config_repository.dart';
import '../../data/repositories/chat_transcript_repository.dart';
import '../../data/repositories/client_session_repository.dart';
import '../../data/repositories/local_history_repository.dart';
import '../../data/repositories/saved_files_repository.dart';
import '../../domain/models/billing_payment.dart';
import '../../domain/models/billing_plan.dart';
import '../../domain/models/billing_summary.dart';
import '../../domain/models/chat_transcript_entry.dart';
import '../../domain/models/job_artifact.dart';
import '../../domain/models/presentation_template.dart';
import '../../domain/models/remote_job.dart';
import '../../domain/models/saved_file_entry.dart';
import '../billing/billing_controller.dart';
import '../converter/converter_controller.dart';
import '../presentation/presentation_controller.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with WidgetsBindingObserver {
  final TextEditingController _composerController = TextEditingController();
  final FocusNode _composerFocusNode = FocusNode();
  final ScrollController _scrollController = ScrollController();
  final List<_ChatMessage> _messages = <_ChatMessage>[];
  final Set<String> _savingAttachmentIds = <String>{};

  PresentationController? _presentationController;
  ConverterController? _converterController;
  BillingController? _billingController;
  BackendConfigRepository? _backendConfigRepository;
  ChatTranscriptRepository? _chatTranscriptRepository;
  ClientSessionRepository? _clientSessionRepository;
  LocalHistoryRepository? _historyRepository;
  SavedFilesRepository? _savedFilesRepository;

  _ComposerMode _composerMode = _ComposerMode.idle;
  bool _didSeedConversation = false;
  bool _didRestoreTranscript = false;
  bool _didInitializeDeepLinks = false;
  bool _billingReturnInFlight = false;
  int _messageCounter = 0;
  StreamSubscription<Uri>? _deepLinkSubscription;
  String? _lastHandledBillingReturnKey;
  String? _lastPresentationOutlineKey;
  String? _lastPresentationError;
  String? _lastPresentationStatusKey;
  String? _lastPresentationResultKey;
  String? _lastConverterError;
  String? _lastConverterStatusKey;
  String? _lastConverterResultKey;
  String? _lastBillingPaymentStatusKey;
  String? _lastBillingTimeoutPaymentId;
  String? _outlineProgressMessageId;
  String? _renderPreparationMessageId;
  String? _presentationStatusMessageId;
  String? _billingProgressMessageId;
  PresentationTemplate? _pendingTemplateAfterPayment;
  bool _resumingPresentationAfterPayment = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_presentationController != null) {
      return;
    }

    _backendConfigRepository = AppScope.backendConfigOf(context);
    _chatTranscriptRepository = AppScope.transcriptOf(context);
    _clientSessionRepository = AppScope.clientSessionOf(context);
    _historyRepository = AppScope.historyOf(context);
    _savedFilesRepository = AppScope.savedFilesOf(context);

    _presentationController = PresentationController(
      repository: AppScope.repositoryOf(context),
      historyRepository: _historyRepository!,
      savedFilesRepository: _savedFilesRepository!,
    )..initialize();
    _converterController = ConverterController(
      repository: AppScope.repositoryOf(context),
      historyRepository: _historyRepository!,
      savedFilesRepository: _savedFilesRepository!,
    );
    _billingController = BillingController(
      repository: AppScope.repositoryOf(context),
    )..initialize();

    _presentationController!.addListener(_handlePresentationUpdates);
    _converterController!.addListener(_handleConverterUpdates);
    _billingController!.addListener(_handleBillingUpdates);
    _backendConfigRepository!.addListener(_handleExternalStateChanged);
    _chatTranscriptRepository!.addListener(_handleExternalStateChanged);
    _historyRepository!.addListener(_handleExternalStateChanged);
    _savedFilesRepository!.addListener(_handleExternalStateChanged);

    if (!_didInitializeDeepLinks) {
      _didInitializeDeepLinks = true;
      unawaited(_initializeIncomingLinks());
    }

    unawaited(_restoreTranscript());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _presentationController?.removeListener(_handlePresentationUpdates);
    _presentationController?.dispose();
    _converterController?.removeListener(_handleConverterUpdates);
    _converterController?.dispose();
    _billingController?.removeListener(_handleBillingUpdates);
    _billingController?.dispose();
    _backendConfigRepository?.removeListener(_handleExternalStateChanged);
    _chatTranscriptRepository?.removeListener(_handleExternalStateChanged);
    _historyRepository?.removeListener(_handleExternalStateChanged);
    _savedFilesRepository?.removeListener(_handleExternalStateChanged);
    _deepLinkSubscription?.cancel();
    _composerController.dispose();
    _composerFocusNode.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_refreshAfterAppResume());
      return;
    }

    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      unawaited(_persistTranscript());
      return;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_presentationController == null || _converterController == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return Scaffold(
      body: Stack(
        children: [
          const _TelegramBackdrop(),
          SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final contentWidth =
                    constraints.maxWidth >= 760 ? 560.0 : constraints.maxWidth;
                return Align(
                  alignment: Alignment.topCenter,
                  child: SizedBox(
                    width: contentWidth,
                    child: Column(
                      children: [
                        const _ChatHeader(),
                        Expanded(
                          child: ListView.builder(
                            controller: _scrollController,
                            padding: const EdgeInsets.fromLTRB(10, 8, 10, 18),
                            itemCount: _messages.length,
                            itemBuilder: (context, index) {
                              final message = _messages[index];
                              return Padding(
                                padding: const EdgeInsets.only(bottom: 10),
                                child: _ChatMessageCard(
                                  message: message,
                                  savedFilesRepository: _savedFilesRepository!,
                                  busyAttachmentIds: _savingAttachmentIds,
                                  onActionTap: _runAction,
                                  onAttachmentTap: _handleAttachmentTap,
                                  onAttachmentDeleteTap:
                                      _handleAttachmentDelete,
                                ),
                              );
                            },
                          ),
                        ),
                        _ComposerBar(
                          controller: _composerController,
                          focusNode: _composerFocusNode,
                          mode: _composerMode,
                          onMenuPressed: () => unawaited(_runAction(
                            _ChatAction(
                              label: '🏠 Главное меню',
                              onTap: _showMainMenu,
                              showAsUserMessage: true,
                              actionKey: 'show_main_menu',
                            ),
                            _showMainMenu,
                          )),
                          onSubmit: _submitComposer,
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _restoreTranscript() async {
    if (_didRestoreTranscript) {
      return;
    }
    _didRestoreTranscript = true;

    final transcript = _chatTranscriptRepository;
    if (transcript == null) {
      _seedConversation();
      return;
    }

    await transcript.restore();
    if (!mounted) {
      return;
    }

    if (transcript.entries.isEmpty) {
      _seedConversation();
      return;
    }

    setState(() {
      _messages
        ..clear()
        ..addAll(transcript.entries.map(_messageFromTranscript));
      _messageCounter = _messages.length;
      _composerMode = _composerModeFromStorageKey(transcript.composerModeKey);
      _pendingTemplateAfterPayment =
          transcript.pendingTemplate?.toPresentationTemplate();
    });
    _scrollToBottom();
  }

  void _seedConversation() {
    if (_didSeedConversation) {
      return;
    }
    _didSeedConversation = true;
    _appendBotMessage(
      '🎬 AI Презентации\n'
      'Создавай презентации и конвертируй файлы за пару минут.\n\n'
      '🚀 Генерация по теме и пожеланиям\n'
      '🎨 4 дизайна на выбор\n'
      '🖼 Иллюстрации и PDF-рендер\n'
      '🧰 Конвертация PDF/DOCX/PPTX\n\n'
      'Выбери раздел ниже 👇',
      keyboard: _mainMenuKeyboard(),
    );
  }

  Future<void> _refreshAfterAppResume() async {
    final billingController = _billingController;
    if (billingController == null) {
      return;
    }

    final payment = billingController.payment;
    if (payment != null && !payment.isFinished) {
      await billingController.pollPayment(payment.paymentId);
      return;
    }

    if (_pendingTemplateAfterPayment == null) {
      return;
    }

    await billingController.refreshSummary();
    final summary = billingController.summary;
    if (summary != null && summary.remainingGenerations > 0) {
      await _resumePendingPresentationAfterPayment();
    }
  }

  Future<void> _initializeIncomingLinks() async {
    if (kIsWeb) {
      return;
    }

    final appLinks = AppLinks();
    try {
      final initialLink = await appLinks.getInitialLink();
      if (initialLink != null) {
        await _handleIncomingUri(initialLink);
      }
    } catch (_) {}

    _deepLinkSubscription = appLinks.uriLinkStream.listen(
      (uri) => unawaited(_handleIncomingUri(uri)),
      onError: (_) {},
    );
  }

  Future<void> _handleIncomingUri(Uri uri) async {
    if (!_isBillingReturnUri(uri)) {
      return;
    }

    final uriKey = uri.toString();
    if (_billingReturnInFlight || _lastHandledBillingReturnKey == uriKey) {
      return;
    }

    _billingReturnInFlight = true;
    _lastHandledBillingReturnKey = uriKey;
    try {
      await _handleBillingReturn();
    } finally {
      _billingReturnInFlight = false;
    }
  }

  bool _isBillingReturnUri(Uri uri) {
    return uri.scheme == 'appslides' &&
        uri.host == 'billing' &&
        uri.path == '/return';
  }

  Future<void> _handleBillingReturn() async {
    final billingController = _billingController;
    if (billingController == null) {
      return;
    }

    final payment = billingController.payment;
    if (payment != null && !payment.isFinished) {
      await billingController.pollPayment(payment.paymentId);
      return;
    }

    await billingController.refreshSummary();
    final summary = billingController.summary;
    if (summary == null) {
      return;
    }

    if (_pendingTemplateAfterPayment != null &&
        summary.remainingGenerations > 0) {
      await _resumePendingPresentationAfterPayment();
      return;
    }

    if (summary.remainingGenerations > 0) {
      _appendBotMessage(
        '✅ **Возврат из YooKassa выполнен**\nСтатус подписки обновлён.',
        keyboard: _mainMenuOnlyKeyboard(),
      );
    }
  }

  Future<void> _submitComposer() async {
    final raw = _composerController.text.trim();
    if (raw.isEmpty) {
      return;
    }

    FocusScope.of(context).unfocus();
    _composerFocusNode.unfocus();
    _composerController.clear();
    _appendUserMessage(raw);
    await _persistTranscript();

    final command = raw.toLowerCase();
    if (command.startsWith('/')) {
      await _handleCommand(command);
      await _persistTranscript();
      return;
    }

    switch (_composerMode) {
      case _ComposerMode.idle:
        await _startPresentationTopic(raw);
        await _persistTranscript();
        return;
      case _ComposerMode.presentationTopic:
        await _startPresentationTopic(raw);
        await _persistTranscript();
        return;
      case _ComposerMode.presentationSlides:
        await _acceptSlidesFromText(raw);
        await _persistTranscript();
        return;
      case _ComposerMode.outlineRevision:
        await _submitOutlineRevision(raw);
        await _persistTranscript();
        return;
    }
  }

  Future<void> _handleCommand(String command) async {
    switch (command) {
      case '/start':
      case '/menu':
        return _showMainMenu();
      case '/help':
        _showHelp();
        return;
      case '/balance':
        await _showBalance();
        return;
      case '/settings':
        await _showSettings();
        return;
      case '/history':
        _showHistory();
        return;
      case '/files':
        _showFiles();
        return;
      default:
        _appendBotMessage(
          'Я не знаю команду `$command`.\n'
          'Попробуй `/start`, `/help`, `/balance`, `/settings`, `/files` или просто отправь тему презентации.',
          keyboard: _mainMenuKeyboard(),
        );
        return;
    }
  }

  Future<void> _showMainMenu() async {
    _composerMode = _ComposerMode.idle;
    if (mounted) {
      setState(() {});
    }
    _appendBotMessage(
      '**Главное меню** 📌',
      keyboard: _mainMenuKeyboard(),
    );
  }

  void _showHelp() {
    final supportLink = _currentSupportMarkdownLink();
    final clientId = _currentClientId();
    _appendBotMessage(
      '**❓ Помощь**\n'
      '1. Нажми **«Создать презентацию»** или просто отправь тему.\n'
      '2. Выбери число слайдов.\n'
      '3. Утверди план и дизайн.\n'
      '4. Получи **PPTX** и **PDF**.\n\n'
      'Для конвертации используй отдельные кнопки **PDF / DOCX / PPTX**.\n\n'
      'Команда `/files` показывает локально сохранённые файлы.\n\n'
      '**ID устройства:** `$clientId`\n\n'
      'Если что-то не работает, напиши в поддержку:\n'
      '$supportLink',
      keyboard: [
        [
          _action(
            '🏠 Главное меню',
            _showMainMenu,
            actionKey: 'show_main_menu',
            echoAsUser: false,
          ),
        ],
      ],
    );
  }

  Future<void> _showBalance() async {
    final controller = _billingController;
    if (controller == null) {
      return;
    }

    await controller.refreshSummary();
    final summary = controller.summary;
    if (summary == null) {
      final message = controller.error?.trim().isNotEmpty == true
          ? controller.error!.trim()
          : 'Не удалось загрузить данные по подписке.';
      _appendBotMessage(
        '❌ $message',
        keyboard: [
          [
            _action(
              '🔄 Повторить',
              _showBalance,
              actionKey: 'show_balance',
              echoAsUser: false,
            ),
            _action(
              '🏠 Главное меню',
              _showMainMenu,
              actionKey: 'show_main_menu',
              echoAsUser: false,
            ),
          ],
        ],
      );
      return;
    }

    _appendBotMessage(
      _buildBalanceText(summary),
      keyboard: _buildBalanceKeyboard(summary),
    );
  }

  Future<void> _showSettings() async {
    final currentUrl =
        _backendConfigRepository?.baseUrl ?? AppConfig.defaultBackendBaseUrl;
    _appendBotMessage(
      '⚙️ Настройки\n'
      'Приложение всегда подключается к удалённому backend AppSlides.\n'
      'Локальная смена URL отключена.\n\n'
      'Текущий сервер:\n'
      '$currentUrl',
      keyboard: [
        [
          _action('🔌 Проверить', _testConnection,
              actionKey: 'test_connection'),
        ],
        [
          _action(
            '🏠 Главное меню',
            _showMainMenu,
            actionKey: 'show_main_menu',
            echoAsUser: false,
          ),
        ],
      ],
    );
  }

  void _showHistory() {
    final history = _historyRepository;
    final savedFiles = _savedFilesRepository;
    if (history == null || savedFiles == null) {
      return;
    }

    final recentEntries = history.entries.take(6).toList();
    final recentFiles = savedFiles.entries.take(4).toList();
    final buffer = StringBuffer('🗂 История\n');

    if (recentEntries.isEmpty) {
      buffer.writeln('Пока пусто. Сгенерируй outline или запусти конвертацию.');
    } else {
      buffer.writeln('Последние события:');
      for (final entry in recentEntries) {
        buffer.writeln('• ${entry.title} — ${entry.status.name}');
      }
    }

    if (recentFiles.isNotEmpty) {
      buffer.writeln('\nЛокально сохраненные файлы:');
      for (final file in recentFiles) {
        buffer.writeln('• ${file.filename} — ${file.kind.toUpperCase()}');
      }
    }

    _appendBotMessage(
      buffer.toString().trim(),
      attachments:
          recentFiles.map(_buildSavedFileAttachment).toList(growable: false),
      keyboard: [
        [
          _action('📁 Файлы', () async => _showFiles(),
              actionKey: 'show_files'),
          _action(
            '🏠 Главное меню',
            _showMainMenu,
            actionKey: 'show_main_menu',
            echoAsUser: false,
          ),
        ],
      ],
    );
  }

  void _showFiles() {
    final savedFiles = _savedFilesRepository;
    if (savedFiles == null) {
      return;
    }

    final recentFiles = savedFiles.entries.take(6).toList(growable: false);
    if (recentFiles.isEmpty) {
      _appendBotMessage(
        '📁 Локальных файлов пока нет.\n'
        'Сохрани результат генерации или конвертации, и он появится здесь.',
        keyboard: [
          [
            _action(
              '🏠 Главное меню',
              _showMainMenu,
              actionKey: 'show_main_menu',
              echoAsUser: false,
            ),
          ],
        ],
      );
      return;
    }

    _appendBotMessage(
      '📁 Локальные файлы\n'
      'Ниже последние сохранённые результаты. Их можно открыть или удалить прямо из чата.',
      attachments:
          recentFiles.map(_buildSavedFileAttachment).toList(growable: false),
      keyboard: [
        [
          _action('🗂 История', () async => _showHistory(),
              actionKey: 'show_history'),
          _action(
            '🏠 Главное меню',
            _showMainMenu,
            actionKey: 'show_main_menu',
            echoAsUser: false,
          ),
        ],
      ],
    );
  }

  Future<void> _testConnection() async {
    _appendBotMessage('Проверяю backend...');
    try {
      final healthy = await AppScope.repositoryOf(context).healthcheck();
      _appendBotMessage(
        healthy
            ? '✅ Backend ответил: `/v1/health -> ok`'
            : '⚠️ Backend ответил, но статус не ok.',
        keyboard: [
          [
            _action(
              '🏠 Главное меню',
              _showMainMenu,
              actionKey: 'show_main_menu',
              echoAsUser: false,
            ),
          ],
        ],
      );
    } catch (error) {
      _appendBotMessage(
        '❌ Не удалось достучаться до backend.\n$error',
        keyboard: [
          [
            _action(
              '🔄 Повторить',
              _testConnection,
              actionKey: 'test_connection',
              echoAsUser: false,
            ),
            _action(
              '🏠 Главное меню',
              _showMainMenu,
              actionKey: 'show_main_menu',
              echoAsUser: false,
            ),
          ],
        ],
      );
    }
  }

  Future<void> _beginPresentationTopicInput() async {
    _composerMode = _ComposerMode.presentationTopic;
    if (mounted) {
      setState(() {});
    }
    _appendBotMessage(
      '✍️ Напиши тему презентации и пожелания.\nНапример: «Удивительные факты о космосе для школьников».',
    );
  }

  Future<void> _startPresentationTopic(String topic) async {
    final controller = _presentationController;
    if (controller == null) {
      return;
    }

    controller.resetDraft();
    _pendingTemplateAfterPayment = null;
    _resumingPresentationAfterPayment = false;
    _clearOutlineProgressMessage();
    _clearRenderProgressMessages();
    _clearBillingProgressMessage();
    _lastPresentationOutlineKey = null;
    _lastPresentationError = null;
    _lastPresentationStatusKey = null;
    _lastPresentationResultKey = null;
    controller.setTopic(topic);

    _composerMode = _ComposerMode.presentationSlides;
    if (mounted) {
      setState(() {});
    }

    _appendBotMessage(
      'Отлично. Сколько сделать слайдов?',
      keyboard: [
        [
          _slideAction(4),
          _slideAction(5),
          _slideAction(6),
          _slideAction(7),
          _slideAction(8),
          _slideAction(9),
          _slideAction(10),
        ],
        [
          _action(
            '↩ Отмена',
            _showMainMenu,
            actionKey: 'show_main_menu',
            echoAsUser: false,
          ),
        ],
      ],
    );
  }

  Future<void> _acceptSlides(int slides) async {
    final controller = _presentationController;
    if (controller == null) {
      return;
    }

    controller.setSlidesTotal(slides);
    _composerMode = _ComposerMode.idle;
    if (mounted) {
      setState(() {});
    }

    _clearOutlineProgressMessage();
    _outlineProgressMessageId =
        _appendBotMessage('_Генерирую план презентации..._');
    await controller.generateOutline();
  }

  Future<void> _acceptSlidesFromText(String raw) async {
    final parsed = int.tryParse(raw);
    if (parsed == null ||
        !_presentationController!.slideOptions.contains(parsed)) {
      _appendBotMessage(
        'Пожалуйста, отправь число от 4 до 10 или нажми кнопку с количеством слайдов.',
      );
      return;
    }
    await _acceptSlides(parsed);
  }

  void _approveOutline() {
    final controller = _presentationController;
    if (controller == null || !controller.hasOutline) {
      return;
    }

    final templates = controller.templates
        .where((item) => item.templateAvailable)
        .toList(growable: false);

    if (templates.isEmpty) {
      _appendBotMessage(
        'Шаблоны пока не загрузились. Попробую обновить каталог ещё раз...',
      );
      unawaited(controller.refreshTemplates());
      return;
    }

    _appendBotMessage(
      '',
      templatePreviewTemplates: templates,
    );
    _appendBotMessage(
      'Выбери дизайн оформления 🎨',
      keyboard: _buildTemplateKeyboard(templates),
    );
  }

  Future<void> _requestOutlineRevision() async {
    _composerMode = _ComposerMode.outlineRevision;
    if (mounted) {
      setState(() {});
    }
    _appendBotMessage(
      '✍️ Напиши, что изменить в плане.\n'
      'Например: «сделай акцент на практических выводах и сократи вводную часть».',
    );
  }

  Future<void> _submitOutlineRevision(String comment) async {
    final controller = _presentationController;
    if (controller == null) {
      return;
    }

    _composerMode = _ComposerMode.idle;
    if (mounted) {
      setState(() {});
    }

    _clearOutlineProgressMessage();
    _outlineProgressMessageId =
        _appendBotMessage('_Обновляю план по твоему комментарию..._');
    await controller.reviseOutline(comment);
  }

  Future<void> _selectTemplate(PresentationTemplate template) async {
    final controller = _presentationController;
    if (controller == null) {
      return;
    }

    final billingController = _billingController;
    if (billingController != null) {
      await billingController.refreshSummary();
      final summary = billingController.summary;
      if (summary == null) {
        _appendBotMessage(
          '❌ Не удалось проверить баланс генераций.\n'
          '${billingController.error ?? 'Открой /balance и попробуй снова.'}',
        );
        return;
      }
      if (summary.remainingGenerations <= 0) {
        _pendingTemplateAfterPayment = template;
        await _showPendingPresentationPaywall(summary);
        return;
      }
    }

    controller.selectDesign(template.id);
    _clearRenderProgressMessages();
    _renderPreparationMessageId = _appendBotMessage('_Пишу тексты..._');
    unawaited(_startRender(generatePdf: true));
  }

  Future<void> _startRender({
    required bool generatePdf,
  }) async {
    final controller = _presentationController;
    if (controller == null) {
      return;
    }

    controller.setGeneratePdf(generatePdf);
    await controller.startPresentationJob();
  }

  Future<void> _startConversionFlow({
    required String sourceExtension,
    required String targetExtension,
    required String label,
  }) async {
    final controller = _converterController;
    if (controller == null) {
      return;
    }

    controller.reset();
    _lastConverterError = null;
    _lastConverterStatusKey = null;
    _lastConverterResultKey = null;

    await controller.pickFile(
      allowedExtensions: <String>[sourceExtension],
    );
    final selectedFile = controller.selectedFile;
    if (selectedFile == null) {
      _appendBotMessage(
        'Файл не выбран. Нажми `$label` ещё раз, когда будешь готов.',
      );
      return;
    }

    controller.setTargetFormat(targetExtension);
    _appendBotMessage(
      '📎 Принял файл `${selectedFile.name}`.\n'
      'Запускаю конвертацию ${sourceExtension.toUpperCase()} → ${targetExtension.toUpperCase()}...',
    );
    await controller.startConversionJob();
  }

  void _handlePresentationUpdates() {
    final controller = _presentationController;
    if (controller == null) {
      return;
    }

    final error = controller.error?.trim();
    if (error == null || error.isEmpty) {
      _lastPresentationError = null;
    } else if (error != _lastPresentationError) {
      _lastPresentationError = error;
      if (controller.job == null) {
        _clearOutlineProgressMessage();
        _removeMessageById(_renderPreparationMessageId);
        _renderPreparationMessageId = null;
      }
      _appendBotMessage('❌ $error');
    }

    if (controller.hasOutline) {
      final key = '${controller.title}|${controller.outline.join('||')}';
      if (key != _lastPresentationOutlineKey) {
        _lastPresentationOutlineKey = key;
        _clearOutlineProgressMessage();
        _appendBotMessage(_buildOutlineText(controller));
        _appendBotMessage(
          'Принять или изменить?\nМожно написать комментарий к плану, и я его обновлю.',
          keyboard: [
            [
              _action(
                '✅ Принять план',
                () async => _approveOutline(),
                actionKey: 'approve_outline',
              ),
              _action(
                '✍️ Редактировать',
                _requestOutlineRevision,
                actionKey: 'request_outline_revision',
              ),
            ],
            [
              _action(
                '↩ Отмена',
                _showMainMenu,
                actionKey: 'show_main_menu',
                echoAsUser: false,
              ),
            ],
          ],
        );
      }
    }

    final job = controller.job;
    if (job != null) {
      final statusKey = '${job.jobId}:${job.status.name}';
      if (statusKey != _lastPresentationStatusKey) {
        _lastPresentationStatusKey = statusKey;
        switch (job.status) {
          case RemoteJobStatus.queued:
            _removeMessageById(_renderPreparationMessageId);
            _renderPreparationMessageId = null;
            if (_presentationStatusMessageId == null) {
              _presentationStatusMessageId = _appendBotMessage(
                '⌛ Задача поставлена в очередь.\nID задачи: `${job.jobId}`',
              );
            } else {
              _updateMessageById(
                _presentationStatusMessageId!,
                text:
                    '⌛ Задача поставлена в очередь.\nID задачи: `${job.jobId}`',
              );
            }
            break;
          case RemoteJobStatus.running:
            _removeMessageById(_renderPreparationMessageId);
            _renderPreparationMessageId = null;
            if (_presentationStatusMessageId == null) {
              _presentationStatusMessageId = _appendBotMessage(
                '⚙️ Генерация идёт.\nID задачи: `${job.jobId}`',
              );
            } else {
              _updateMessageById(
                _presentationStatusMessageId!,
                text: '⚙️ Генерация идёт.\nID задачи: `${job.jobId}`',
              );
            }
            break;
          case RemoteJobStatus.failed:
            _removeMessageById(_renderPreparationMessageId);
            _renderPreparationMessageId = null;
            _appendBotMessage(
              '❌ Не удалось собрать презентацию.\n${job.error ?? 'Попробуй ещё раз.'}',
              keyboard: _mainMenuOnlyKeyboard(),
            );
            break;
          case RemoteJobStatus.succeeded:
          case RemoteJobStatus.unknown:
            break;
        }
      }

      if (job.isSuccessful && job.artifacts.isNotEmpty) {
        final resultKey =
            '${job.jobId}:${job.artifacts.map((item) => item.artifactId).join(',')}';
        if (resultKey != _lastPresentationResultKey) {
          _lastPresentationResultKey = resultKey;
          _clearRenderProgressMessages();
          final attachments = job.artifacts
              .map((artifact) =>
                  _buildPresentationAttachment(job.jobId, artifact))
              .toList(growable: false);
          _appendBotMessage(
            '**✅ Презентация готова**\n'
            'Тема: **${controller.title}**\n'
            'Файлы уже доступны ниже.',
            attachments: attachments,
            keyboard: _mainMenuOnlyKeyboard(),
          );
          unawaited(_prefetchAttachmentsInBackground(attachments));
        }
      }
    }

    if (mounted) {
      setState(() {});
    }
  }

  void _handleConverterUpdates() {
    final controller = _converterController;
    if (controller == null) {
      return;
    }

    final error = controller.error?.trim();
    if (error == null || error.isEmpty) {
      _lastConverterError = null;
    } else if (error != _lastConverterError) {
      _lastConverterError = error;
      _appendBotMessage('❌ $error');
    }

    final job = controller.job;
    if (job != null) {
      final statusKey = '${job.jobId}:${job.status.name}';
      if (statusKey != _lastConverterStatusKey) {
        _lastConverterStatusKey = statusKey;
        switch (job.status) {
          case RemoteJobStatus.queued:
            _appendBotMessage('⌛ Файл поставлен в очередь на конвертацию.');
            break;
          case RemoteJobStatus.running:
            _appendBotMessage('⚙️ Конвертация идёт...');
            break;
          case RemoteJobStatus.failed:
            _appendBotMessage(
              '❌ Конвертация завершилась с ошибкой.\n${job.error ?? 'Попробуй ещё раз.'}',
              keyboard: [
                [
                  _action(
                    '🏠 Главное меню',
                    _showMainMenu,
                    actionKey: 'show_main_menu',
                    echoAsUser: false,
                  ),
                ],
              ],
            );
            break;
          case RemoteJobStatus.succeeded:
          case RemoteJobStatus.unknown:
            break;
        }
      }

      final artifact = job.artifact;
      if (job.isSuccessful && artifact != null) {
        final resultKey = '${job.jobId}:${artifact.artifactId}';
        if (resultKey != _lastConverterResultKey) {
          _lastConverterResultKey = resultKey;
          _appendBotMessage(
            '✅ Конвертация готова\nФайл доступен ниже.',
            attachments: <_ChatAttachment>[
              _buildConversionAttachment(job.jobId, artifact),
            ],
            keyboard: [
              [
                _action(
                  '🏠 Главное меню',
                  _showMainMenu,
                  actionKey: 'show_main_menu',
                  echoAsUser: false,
                ),
              ],
            ],
          );
        }
      }
    }

    if (mounted) {
      setState(() {});
    }
  }

  void _handleBillingUpdates() {
    final controller = _billingController;
    if (controller == null) {
      return;
    }

    final payment = controller.payment;
    if (payment != null &&
        controller.paymentPollingTimedOut &&
        !payment.isFinished &&
        payment.paymentId != _lastBillingTimeoutPaymentId) {
      _lastBillingTimeoutPaymentId = payment.paymentId;
      _appendBotMessage(
        '⌛ **Оплата ещё не подтверждена**\n'
        'Я автоматически проверял статус 15 минут. Если ты уже оплатил, нажми **«Проверить оплату»** или открой счёт снова.',
        keyboard: _buildPendingPaymentKeyboard(payment),
      );
    }

    if (payment != null) {
      final statusKey = '${payment.paymentId}:${payment.status}';
      if (statusKey != _lastBillingPaymentStatusKey) {
        _lastBillingPaymentStatusKey = statusKey;
        switch (payment.status) {
          case 'pending':
          case 'waiting_for_capture':
            _clearBillingProgressMessage();
            _appendBotMessage(
              '💳 **Счёт создан**\nОткрой YooKassa, оплати тариф и затем нажми **«Проверить оплату»**.',
              keyboard: _buildPendingPaymentKeyboard(payment),
            );
            if (payment.confirmationUrl case final confirmationUrl?) {
              unawaited(_launchPaymentUrl(confirmationUrl));
            }
            break;
          case 'paid':
            _lastBillingTimeoutPaymentId = null;
            _clearBillingProgressMessage();
            _appendBotMessage(
              _buildPaymentSuccessText(payment.summary),
              keyboard: _mainMenuOnlyKeyboard(),
            );
            unawaited(_resumePendingPresentationAfterPayment());
            break;
          case 'canceled':
            _lastBillingTimeoutPaymentId = null;
            _clearBillingProgressMessage();
            _appendBotMessage(
              '❌ Оплата отменена.',
              keyboard: [
                [
                  _action(
                    '✅ Выбрать подписку',
                    _showPlanOptions,
                    actionKey: 'show_plan_options',
                  ),
                ],
                [
                  _action(
                    '🏠 Главное меню',
                    _showMainMenu,
                    actionKey: 'show_main_menu',
                    echoAsUser: false,
                  ),
                ],
              ],
            );
            break;
          case 'failed':
            _lastBillingTimeoutPaymentId = null;
            _clearBillingProgressMessage();
            _appendBotMessage(
              '❌ Платёж завершился ошибкой. Попробуй выбрать тариф ещё раз.',
              keyboard: [
                [
                  _action(
                    '✅ Выбрать подписку',
                    _showPlanOptions,
                    actionKey: 'show_plan_options',
                  ),
                ],
                [
                  _action(
                    '🏠 Главное меню',
                    _showMainMenu,
                    actionKey: 'show_main_menu',
                    echoAsUser: false,
                  ),
                ],
              ],
            );
            break;
          default:
            break;
        }
      }
    }

    if (mounted) {
      setState(() {});
    }
  }

  String _buildBalanceText(BillingSummary summary) {
    final active = summary.activeSubscription;
    final latest = summary.latestValidSubscription;
    final buffer = StringBuffer();

    if (active != null && active.isActive) {
      final plan = _findBillingPlan(summary, active.planKey);
      buffer.writeln('**✅ Подписка активна**');
      if (plan != null) {
        buffer.writeln('**Тариф:** ${_planTariffLine(plan)}');
      }
      buffer.writeln('**Остаток генераций:** ${active.remaining}');
      buffer.writeln('**Действует до:** ${_shortDate(active.endsAt)}');
      if (active.provider == 'yookassa') {
        buffer.writeln(
          active.autoRenew
              ? 'Автопродление через YooKassa включено.'
              : 'Автопродление через YooKassa отключено.',
        );
      }
      return buffer.toString().trim();
    }

    final remaining = latest?.remaining ?? 0;
    if (latest != null && latest.isCanceled) {
      buffer.writeln('**❌ Подписка отключена**');
      buffer.writeln('**Генерации:** $remaining');
      buffer.writeln('Генерации доступны до ${_shortDate(latest.endsAt)}.');
    } else {
      buffer.writeln('**❌ Подписка неактивна**');
      buffer.writeln('**Генерации:** $remaining');
    }

    final recurringPlans = _visibleBillingPlans(summary);
    if (recurringPlans.isNotEmpty) {
      buffer.writeln();
      buffer.writeln('**Подписка с автосписанием**');
      for (final plan in recurringPlans) {
        buffer.writeln('- ${_planOptionLabel(plan)}');
      }
    }

    if (summary.testMode) {
      buffer.writeln();
      buffer.writeln('_Тестовый режим YooKassa включён._');
    }

    buffer.writeln();
    buffer.writeln(
      'Переходя к оплате, вы соглашаетесь с [офертой](${summary.offerUrl}).',
    );
    return buffer.toString().trim();
  }

  List<List<_ChatAction>> _buildBalanceKeyboard(BillingSummary summary) {
    final rows = <List<_ChatAction>>[];
    final active = summary.activeSubscription;

    if (active != null && active.isActive && active.autoRenew) {
      rows.add([
        _action(
          '❌ Отключить подписку',
          _cancelBillingSubscription,
          actionKey: 'cancel_billing_subscription',
        ),
      ]);
    } else if (active == null || !active.isActive) {
      rows.add([
        _action(
          '✅ Выбрать подписку',
          _showPlanOptions,
          actionKey: 'show_plan_options',
        ),
      ]);
    }

    rows.add([
      _action(
        '🏠 Главное меню',
        _showMainMenu,
        actionKey: 'show_main_menu',
        echoAsUser: false,
      ),
    ]);
    return rows;
  }

  List<List<_ChatAction>> _buildPendingPaymentKeyboard(BillingPayment payment) {
    final rows = <List<_ChatAction>>[];
    if (payment.confirmationUrl != null) {
      rows.add([
        _action(
          '💳 Оплатить',
          () async => _launchPaymentUrl(payment.confirmationUrl!),
          actionKey: 'launch_payment_url',
          payload: <String, dynamic>{
            'url': payment.confirmationUrl!,
          },
        ),
      ]);
    }
    rows.add([
      _action(
        '🔄 Проверить оплату',
        () async => _checkBillingPayment(payment.paymentId),
        actionKey: 'check_billing_payment',
        payload: <String, dynamic>{
          'payment_id': payment.paymentId,
        },
      ),
    ]);
    rows.add([
      _action(
        '🏠 Главное меню',
        _showMainMenu,
        actionKey: 'show_main_menu',
        echoAsUser: false,
      ),
    ]);
    return rows;
  }

  Future<void> _showPendingPresentationPaywall(BillingSummary summary) async {
    final rows = <List<_ChatAction>>[
      for (final plan in _visibleBillingPlans(summary))
        [
          _action(
            _planOptionLabel(plan),
            () async => _startBillingPayment(plan.key),
            actionKey: 'start_billing_payment',
            payload: <String, dynamic>{
              'plan_key': plan.key,
              'renew': false,
            },
          ),
        ],
      [
        _action(
          '⬅️ Назад',
          _showMainMenu,
          actionKey: 'show_main_menu',
          echoAsUser: false,
        ),
      ],
    ];

    _appendBotMessage(
      '**Презентация почти готова!** ✅\n'
      'Выбери подписку, чтобы завершить финальный шаг и получить готовую презентацию.',
      keyboard: rows,
    );
  }

  List<BillingPlan> _visibleBillingPlans(BillingSummary summary) {
    return summary.plans
        .where((plan) => plan.recurring)
        .toList(growable: false);
  }

  String _buildPaymentSuccessText(BillingSummary summary) {
    final active = summary.activeSubscription;
    final plan =
        active == null ? null : _findBillingPlan(summary, active.planKey);
    final buffer = StringBuffer('**Оплата прошла успешно.** ✅\n\n');
    if (plan != null) {
      buffer.writeln('**Тариф:** ${_planTariffLine(plan)}');
    }
    if (active != null) {
      buffer.writeln('**Остаток генераций:** ${active.remaining}');
      buffer.writeln('**Действует до:** ${_shortDate(active.endsAt)}');
    }
    return buffer.toString().trim();
  }

  List<List<_ChatAction>> _mainMenuOnlyKeyboard() {
    return [
      [
        _action(
          '🏠 Главное меню',
          _showMainMenu,
          actionKey: 'show_main_menu',
          echoAsUser: false,
        ),
      ],
    ];
  }

  Future<void> _prefetchAttachmentsInBackground(
    List<_ChatAttachment> attachments,
  ) async {
    if (kIsWeb) {
      return;
    }
    for (final attachment in attachments) {
      await _saveAttachmentSilently(attachment);
    }
  }

  Future<void> _saveAttachmentSilently(_ChatAttachment attachment) async {
    final savedFiles = _savedFilesRepository;
    final history = _historyRepository;
    if (savedFiles == null || history == null) {
      return;
    }
    if (savedFiles.findByArtifactId(attachment.artifactId) != null) {
      return;
    }

    try {
      final savedEntry = await savedFiles.downloadAndStore(
        sourceType: attachment.sourceType,
        jobId: attachment.jobId,
        artifactId: attachment.artifactId,
        kind: attachment.kind,
        filename: attachment.filename,
        mediaType: attachment.mediaType,
        remoteUri: attachment.remoteUri,
      );
      switch (attachment.sourceType) {
        case SavedFileSourceType.presentationArtifact:
          history.attachPresentationLocalFile(
            jobId: attachment.jobId,
            localPath: savedEntry.localPath,
          );
          break;
        case SavedFileSourceType.conversionArtifact:
          history.attachConversionLocalFile(
            jobId: attachment.jobId,
            localPath: savedEntry.localPath,
          );
          break;
      }
    } catch (_) {
      // Silent by design: this path is only a convenience preload.
    }
  }

  Future<void> _showPlanOptions({bool renew = false}) async {
    final controller = _billingController;
    if (controller == null) {
      return;
    }

    await controller.refreshSummary();
    final summary = controller.summary;
    if (summary == null) {
      _appendBotMessage(
        '❌ ${controller.error ?? 'Не удалось загрузить список тарифов.'}',
      );
      return;
    }

    final plans = _visibleBillingPlans(summary);
    final rows = <List<_ChatAction>>[
      for (final plan in plans)
        [
          _action(
            _planOptionLabel(plan),
            () async => _startBillingPayment(
              plan.key,
              renew: renew && plan.recurring,
            ),
            actionKey: 'start_billing_payment',
            payload: <String, dynamic>{
              'plan_key': plan.key,
              'renew': renew && plan.recurring,
            },
          ),
        ],
      [
        _action(
          '⬅️ Назад',
          _showBalance,
          actionKey: 'show_balance',
          echoAsUser: false,
        ),
      ],
    ];

    _appendBotMessage(
      renew
          ? '**Продлить подписку**\nВыбери тариф для продления:'
          : '**Выбери подписку** 👇',
      keyboard: rows,
    );
  }

  Future<void> _startBillingPayment(String planKey,
      {bool renew = false}) async {
    final controller = _billingController;
    if (controller == null) {
      return;
    }

    _lastBillingPaymentStatusKey = null;
    _lastBillingTimeoutPaymentId = null;
    controller.clearPayment();
    _clearBillingProgressMessage();
    _billingProgressMessageId = _appendBotMessage('_Создаю счёт на оплату..._');
    await controller.startCheckout(planKey: planKey, renew: renew);
    if (controller.payment == null && controller.error != null) {
      _clearBillingProgressMessage();
      _appendBotMessage('❌ ${controller.error!}');
    }
  }

  Future<void> _checkBillingPayment(String paymentId) async {
    final controller = _billingController;
    if (controller == null) {
      return;
    }
    await controller.pollPayment(paymentId);
  }

  Future<void> _cancelBillingSubscription() async {
    final controller = _billingController;
    if (controller == null) {
      return;
    }

    await controller.cancelSubscription();
    final summary = controller.summary;
    if (summary == null) {
      _appendBotMessage(
        '❌ ${controller.error ?? 'Не удалось отключить подписку.'}',
      );
      return;
    }

    final latest = summary.latestValidSubscription;
    final untilDate = latest == null ? '' : _shortDate(latest.endsAt);
    _appendBotMessage(
      latest == null
          ? 'Подписка отключена.'
          : 'Подписка выключена. Генерации доступны до $untilDate.',
      keyboard: [
        [
          _action(
            '🏠 Главное меню',
            _showMainMenu,
            actionKey: 'show_main_menu',
            echoAsUser: false,
          ),
        ],
      ],
    );
  }

  Future<void> _resumePendingPresentationAfterPayment() async {
    if (_resumingPresentationAfterPayment) {
      return;
    }

    final template = _pendingTemplateAfterPayment;
    final controller = _presentationController;
    if (template == null || controller == null || !controller.hasOutline) {
      return;
    }

    _resumingPresentationAfterPayment = true;
    _pendingTemplateAfterPayment = null;

    try {
      controller.selectDesign(template.id);
      _clearRenderProgressMessages();
      _renderPreparationMessageId = _appendBotMessage(
          '_Оплата подтверждена. Продолжаю создание презентации..._');
      await _startRender(generatePdf: true);
    } finally {
      _resumingPresentationAfterPayment = false;
    }
  }

  String _currentSupportUsername() {
    final username = _billingController?.summary?.supportUsername.trim();
    if (username != null && username.isNotEmpty) {
      return username;
    }
    return '@your_tracksupport';
  }

  String _currentSupportMarkdownLink() {
    final username = _currentSupportUsername();
    final normalized =
        username.startsWith('@') ? username.substring(1) : username;
    if (normalized.isEmpty || normalized.contains(' ')) {
      return username;
    }
    return '[@$normalized](https://t.me/$normalized)';
  }

  String _currentClientId() {
    final clientId = _clientSessionRepository?.clientId?.trim();
    if (clientId != null && clientId.isNotEmpty) {
      return clientId;
    }
    return 'загружается...';
  }

  Future<void> _launchPaymentUrl(String url) async {
    final uri = Uri.tryParse(url);
    if (uri == null) {
      _appendBotMessage('Ссылка на оплату:\n$url');
      return;
    }

    final launched = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!launched) {
      _appendBotMessage(
        'Не удалось открыть ссылку автоматически.\nОткрой её вручную:\n$url',
      );
    }
  }

  BillingPlan? _findBillingPlan(BillingSummary summary, String planKey) {
    for (final plan in summary.plans) {
      if (plan.key == planKey) {
        return plan;
      }
    }
    return null;
  }

  String _planOptionLabel(BillingPlan plan) {
    return switch (plan.key) {
      'week' => '🔥 ${_planTariffLine(plan)}',
      'month' => '⭐ ${_planTariffLine(plan)}',
      'one10' => '⭐ ${_planTariffLine(plan)}',
      'one40' => '⭐ ${_planTariffLine(plan)}',
      _ => '${plan.priceRub} ₽ — ${plan.limit} генераций',
    };
  }

  String _planTariffLine(BillingPlan plan) {
    return switch (plan.key) {
      'week' => '${plan.priceRub} ₽ / неделя — ${plan.limit} генераций',
      'month' => '${plan.priceRub} ₽ / месяц — ${plan.limit} генераций',
      'one10' => '${plan.priceRub} ₽ — ${plan.limit} генераций',
      'one40' => '${plan.priceRub} ₽ — ${plan.limit} генераций',
      _ => '${plan.priceRub} ₽ — ${plan.limit} генераций',
    };
  }

  String _shortDate(String value) {
    final parsed = DateTime.tryParse(value);
    if (parsed == null) {
      return value;
    }
    final date = parsed.toLocal();
    final year = date.year.toString().padLeft(4, '0');
    final month = date.month.toString().padLeft(2, '0');
    final day = date.day.toString().padLeft(2, '0');
    return '$year-$month-$day';
  }

  void _handleExternalStateChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _handleAttachmentTap(_ChatAttachment attachment) async {
    final savedFiles = _savedFilesRepository;
    final history = _historyRepository;
    if (savedFiles == null || history == null) {
      return;
    }

    final existing = savedFiles.findByArtifactId(attachment.artifactId);
    if (existing != null) {
      final error = await savedFiles.openEntry(existing);
      if (error != null) {
        _appendBotMessage('❌ $error');
      }
      return;
    }

    if (kIsWeb) {
      _appendBotMessage(
        'На web локальное сохранение пока отключено.\nИспользуй download URL из карточки файла.',
      );
      return;
    }

    if (_savingAttachmentIds.contains(attachment.artifactId)) {
      return;
    }

    setState(() {
      _savingAttachmentIds.add(attachment.artifactId);
    });

    try {
      final savedEntry = await savedFiles.downloadAndStore(
        sourceType: attachment.sourceType,
        jobId: attachment.jobId,
        artifactId: attachment.artifactId,
        kind: attachment.kind,
        filename: attachment.filename,
        mediaType: attachment.mediaType,
        remoteUri: attachment.remoteUri,
      );

      switch (attachment.sourceType) {
        case SavedFileSourceType.presentationArtifact:
          history.attachPresentationLocalFile(
            jobId: attachment.jobId,
            localPath: savedEntry.localPath,
          );
          break;
        case SavedFileSourceType.conversionArtifact:
          history.attachConversionLocalFile(
            jobId: attachment.jobId,
            localPath: savedEntry.localPath,
          );
          break;
      }

      final openError = await savedFiles.openEntry(savedEntry);
      if (openError != null) {
        _appendBotMessage('❌ $openError');
      }
    } catch (error) {
      _appendBotMessage('❌ Не удалось сохранить файл.\n$error');
    } finally {
      if (mounted) {
        setState(() {
          _savingAttachmentIds.remove(attachment.artifactId);
        });
      }
    }
  }

  Future<void> _handleAttachmentDelete(_ChatAttachment attachment) async {
    final savedFiles = _savedFilesRepository;
    final history = _historyRepository;
    if (savedFiles == null || history == null) {
      return;
    }

    final existing = savedFiles.findByArtifactId(attachment.artifactId);
    if (existing == null ||
        _savingAttachmentIds.contains(attachment.artifactId)) {
      return;
    }

    setState(() {
      _savingAttachmentIds.add(attachment.artifactId);
    });

    try {
      final deleted = await savedFiles.deleteEntry(existing);
      if (deleted) {
        history.detachLocalFile(existing.localPath);
        _appendBotMessage(
            '🗑 Файл `${existing.filename}` удалён из локального хранилища.');
      } else {
        _appendBotMessage('❌ Не удалось удалить `${existing.filename}`.');
      }
    } catch (error) {
      _appendBotMessage('❌ Ошибка при удалении файла.\n$error');
    } finally {
      if (mounted) {
        setState(() {
          _savingAttachmentIds.remove(attachment.artifactId);
        });
      }
    }
  }

  Future<void> _runAction(
    _ChatAction action,
    Future<void> Function() callback,
  ) async {
    if (action.showAsUserMessage) {
      _appendUserMessage(action.label);
    }
    await callback();
    await _persistTranscript();
  }

  List<List<_ChatAction>> _mainMenuKeyboard() {
    return [
      [
        _action(
          '📊 Создать презентацию',
          _beginPresentationTopicInput,
          actionKey: 'begin_presentation_topic',
        ),
      ],
      [
        _action(
          '📄 PDF → DOCX',
          () => _startConversionFlow(
            sourceExtension: 'pdf',
            targetExtension: 'docx',
            label: '📄 PDF → DOCX',
          ),
          actionKey: 'start_conversion',
          payload: const <String, dynamic>{
            'source': 'pdf',
            'target': 'docx',
          },
        ),
      ],
      [
        _action(
          '📄 DOCX → PDF',
          () => _startConversionFlow(
            sourceExtension: 'docx',
            targetExtension: 'pdf',
            label: '📄 DOCX → PDF',
          ),
          actionKey: 'start_conversion',
          payload: const <String, dynamic>{
            'source': 'docx',
            'target': 'pdf',
          },
        ),
      ],
      [
        _action(
          '📊 PPTX → PDF',
          () => _startConversionFlow(
            sourceExtension: 'pptx',
            targetExtension: 'pdf',
            label: '📊 PPTX → PDF',
          ),
          actionKey: 'start_conversion',
          payload: const <String, dynamic>{
            'source': 'pptx',
            'target': 'pdf',
          },
        ),
      ],
      [
        _action(
          '💳 Баланс / Подписка',
          () async => _showBalance(),
          actionKey: 'show_balance',
        ),
      ],
      [
        _action('❓ Помощь', () async => _showHelp(), actionKey: 'show_help'),
      ],
    ];
  }

  List<List<_ChatAction>> _buildTemplateKeyboard(
    List<PresentationTemplate> templates,
  ) {
    final rows = <List<_ChatAction>>[];
    for (var index = 0; index < templates.length; index++) {
      rows.add(
        templates
            .skip(index)
            .take(1)
            .map(
              (template) => _action(
                template.name,
                () async => _selectTemplate(template),
                actionKey: 'select_template',
                payload: _templatePayload(template),
              ),
            )
            .toList(),
      );
    }
    rows.add(
      <_ChatAction>[
        _action(
          '↩ Отмена',
          _showMainMenu,
          actionKey: 'show_main_menu',
          echoAsUser: false,
        ),
      ],
    );
    return rows;
  }

  _ChatAction _slideAction(int slides) {
    return _action(
      '$slides',
      () => _acceptSlides(slides),
      actionKey: 'accept_slides',
      payload: <String, dynamic>{
        'slides': slides,
      },
    );
  }

  _ChatAction _action(
    String label,
    Future<void> Function() onTap, {
    required String actionKey,
    Map<String, dynamic> payload = const <String, dynamic>{},
    bool echoAsUser = true,
  }) {
    return _ChatAction(
      label: label,
      onTap: onTap,
      showAsUserMessage: echoAsUser,
      actionKey: actionKey,
      payload: payload,
    );
  }

  _ChatAttachment _buildPresentationAttachment(
    String jobId,
    JobArtifact artifact,
  ) {
    final remoteUri = _presentationController?.downloadUriFor(artifact) ??
        Uri.parse(artifact.downloadUrl);
    return _ChatAttachment(
      jobId: jobId,
      artifactId: artifact.artifactId,
      filename: artifact.filename,
      kind: artifact.kind,
      mediaType: artifact.mediaType,
      remoteUri: remoteUri,
      sourceType: SavedFileSourceType.presentationArtifact,
      icon: artifact.kind == 'pdf'
          ? Icons.picture_as_pdf_rounded
          : Icons.slideshow_rounded,
      caption: artifact.kind == 'pdf' ? 'Финальный PDF' : 'Редактируемый PPTX',
    );
  }

  _ChatAttachment _buildConversionAttachment(
    String jobId,
    JobArtifact artifact,
  ) {
    return _ChatAttachment(
      jobId: jobId,
      artifactId: artifact.artifactId,
      filename: artifact.filename,
      kind: artifact.kind,
      mediaType: artifact.mediaType,
      remoteUri: AppScope.repositoryOf(context).conversionDownloadUri(jobId),
      sourceType: SavedFileSourceType.conversionArtifact,
      icon: artifact.kind == 'docx'
          ? Icons.description_rounded
          : Icons.picture_as_pdf_rounded,
      caption: 'Результат конвертации',
    );
  }

  _ChatAttachment _buildSavedFileAttachment(SavedFileEntry entry) {
    return _ChatAttachment(
      jobId: entry.jobId,
      artifactId: entry.artifactId,
      filename: entry.filename,
      kind: entry.kind,
      mediaType: entry.mediaType,
      remoteUri: Uri.tryParse(entry.remoteUrl) ?? Uri(),
      sourceType: entry.sourceType,
      icon: _iconForKind(entry.kind),
      caption: entry.sourceType == SavedFileSourceType.presentationArtifact
          ? 'Сохранённый файл презентации'
          : 'Сохранённый результат конвертации',
    );
  }

  _ChatMessage _messageFromTranscript(ChatTranscriptEntry entry) {
    return _ChatMessage(
      id: entry.id,
      sender: entry.sender == ChatTranscriptSender.user
          ? _MessageSender.user
          : _MessageSender.bot,
      text: entry.text,
      sentAt: entry.sentAt,
      keyboard: entry.keyboard
          .map(
            (row) => row
                .map(_actionFromTranscript)
                .whereType<_ChatAction>()
                .toList(growable: false),
          )
          .where((row) => row.isNotEmpty)
          .toList(growable: false),
      linkPreview: entry.linkPreview == null
          ? null
          : _MessageLinkPreview(
              domain: entry.linkPreview!.domain,
              title: entry.linkPreview!.title,
              description: entry.linkPreview!.description,
              url: entry.linkPreview!.url,
            ),
      attachments: entry.attachments
          .map(
            (attachment) => _ChatAttachment(
              jobId: attachment.jobId,
              artifactId: attachment.artifactId,
              filename: attachment.filename,
              kind: attachment.kind,
              mediaType: attachment.mediaType,
              remoteUri: Uri.tryParse(attachment.remoteUrl) ?? Uri(),
              sourceType: attachment.sourceType,
              icon: _iconForKind(attachment.kind),
              caption: attachment.caption,
            ),
          )
          .toList(growable: false),
      templatePreviewTemplates: entry.templatePreviewTemplates
          .map((item) => item.toPresentationTemplate())
          .toList(growable: false),
    );
  }

  ChatTranscriptEntry _messageToTranscript(_ChatMessage message) {
    return ChatTranscriptEntry(
      id: message.id,
      sender: message.sender == _MessageSender.user
          ? ChatTranscriptSender.user
          : ChatTranscriptSender.bot,
      text: message.text,
      sentAt: message.sentAt,
      keyboard: message.keyboard
          .map(
            (row) => row
                .map(_actionToTranscript)
                .whereType<ChatTranscriptAction>()
                .toList(growable: false),
          )
          .where((row) => row.isNotEmpty)
          .toList(growable: false),
      linkPreview: message.linkPreview == null
          ? null
          : ChatTranscriptLinkPreview(
              domain: message.linkPreview!.domain,
              title: message.linkPreview!.title,
              description: message.linkPreview!.description,
              url: message.linkPreview!.url,
            ),
      attachments: message.attachments
          .map(
            (attachment) => ChatTranscriptAttachment(
              jobId: attachment.jobId,
              artifactId: attachment.artifactId,
              filename: attachment.filename,
              kind: attachment.kind,
              mediaType: attachment.mediaType,
              remoteUrl: attachment.remoteUri.toString(),
              sourceType: attachment.sourceType,
              caption: attachment.caption,
            ),
          )
          .toList(growable: false),
      templatePreviewTemplates: message.templatePreviewTemplates
          .map(ChatTranscriptTemplatePreview.fromPresentationTemplate)
          .toList(growable: false),
    );
  }

  Future<void> _persistTranscript() async {
    final transcript = _chatTranscriptRepository;
    if (transcript == null) {
      return;
    }
    await transcript.saveSnapshot(
      entries: _messages.map(_messageToTranscript).toList(growable: false),
      composerModeKey: _composerMode.name,
      pendingTemplate: _pendingTemplateAfterPayment == null
          ? null
          : ChatTranscriptTemplatePreview.fromPresentationTemplate(
              _pendingTemplateAfterPayment!,
            ),
    );
  }

  _ComposerMode _composerModeFromStorageKey(String value) {
    return switch (value) {
      'presentationTopic' => _ComposerMode.presentationTopic,
      'presentationSlides' => _ComposerMode.presentationSlides,
      'outlineRevision' => _ComposerMode.outlineRevision,
      _ => _ComposerMode.idle,
    };
  }

  ChatTranscriptAction? _actionToTranscript(_ChatAction action) {
    if (action.actionKey.isEmpty) {
      return null;
    }
    return ChatTranscriptAction(
      label: action.label,
      actionKey: action.actionKey,
      showAsUserMessage: action.showAsUserMessage,
      payload: action.payload,
    );
  }

  _ChatAction? _actionFromTranscript(ChatTranscriptAction action) {
    Future<void> Function()? callback;

    switch (action.actionKey) {
      case 'show_main_menu':
        callback = _showMainMenu;
        break;
      case 'show_help':
        callback = () async => _showHelp();
        break;
      case 'show_balance':
        callback = _showBalance;
        break;
      case 'show_settings':
        callback = _showSettings;
        break;
      case 'show_history':
        callback = () async => _showHistory();
        break;
      case 'show_files':
        callback = () async => _showFiles();
        break;
      case 'test_connection':
        callback = _testConnection;
        break;
      case 'begin_presentation_topic':
        callback = _beginPresentationTopicInput;
        break;
      case 'start_conversion':
        callback = () => _startConversionFlow(
              sourceExtension: (action.payload['source'] as String?) ?? 'pdf',
              targetExtension: (action.payload['target'] as String?) ?? 'docx',
              label: action.label,
            );
        break;
      case 'accept_slides':
        final slides = int.tryParse('${action.payload['slides'] ?? ''}');
        if (slides == null) {
          return null;
        }
        callback = () => _acceptSlides(slides);
        break;
      case 'approve_outline':
        callback = () async => _approveOutline();
        break;
      case 'request_outline_revision':
        callback = _requestOutlineRevision;
        break;
      case 'select_template':
        final template = _templateFromPayload(action.payload);
        if (template == null) {
          return null;
        }
        callback = () => _selectTemplate(template);
        break;
      case 'show_plan_options':
        final renew = action.payload['renew'] == true;
        callback = () => _showPlanOptions(renew: renew);
        break;
      case 'start_billing_payment':
        final planKey = action.payload['plan_key'] as String?;
        if (planKey == null || planKey.isEmpty) {
          return null;
        }
        final renew = action.payload['renew'] == true;
        callback = () => _startBillingPayment(planKey, renew: renew);
        break;
      case 'cancel_billing_subscription':
        callback = _cancelBillingSubscription;
        break;
      case 'launch_payment_url':
        final url = action.payload['url'] as String?;
        if (url == null || url.isEmpty) {
          return null;
        }
        callback = () => _launchPaymentUrl(url);
        break;
      case 'check_billing_payment':
        final paymentId = action.payload['payment_id'] as String?;
        if (paymentId == null || paymentId.isEmpty) {
          return null;
        }
        callback = () => _checkBillingPayment(paymentId);
        break;
      default:
        return null;
    }

    return _ChatAction(
      label: action.label,
      onTap: callback,
      showAsUserMessage: action.showAsUserMessage,
      actionKey: action.actionKey,
      payload: action.payload,
    );
  }

  PresentationTemplate? _templateFromPayload(Map<String, dynamic> payload) {
    final id = payload['id'];
    final name = payload['name'];
    if (id is! int || name is! String || name.isEmpty) {
      return null;
    }

    return PresentationTemplate(
      id: id,
      name: name,
      templatePath: payload['template_path'] as String?,
      previewPath: payload['preview_path'] as String?,
      templateAvailable: payload['template_available'] as bool? ?? true,
      previewAvailable: payload['preview_available'] as bool? ?? true,
    );
  }

  Map<String, dynamic> _templatePayload(PresentationTemplate template) {
    return <String, dynamic>{
      'id': template.id,
      'name': template.name,
      'template_path': template.templatePath,
      'preview_path': template.previewPath,
      'template_available': template.templateAvailable,
      'preview_available': template.previewAvailable,
    };
  }

  String _buildOutlineText(PresentationController controller) {
    final buffer = StringBuffer();
    buffer.writeln('**План презентации «${controller.title}»** 📋');
    buffer.writeln();
    for (var index = 0; index < controller.outline.length; index++) {
      buffer.writeln('${index + 1}. ${controller.outline[index]}');
    }
    return buffer.toString().trim();
  }

  String _appendBotMessage(
    String text, {
    List<List<_ChatAction>> keyboard = const <List<_ChatAction>>[],
    List<_ChatAttachment> attachments = const <_ChatAttachment>[],
    List<PresentationTemplate> templatePreviewTemplates =
        const <PresentationTemplate>[],
    _MessageLinkPreview? linkPreview,
  }) {
    final id = 'msg-${_messageCounter++}';
    setState(() {
      _messages.add(
        _ChatMessage(
          id: id,
          sender: _MessageSender.bot,
          text: text,
          sentAt: DateTime.now(),
          keyboard: keyboard,
          attachments: attachments,
          templatePreviewTemplates: templatePreviewTemplates,
          linkPreview: linkPreview,
        ),
      );
    });
    unawaited(_persistTranscript());
    _scrollToBottom();
    return id;
  }

  String _appendUserMessage(String text) {
    final id = 'msg-${_messageCounter++}';
    setState(() {
      _messages.add(
        _ChatMessage(
          id: id,
          sender: _MessageSender.user,
          text: text,
          sentAt: DateTime.now(),
        ),
      );
    });
    unawaited(_persistTranscript());
    _scrollToBottom();
    return id;
  }

  void _updateMessageById(
    String id, {
    String? text,
    List<List<_ChatAction>>? keyboard,
    List<_ChatAttachment>? attachments,
    List<PresentationTemplate>? templatePreviewTemplates,
    _MessageLinkPreview? linkPreview,
  }) {
    final index = _messages.indexWhere((message) => message.id == id);
    if (index < 0) {
      return;
    }

    setState(() {
      _messages[index] = _messages[index].copyWith(
        text: text,
        keyboard: keyboard,
        attachments: attachments,
        templatePreviewTemplates: templatePreviewTemplates,
        linkPreview: linkPreview,
      );
    });
    unawaited(_persistTranscript());
    _scrollToBottom();
  }

  void _removeMessageById(String? id) {
    if (id == null) {
      return;
    }

    final index = _messages.indexWhere((message) => message.id == id);
    if (index < 0) {
      return;
    }

    setState(() {
      _messages.removeAt(index);
    });
    unawaited(_persistTranscript());
  }

  void _clearOutlineProgressMessage() {
    _removeMessageById(_outlineProgressMessageId);
    _outlineProgressMessageId = null;
  }

  void _clearRenderProgressMessages() {
    _removeMessageById(_renderPreparationMessageId);
    _renderPreparationMessageId = null;
    _removeMessageById(_presentationStatusMessageId);
    _presentationStatusMessageId = null;
  }

  void _clearBillingProgressMessage() {
    _removeMessageById(_billingProgressMessageId);
    _billingProgressMessageId = null;
  }

  IconData _iconForKind(String kind) {
    switch (kind) {
      case 'pdf':
        return Icons.picture_as_pdf_rounded;
      case 'pptx':
        return Icons.slideshow_rounded;
      case 'docx':
        return Icons.description_rounded;
      default:
        return Icons.insert_drive_file_rounded;
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) {
        return;
      }
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent + 160,
        duration: const Duration(milliseconds: 260),
        curve: Curves.easeOutCubic,
      );
    });
  }
}

enum _ComposerMode {
  idle,
  presentationTopic,
  presentationSlides,
  outlineRevision,
}

enum _MessageSender {
  bot,
  user,
}

class _ChatMessage {
  const _ChatMessage({
    required this.id,
    required this.sender,
    required this.text,
    required this.sentAt,
    this.keyboard = const <List<_ChatAction>>[],
    this.attachments = const <_ChatAttachment>[],
    this.templatePreviewTemplates = const <PresentationTemplate>[],
    this.linkPreview,
  });

  final String id;
  final _MessageSender sender;
  final String text;
  final DateTime sentAt;
  final List<List<_ChatAction>> keyboard;
  final List<_ChatAttachment> attachments;
  final List<PresentationTemplate> templatePreviewTemplates;
  final _MessageLinkPreview? linkPreview;

  _ChatMessage copyWith({
    String? text,
    List<List<_ChatAction>>? keyboard,
    List<_ChatAttachment>? attachments,
    List<PresentationTemplate>? templatePreviewTemplates,
    _MessageLinkPreview? linkPreview,
  }) {
    return _ChatMessage(
      id: id,
      sender: sender,
      text: text ?? this.text,
      sentAt: sentAt,
      keyboard: keyboard ?? this.keyboard,
      attachments: attachments ?? this.attachments,
      templatePreviewTemplates:
          templatePreviewTemplates ?? this.templatePreviewTemplates,
      linkPreview: linkPreview,
    );
  }
}

class _ChatAction {
  const _ChatAction({
    required this.label,
    required this.onTap,
    required this.showAsUserMessage,
    required this.actionKey,
    this.payload = const <String, dynamic>{},
  });

  final String label;
  final Future<void> Function() onTap;
  final bool showAsUserMessage;
  final String actionKey;
  final Map<String, dynamic> payload;
}

class _ChatAttachment {
  const _ChatAttachment({
    required this.jobId,
    required this.artifactId,
    required this.filename,
    required this.kind,
    required this.mediaType,
    required this.remoteUri,
    required this.sourceType,
    required this.icon,
    required this.caption,
  });

  final String jobId;
  final String artifactId;
  final String filename;
  final String kind;
  final String mediaType;
  final Uri remoteUri;
  final SavedFileSourceType sourceType;
  final IconData icon;
  final String caption;
}

class _MessageLinkPreview {
  const _MessageLinkPreview({
    required this.domain,
    required this.title,
    required this.description,
    required this.url,
  });

  final String domain;
  final String title;
  final String description;
  final String url;
}

class _MessageMarkdown extends StatelessWidget {
  const _MessageMarkdown({
    required this.data,
    required this.textColor,
  });

  final String data;
  final Color textColor;

  @override
  Widget build(BuildContext context) {
    final style = MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
      p: TextStyle(
        fontSize: 15.8,
        height: 1.28,
        color: textColor,
      ),
      strong: TextStyle(
        fontSize: 15.8,
        height: 1.28,
        color: textColor,
        fontWeight: FontWeight.w700,
      ),
      em: TextStyle(
        fontSize: 15.8,
        height: 1.28,
        color: textColor,
        fontStyle: FontStyle.italic,
      ),
      a: const TextStyle(
        fontSize: 15.8,
        height: 1.28,
        color: Color(0xFF2697E8),
        decoration: TextDecoration.none,
      ),
      blockquote: TextStyle(
        fontSize: 15.8,
        height: 1.28,
        color: textColor,
      ),
      listBullet: TextStyle(
        fontSize: 15.8,
        height: 1.28,
        color: textColor,
      ),
    );

    return MarkdownBody(
      data: data,
      selectable: true,
      shrinkWrap: true,
      softLineBreak: true,
      styleSheet: style,
      onTapLink: (_, href, __) async {
        if (href == null || href.isEmpty) {
          return;
        }
        final uri = Uri.tryParse(href);
        if (uri == null) {
          return;
        }
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      },
    );
  }
}

class _ChatHeader extends StatelessWidget {
  const _ChatHeader();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 58,
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 7, 14, 7),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(
          bottom: BorderSide(
            color: Colors.black.withValues(alpha: 0.08),
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text(
            'Слайд ИИ Создать Презентацию',
            style: TextStyle(
              fontSize: 13.8,
              fontWeight: FontWeight.w600,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 2),
          const Text(
            'бот',
            style: TextStyle(
              fontSize: 11,
              color: Color(0xFF9AA1AA),
            ),
          ),
        ],
      ),
    );
  }
}

class _ComposerBar extends StatelessWidget {
  const _ComposerBar({
    required this.controller,
    required this.focusNode,
    required this.mode,
    required this.onMenuPressed,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final _ComposerMode mode;
  final VoidCallback onMenuPressed;
  final Future<void> Function() onSubmit;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 10),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(
          top: BorderSide(
            color: Colors.black.withValues(alpha: 0.08),
          ),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          FilledButton(
            onPressed: onMenuPressed,
            style: FilledButton.styleFrom(
              minimumSize: const Size(0, 42),
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
              backgroundColor: const Color(0xFF4BA7E8),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(999),
              ),
            ),
            child: const Text('Меню'),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Container(
              height: 48,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              decoration: BoxDecoration(
                color: const Color(0xFFF4F6F8),
                borderRadius: BorderRadius.circular(24),
              ),
              alignment: Alignment.center,
              child: TextField(
                controller: controller,
                focusNode: focusNode,
                minLines: 1,
                maxLines: 1,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => unawaited(onSubmit()),
                decoration: InputDecoration(
                  isCollapsed: true,
                  border: InputBorder.none,
                  hintText: switch (mode) {
                    _ComposerMode.presentationTopic =>
                      'Тема презентации и пожелания',
                    _ComposerMode.presentationSlides => 'Например, 7',
                    _ComposerMode.outlineRevision => 'Что изменить в плане?',
                    _ComposerMode.idle => null,
                  },
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          ValueListenableBuilder<TextEditingValue>(
            valueListenable: controller,
            builder: (context, value, _) {
              final hasText = value.text.trim().isNotEmpty;
              return IconButton(
                onPressed: hasText ? onSubmit : null,
                icon: const Icon(Icons.send_rounded),
                color:
                    hasText ? const Color(0xFF4BA7E8) : const Color(0xFFAEB6BF),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _ChatMessageCard extends StatelessWidget {
  const _ChatMessageCard({
    required this.message,
    required this.savedFilesRepository,
    required this.busyAttachmentIds,
    required this.onActionTap,
    required this.onAttachmentTap,
    required this.onAttachmentDeleteTap,
  });

  final _ChatMessage message;
  final SavedFilesRepository savedFilesRepository;
  final Set<String> busyAttachmentIds;
  final Future<void> Function(
    _ChatAction action,
    Future<void> Function() callback,
  ) onActionTap;
  final Future<void> Function(_ChatAttachment attachment) onAttachmentTap;
  final Future<void> Function(_ChatAttachment attachment) onAttachmentDeleteTap;

  @override
  Widget build(BuildContext context) {
    final isUser = message.sender == _MessageSender.user;
    final timeLabel = isUser
        ? '${_formatTime(message.sentAt)}  ✓✓'
        : _formatTime(message.sentAt);
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final maxWidth = math.min(
            constraints.maxWidth * (isUser ? 0.82 : 0.9),
            isUser ? 388.0 : 430.0,
          );
          return ConstrainedBox(
            constraints: BoxConstraints(maxWidth: maxWidth),
            child: Column(
              crossAxisAlignment:
                  isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                if (message.templatePreviewTemplates.isNotEmpty) ...[
                  _TemplatePreviewCard(
                    templates: message.templatePreviewTemplates,
                  ),
                  const SizedBox(height: 8),
                ],
                if (message.text.trim().isNotEmpty ||
                    message.attachments.isNotEmpty)
                  Container(
                    decoration: BoxDecoration(
                      color: isUser ? const Color(0xFFEFFFF0) : Colors.white,
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(18),
                        topRight: const Radius.circular(18),
                        bottomLeft: Radius.circular(isUser ? 18 : 4),
                        bottomRight: Radius.circular(isUser ? 4 : 18),
                      ),
                      border: Border.all(
                        color: isUser
                            ? const Color(0xFFD6F0C8)
                            : const Color(0xFFDCE4D2),
                      ),
                    ),
                    padding: const EdgeInsets.fromLTRB(14, 11, 14, 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (message.text.trim().isNotEmpty)
                          _MessageMarkdown(
                            data: message.text,
                            textColor: isUser
                                ? const Color(0xFF273226)
                                : const Color(0xFF202124),
                          ),
                        if (message.attachments.isNotEmpty) ...[
                          if (message.text.trim().isNotEmpty)
                            const SizedBox(height: 10),
                          ...message.attachments.map(
                            (attachment) => Padding(
                              padding: const EdgeInsets.only(bottom: 10),
                              child: _AttachmentTile(
                                attachment: attachment,
                                savedFilesRepository: savedFilesRepository,
                                busy: busyAttachmentIds
                                    .contains(attachment.artifactId),
                                onTap: () => onAttachmentTap(attachment),
                                onDelete: () =>
                                    onAttachmentDeleteTap(attachment),
                              ),
                            ),
                          ),
                        ],
                        if (message.linkPreview != null) ...[
                          if (message.text.trim().isNotEmpty ||
                              message.attachments.isNotEmpty)
                            const SizedBox(height: 10),
                          _LinkPreviewCard(preview: message.linkPreview!),
                        ],
                        const SizedBox(height: 2),
                        Align(
                          alignment: Alignment.bottomRight,
                          child: Text(
                            timeLabel,
                            style: TextStyle(
                              fontSize: 12,
                              color: isUser
                                  ? const Color(0xFF7A9A63)
                                  : const Color(0xFFA2A9B2),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                if (message.keyboard.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  ...message.keyboard.map(
                    (row) => Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: _KeyboardRow(
                        row: row,
                        maxWidth: maxWidth,
                        onActionTap: onActionTap,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }

  static String _formatTime(DateTime value) {
    final hour = value.hour.toString().padLeft(2, '0');
    final minute = value.minute.toString().padLeft(2, '0');
    return '$hour:$minute';
  }
}

class _AttachmentTile extends StatelessWidget {
  const _AttachmentTile({
    required this.attachment,
    required this.savedFilesRepository,
    required this.busy,
    required this.onTap,
    required this.onDelete,
  });

  final _ChatAttachment attachment;
  final SavedFilesRepository savedFilesRepository;
  final bool busy;
  final Future<void> Function() onTap;
  final Future<void> Function() onDelete;

  @override
  Widget build(BuildContext context) {
    final savedEntry =
        savedFilesRepository.findByArtifactId(attachment.artifactId);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: busy ? null : onTap,
        borderRadius: BorderRadius.circular(18),
        child: Ink(
          padding: const EdgeInsets.fromLTRB(12, 12, 10, 10),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: const Color(0xFFDDE5D8)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: const BoxDecoration(
                  color: Color(0xFF4EA3E5),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.insert_drive_file_rounded,
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      attachment.filename,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _prettyAttachmentMeta(attachment),
                      style: const TextStyle(
                        color: Color(0xFF94A3B8),
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          attachment.icon,
                          size: 17,
                          color: const Color(0xFF5C8F54),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            attachment.caption,
                            style: const TextStyle(
                              fontSize: 14,
                              height: 1.25,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              Column(
                children: [
                  InkWell(
                    onTap: busy ? null : onTap,
                    borderRadius: BorderRadius.circular(999),
                    child: Ink(
                      width: 38,
                      height: 38,
                      decoration: const BoxDecoration(
                        color: Color(0xFF7FB36D),
                        shape: BoxShape.circle,
                      ),
                      child: Center(
                        child: busy
                            ? const SizedBox.square(
                                dimension: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Icon(
                                Icons.arrow_forward_rounded,
                                color: Colors.white,
                              ),
                      ),
                    ),
                  ),
                  if (savedEntry != null && !kIsWeb) ...[
                    const SizedBox(height: 10),
                    InkWell(
                      onTap: busy ? null : onDelete,
                      borderRadius: BorderRadius.circular(999),
                      child: Ink(
                        width: 28,
                        height: 28,
                        decoration: BoxDecoration(
                          color: const Color(0xFFF5E3DE),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: const Icon(
                          Icons.delete_outline_rounded,
                          size: 16,
                          color: Color(0xFF9F5B4D),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _prettyAttachmentMeta(_ChatAttachment attachment) {
    switch (attachment.kind) {
      case 'pptx':
        return 'Презентация (PPTX)';
      case 'pdf':
        return 'Презентация (PDF)';
      case 'docx':
        return 'Документ (DOCX)';
      default:
        return attachment.kind.toUpperCase();
    }
  }
}

class _KeyboardRow extends StatelessWidget {
  const _KeyboardRow({
    required this.row,
    required this.maxWidth,
    required this.onActionTap,
  });

  final List<_ChatAction> row;
  final double maxWidth;
  final Future<void> Function(
    _ChatAction action,
    Future<void> Function() callback,
  ) onActionTap;

  @override
  Widget build(BuildContext context) {
    final width = _buttonWidthForRowLength(row.length, maxWidth);
    final compact = row.length >= 4;
    return Align(
      alignment: Alignment.centerLeft,
      child: Wrap(
        spacing: row.length >= 4 ? 3 : 6,
        runSpacing: 5,
        children: row
            .map(
              (action) => SizedBox(
                width: width,
                child: _KeyboardButton(
                  label: action.label,
                  compact: compact,
                  onPressed: () => onActionTap(action, action.onTap),
                ),
              ),
            )
            .toList(growable: false),
      ),
    );
  }

  double _buttonWidthForRowLength(int rowLength, double availableWidth) {
    if (rowLength <= 1) {
      return math.min(availableWidth - 18, 286);
    }
    if (rowLength == 2) {
      return math.min((math.min(availableWidth - 18, 286) - 6) / 2, 140);
    }
    if (rowLength == 3) {
      return 92;
    }
    return math.max(
      38,
      math.min(
        41,
        (math.min(availableWidth - 12, 330) - ((rowLength - 1) * 3)) /
            rowLength,
      ),
    );
  }
}

class _KeyboardButton extends StatelessWidget {
  const _KeyboardButton({
    required this.label,
    required this.compact,
    required this.onPressed,
  });

  final String label;
  final bool compact;
  final Future<void> Function() onPressed;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: onPressed,
      style: ElevatedButton.styleFrom(
        padding: EdgeInsets.symmetric(
          horizontal: compact ? 4 : 12,
          vertical: compact ? 10 : 10.5,
        ),
        minimumSize: Size(0, compact ? 39 : 44),
        backgroundColor: const Color(0xFF89AA6A).withValues(alpha: 0.8),
        foregroundColor: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: BorderSide(
            color: Colors.white.withValues(alpha: 0.14),
          ),
        ),
      ),
      child: Text(
        label,
        textAlign: TextAlign.center,
        style: TextStyle(
          fontWeight: FontWeight.w600,
          fontSize: compact ? 13.4 : 15.2,
          height: 1.05,
        ),
      ),
    );
  }
}

class _TemplatePreviewCard extends StatelessWidget {
  const _TemplatePreviewCard({
    required this.templates,
  });

  final List<PresentationTemplate> templates;

  @override
  Widget build(BuildContext context) {
    final items = templates.take(4).toList(growable: false);
    return Container(
      width: math.min(486, MediaQuery.of(context).size.width - 24),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFDCE4D2)),
      ),
      child: GridView.builder(
        itemCount: items.length,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          crossAxisSpacing: 10,
          mainAxisSpacing: 10,
          childAspectRatio: 1.25,
        ),
        itemBuilder: (context, index) {
          final template = items[index];
          final decoration = switch (index) {
            0 => const BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFFF1F4FB), Color(0xFFEAEFF8)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
            1 => const BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFFF2F8E7), Color(0xFFE2F3CF)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
            2 => const BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFFF4FAFF), Color(0xFF90D1FF)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
            _ => const BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFFFFFFFF), Color(0xFFFFA63F)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
          };
          return ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: Container(
              decoration: decoration.copyWith(
                border: Border.all(color: const Color(0xFFE3E8EF)),
              ),
              child: Stack(
                children: [
                  if (index == 1)
                    Positioned(
                      top: -16,
                      right: -18,
                      child: Transform.rotate(
                        angle: 0.6,
                        child: Container(
                          width: 64,
                          height: 64,
                          color: const Color(0xFFD5EDB9),
                        ),
                      ),
                    ),
                  if (index == 2)
                    Positioned(
                      bottom: -34,
                      right: -8,
                      child: Container(
                        width: 130,
                        height: 86,
                        decoration: BoxDecoration(
                          color: const Color(0xFFB5E1FF),
                          borderRadius: BorderRadius.circular(100),
                        ),
                      ),
                    ),
                  if (index == 3)
                    Positioned(
                      bottom: -20,
                      left: -8,
                      child: Container(
                        width: 160,
                        height: 58,
                        decoration: BoxDecoration(
                          color: const Color(0xFFFFB24C),
                          borderRadius: BorderRadius.circular(80),
                        ),
                      ),
                    ),
                  Center(
                    child: Text(
                      template.name.toUpperCase(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF2B3D55),
                        fontSize: 15,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _LinkPreviewCard extends StatelessWidget {
  const _LinkPreviewCard({
    required this.preview,
  });

  final _MessageLinkPreview preview;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      decoration: BoxDecoration(
        color: const Color(0xFFF7E8DA),
        borderRadius: BorderRadius.circular(10),
        border: Border(
          left: BorderSide(
            color: const Color(0xFFE29B61),
            width: 3,
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            preview.domain,
            style: const TextStyle(
              color: Color(0xFFCC6A1E),
              fontSize: 13,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            preview.title,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              height: 1.15,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            preview.description,
            style: const TextStyle(
              fontSize: 13,
              height: 1.22,
              color: Color(0xFF3F3F3F),
            ),
          ),
        ],
      ),
    );
  }
}

class _TelegramBackdrop extends StatelessWidget {
  const _TelegramBackdrop();

  static const List<IconData> _icons = <IconData>[
    Icons.local_florist_outlined,
    Icons.favorite_border_rounded,
    Icons.rocket_launch_outlined,
    Icons.icecream_outlined,
    Icons.pets_outlined,
    Icons.music_note_outlined,
    Icons.cake_outlined,
    Icons.umbrella_outlined,
    Icons.emoji_nature_outlined,
    Icons.camera_alt_outlined,
    Icons.forest_outlined,
    Icons.star_border_rounded,
  ];

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: Stack(
        children: [
          DecoratedBox(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Color(0xFFC9DFAE),
                  Color(0xFFB6D396),
                  Color(0xFFD6E6B3)
                ],
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
              ),
            ),
          ),
          IgnorePointer(
            child: Opacity(
              opacity: 0.08,
              child: GridView.builder(
                itemCount: 72,
                padding: const EdgeInsets.all(24),
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 4,
                  mainAxisSpacing: 20,
                  crossAxisSpacing: 20,
                ),
                itemBuilder: (context, index) {
                  final icon = _icons[index % _icons.length];
                  final size = switch (index % 4) {
                    0 => 16.0,
                    1 => 20.0,
                    2 => 24.0,
                    _ => 18.0,
                  };
                  return Center(
                    child: Transform.rotate(
                      angle: (index % 5) * 0.18,
                      child: Icon(
                        icon,
                        size: size,
                        color: const Color(0xFF587A55),
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}
