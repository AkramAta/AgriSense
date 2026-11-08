import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:tflite_flutter/tflite_flutter.dart';

/// On-Device TensorFlow Lite inference service using the trained 94% accuracy DenseNet model (IO platforms).
class TfliteService {
  static Interpreter? _interpreter;
  static bool _loadFailed = false;

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

  /// Initialize and cache TFLite interpreter instance
  static Future<Interpreter?> getInterpreter() async {
    if (_interpreter != null) return _interpreter;
    if (_loadFailed) return null;

    try {
      final options = InterpreterOptions()..threads = 4;
      _interpreter = await Interpreter.fromAsset(
        'assets/models/tomato_model_94_accuracy.tflite',
        options: options,
      );
      return _interpreter;
    } catch (_) {
      _loadFailed = true;
      return null;
    }
  }

  /// Classifies a tomato leaf image directly on device.
  /// Expects raw image bytes (JPEG, PNG, etc.), resizes to 256x256 RGB,
  /// normalizes to [0.0, 1.0], and runs 94% accuracy DenseNet TFLite inference.
  static Future<Map<String, dynamic>?> classifyImage(Uint8List imageBytes) async {
    final interpreter = await getInterpreter();
    if (interpreter == null) return null;

    try {
      final buffer = await ui.ImmutableBuffer.fromUint8List(imageBytes);
      final descriptor = await ui.ImageDescriptor.encoded(buffer);
      final codec = await descriptor.instantiateCodec(targetWidth: 256, targetHeight: 256);
      final frame = await codec.getNextFrame();
      final byteData = await frame.image.toByteData(format: ui.ImageByteFormat.rawRgba);
      if (byteData == null) return null;

      final rawRgba = byteData.buffer.asUint8List();

      // Input tensor shape: [1, 256, 256, 3] float32 normalized [0.0, 1.0]
      final input = List.generate(
        1,
        (_) => List.generate(
          256,
          (y) => List.generate(
            256,
            (x) {
              final idx = (y * 256 + x) * 4;
              return [
                rawRgba[idx] / 255.0,
                rawRgba[idx + 1] / 255.0,
                rawRgba[idx + 2] / 255.0,
              ];
            },
          ),
        ),
      );

      // Output tensor shape: [1, 10]
      final output = List.generate(1, (_) => List.filled(10, 0.0));
      interpreter.run(input, output);

      final probs = output[0];
      int bestIdx = 0;
      double maxProb = -1.0;
      for (int i = 0; i < probs.length; i++) {
        if (probs[i] > maxProb) {
          maxProb = probs[i];
          bestIdx = i;
        }
      }

      final allProbs = <String, double>{};
      for (int i = 0; i < classNames.length; i++) {
        allProbs[classNames[i]] = double.parse(probs[i].toStringAsFixed(4));
      }

      return {
        'class_name': classNames[bestIdx],
        'confidence': double.parse(maxProb.toStringAsFixed(3)),
        'probabilities': allProbs,
      };
    } catch (_) {
      return null;
    }
  }

  /// Close interpreter and release native resources
  static void close() {
    _interpreter?.close();
    _interpreter = null;
    _loadFailed = false;
  }
}

