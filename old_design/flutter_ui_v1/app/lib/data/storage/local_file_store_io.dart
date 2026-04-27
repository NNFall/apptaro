import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

abstract class LocalFileStore {
  Future<StoredLocalFile> save({
    required Uint8List bytes,
    required String filename,
    required String uniqueHint,
  });

  Future<bool> exists(String path);
  Future<bool> delete(String path);
}

class StoredLocalFile {
  const StoredLocalFile({
    required this.path,
    required this.sizeBytes,
  });

  final String path;
  final int sizeBytes;
}

LocalFileStore createLocalFileStore() => _IoLocalFileStore();

class _IoLocalFileStore implements LocalFileStore {
  static const String _directoryName = 'appslides_files';

  @override
  Future<bool> exists(String path) async {
    if (path.isEmpty) {
      return false;
    }
    return File(path).exists();
  }

  @override
  Future<bool> delete(String path) async {
    if (path.isEmpty) {
      return false;
    }

    final file = File(path);
    if (!await file.exists()) {
      return false;
    }

    await file.delete();
    return true;
  }

  @override
  Future<StoredLocalFile> save({
    required Uint8List bytes,
    required String filename,
    required String uniqueHint,
  }) async {
    final documentsDir = await getApplicationDocumentsDirectory();
    final targetDir = Directory(
      '${documentsDir.path}${Platform.pathSeparator}$_directoryName',
    );
    await targetDir.create(recursive: true);

    final sanitizedName = _sanitizeFilename(filename);
    final storedName =
        '${DateTime.now().millisecondsSinceEpoch}_${_sanitizeFilename(uniqueHint)}_$sanitizedName';
    final file = File(
      '${targetDir.path}${Platform.pathSeparator}$storedName',
    );
    await file.writeAsBytes(bytes, flush: true);

    return StoredLocalFile(
      path: file.path,
      sizeBytes: bytes.length,
    );
  }

  String _sanitizeFilename(String value) {
    final normalized = value.trim().replaceAll(RegExp(r'\s+'), '_');
    final cleaned = normalized.replaceAll(RegExp(r'[^A-Za-z0-9._-]'), '');
    if (cleaned.isEmpty) {
      return 'file';
    }
    return cleaned;
  }
}
