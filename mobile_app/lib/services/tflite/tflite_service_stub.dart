import 'dart:typed_data';

/// Stub implementation of TfliteService for platforms that do not support dart:ffi (e.g. Web).
class TfliteService {
  /// Alphabetical 10 tomato leaf disease classes matching model training output
  static const List<String> classNames = [
    'Tomato___Bacterial_spot',
    'Tomato___Early_blight',
    'Tomato___Late_blight',
    'Tomato___Leaf_Mold',
    'Tomato___Septoria_leaf_spot',
    'Tomato___Spider_mites Two-spotted_spider_mite',
    'Tomato___Target_Spot',
    'Tomato___Tomato_Yellow_Leaf_Curl_Virus',
    'Tomato___Tomato_mosaic_virus',
    'Tomato___healthy',
  ];

  static Future<dynamic> getInterpreter() async => null;

  /// Web fallback returns null so app gracefully uses on-device color/rules or cloud/edge server
  static Future<Map<String, dynamic>?> classifyImage(Uint8List imageBytes) async => null;

  static void close() {}
}

