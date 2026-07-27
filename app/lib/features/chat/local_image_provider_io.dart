import 'dart:io';

import 'package:flutter/painting.dart';

ImageProvider<Object>? localImageProvider(String? path) {
  if (path == null || path.isEmpty) {
    return null;
  }
  return FileImage(File(path));
}
