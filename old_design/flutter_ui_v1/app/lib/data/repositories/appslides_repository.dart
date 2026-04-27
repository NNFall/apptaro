import 'dart:typed_data';

import '../../domain/models/outline_result.dart';
import '../../domain/models/presentation_template.dart';
import '../../domain/models/remote_job.dart';
import '../api/appslides_api_client.dart';
import 'backend_config_repository.dart';

class AppSlidesRepository {
  AppSlidesRepository({
    AppSlidesApiClient? api,
    BackendConfigRepository? backendConfig,
  }) : _api = api ?? AppSlidesApiClient(backendConfig: backendConfig);

  final AppSlidesApiClient _api;

  Future<bool> healthcheck() => _api.healthcheck();

  Future<List<PresentationTemplate>> fetchTemplates() => _api.fetchTemplates();

  Future<OutlineResult> generateOutline({
    required String topic,
    required int slidesTotal,
  }) {
    return _api.generateOutline(
      topic: topic,
      slidesTotal: slidesTotal,
    );
  }

  Future<OutlineResult> reviseOutline({
    required String topic,
    required int slidesTotal,
    required List<String> outline,
    required String comment,
    String? title,
  }) {
    return _api.reviseOutline(
      topic: topic,
      slidesTotal: slidesTotal,
      outline: outline,
      comment: comment,
      title: title,
    );
  }

  Future<RemoteJob> createPresentationJob({
    required String topic,
    required String title,
    required List<String> outline,
    required int designId,
    bool generatePdf = true,
  }) {
    return _api.createPresentationJob(
      topic: topic,
      title: title,
      outline: outline,
      designId: designId,
      generatePdf: generatePdf,
    );
  }

  Future<RemoteJob> getPresentationJob(String jobId) {
    return _api.getPresentationJob(jobId);
  }

  Future<RemoteJob> createConversionJob({
    required List<int> bytes,
    required String filename,
    required String targetFormat,
  }) {
    return _api.createConversionJob(
      bytes: bytes,
      filename: filename,
      targetFormat: targetFormat,
    );
  }

  Future<RemoteJob> getConversionJob(String jobId) {
    return _api.getConversionJob(jobId);
  }

  Uri presentationDownloadUri(String jobId, {required String format}) {
    return _api.presentationDownloadUri(jobId, format: format);
  }

  Uri conversionDownloadUri(String jobId) {
    return _api.conversionDownloadUri(jobId);
  }

  Future<Uint8List> downloadBytes(Uri uri) {
    return _api.downloadBytes(uri);
  }

  void dispose() {
    _api.close();
  }
}
