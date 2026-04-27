import 'dart:typed_data';

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

LocalFileStore createLocalFileStore() => _UnsupportedLocalFileStore();

class _UnsupportedLocalFileStore implements LocalFileStore {
  @override
  Future<bool> exists(String path) async => false;

  @override
  Future<bool> delete(String path) async => false;

  @override
  Future<StoredLocalFile> save({
    required Uint8List bytes,
    required String filename,
    required String uniqueHint,
  }) {
    throw UnsupportedError('Local file storage is unavailable on this platform.');
  }
}
