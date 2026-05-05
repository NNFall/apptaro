import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../../core/config/app_config.dart';
import '../../domain/models/billing_payment.dart';
import '../../domain/models/billing_summary.dart';
import '../../domain/models/outline_result.dart';
import '../../domain/models/presentation_template.dart';
import '../../domain/models/remote_job.dart';
import '../repositories/backend_config_repository.dart';
import '../repositories/client_session_repository.dart';

class AppSlidesApiClient {
  AppSlidesApiClient({
    http.Client? client,
    BackendConfigRepository? backendConfig,
    ClientSessionRepository? clientSession,
  })  : _client = client ?? http.Client(),
        _backendConfig = backendConfig ?? BackendConfigRepository(),
        _clientSession = clientSession ?? ClientSessionRepository();

  final http.Client _client;
  final BackendConfigRepository _backendConfig;
  final ClientSessionRepository _clientSession;

  Future<bool> healthcheck() async {
    final payload = await _getJsonMap(AppConfig.healthPath);
    return payload['status'] == 'ok';
  }

  Future<List<PresentationTemplate>> fetchTemplates() async {
    final payload = await _getJsonMap(AppConfig.templatesPath);
    final rawTemplates =
        payload['templates'] as List<dynamic>? ?? const <dynamic>[];
    return rawTemplates
        .whereType<Map>()
        .map((item) =>
            PresentationTemplate.fromJson(item.cast<String, dynamic>()))
        .toList();
  }

  Future<OutlineResult> generateOutline({
    required String topic,
    required int slidesTotal,
  }) async {
    final payload = await _postJson(
      path: AppConfig.outlinePath,
      body: <String, Object>{
        'topic': topic,
        'slides_total': slidesTotal,
      },
    );
    return OutlineResult.fromJson(payload);
  }

  Future<OutlineResult> reviseOutline({
    required String topic,
    required int slidesTotal,
    required List<String> outline,
    required String comment,
    String? title,
  }) async {
    final payload = await _postJson(
      path: AppConfig.outlineRevisePath,
      body: <String, Object?>{
        'topic': topic,
        'slides_total': slidesTotal,
        'outline': outline,
        'comment': comment,
        'title': title,
      },
    );
    return OutlineResult.fromJson(payload);
  }

  Future<RemoteJob> createPresentationJob({
    required String topic,
    required String title,
    required List<String> outline,
    required int designId,
    bool generatePdf = true,
    String? teaserFirstText,
  }) async {
    final payload = await _postJson(
      path: AppConfig.presentationJobsPath,
      body: <String, Object?>{
        'topic': topic,
        'title': title,
        'outline': outline,
        'design_id': designId,
        'generate_pdf': generatePdf,
        'teaser_first_text': teaserFirstText,
      },
    );
    return RemoteJob.fromJson(payload);
  }

  Future<RemoteJob> getPresentationJob(String jobId) async {
    final payload = await _getJsonMap(AppConfig.presentationJobPath(jobId));
    return RemoteJob.fromJson(payload);
  }

  Future<RemoteJob> createConversionJob({
    required List<int> bytes,
    required String filename,
    required String targetFormat,
  }) async {
    final request = http.MultipartRequest(
      'POST',
      _resolve(AppConfig.conversionJobsPath),
    )
      ..fields['target_format'] = targetFormat
      ..headers.addAll(await _requestHeaders())
      ..files.add(
        http.MultipartFile.fromBytes(
          'file',
          bytes,
          filename: filename,
        ),
      );

    final streamed = await _client.send(request);
    final response = await http.Response.fromStream(streamed);
    final payload = _decodeResponse(response);
    _ensureSuccess(response, payload);
    return RemoteJob.fromJson(payload);
  }

  Future<RemoteJob> getConversionJob(String jobId) async {
    final payload = await _getJsonMap(AppConfig.conversionJobPath(jobId));
    return RemoteJob.fromJson(payload);
  }

  Uri presentationDownloadUri(String jobId, {required String format}) {
    return _resolve(AppConfig.presentationDownloadPath(jobId, format));
  }

  Uri conversionDownloadUri(String jobId) {
    return _resolve(AppConfig.conversionDownloadPath(jobId));
  }

  Future<Uint8List> downloadBytes(Uri uri) async {
    final response = await _client.get(
      uri,
      headers: await _requestHeaders(),
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response.bodyBytes;
    }

    final message = response.bodyBytes.isEmpty
        ? 'Unexpected backend error'
        : utf8.decode(response.bodyBytes, allowMalformed: true);
    throw AppSlidesApiException(
      statusCode: response.statusCode,
      message: message,
    );
  }

  void close() {
    _client.close();
  }

  Future<BillingSummary> fetchBillingSummary() async {
    final payload = await _getJsonMap(AppConfig.billingSummaryPath);
    return BillingSummary.fromJson(payload);
  }

  Future<BillingPayment> createBillingPayment({
    required String planKey,
    bool renew = false,
  }) async {
    final payload = await _postJson(
      path: AppConfig.billingPaymentsPath,
      body: <String, Object>{
        'plan_key': planKey,
        'context': renew ? 'renew' : 'new',
      },
    );
    return BillingPayment.fromJson(payload);
  }

  Future<BillingPayment> getBillingPayment(String paymentId) async {
    final payload = await _getJsonMap(AppConfig.billingPaymentPath(paymentId));
    return BillingPayment.fromJson(payload);
  }

  Future<BillingSummary> cancelBillingSubscription() async {
    final response = await _client.post(
      _resolve(AppConfig.billingCancelSubscriptionPath),
      headers: await _jsonHeaders(),
      body: '{}',
    );
    final payload = _decodeResponse(response);
    _ensureSuccess(response, payload);
    return BillingSummary.fromJson(payload);
  }

  Future<Map<String, dynamic>> _getJsonMap(String path) async {
    final response = await _client.get(
      _resolve(path),
      headers: await _jsonHeaders(),
    );
    final payload = _decodeResponse(response);
    _ensureSuccess(response, payload);
    return payload;
  }

  Future<Map<String, dynamic>> _postJson({
    required String path,
    required Map<String, Object?> body,
  }) async {
    final response = await _client.post(
      _resolve(path),
      headers: await _jsonHeaders(),
      body: utf8.encode(jsonEncode(body)),
    );
    final payload = _decodeResponse(response);
    _ensureSuccess(response, payload);
    return payload;
  }

  Uri _resolve(String path) => _baseUri.resolve(path);

  Uri get _baseUri => Uri.parse(_backendConfig.baseUrl);

  Future<Map<String, String>> _jsonHeaders() async {
    final headers = await _requestHeaders();
    headers['Content-Type'] = 'application/json; charset=utf-8';
    return headers;
  }

  Future<Map<String, String>> _requestHeaders() async {
    final clientId = await _clientSession.getOrCreateClientId();
    return <String, String>{
      'Accept': 'application/json',
      'X-Apptaro-Client-Id': clientId,
      'X-AppSlides-Client-Id': clientId,
    };
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    if (response.bodyBytes.isEmpty) {
      return <String, dynamic>{};
    }
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    if (decoded is Map) {
      return decoded.cast<String, dynamic>();
    }
    return <String, dynamic>{
      'data': decoded,
    };
  }

  void _ensureSuccess(http.Response response, Map<String, dynamic> payload) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return;
    }
    final detail = payload['detail']?.toString() ?? response.body;
    throw AppSlidesApiException(
      statusCode: response.statusCode,
      message: detail.isEmpty ? 'Unexpected backend error' : detail,
    );
  }
}

class AppSlidesApiException implements Exception {
  const AppSlidesApiException({
    required this.statusCode,
    required this.message,
  });

  final int statusCode;
  final String message;

  @override
  String toString() {
    return 'AppSlidesApiException(statusCode: $statusCode, message: $message)';
  }
}
