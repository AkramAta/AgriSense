/// Conditional export for TFLite service:
/// Uses native TFLite (via dart:ffi) on IO platforms (Android, iOS, Desktop),
/// and falls back to a clean stub on Web where dart:ffi is unavailable.
library tflite_service;

export 'tflite/tflite_service_stub.dart'
    if (dart.library.io) 'tflite/tflite_service_io.dart';
