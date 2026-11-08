import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';
import 'package:flutter/services.dart' show rootBundle;

/// Pure Dart Implementation of AgriSense 10-Class Convolutional Neural Network (CNN).
/// Executes on-device in real-time (~90ms) with zero cloud/Gemini dependency.
class AgriSenseTomatoCNN {
  static const List<String> classNames = [
    'Tomato___Bacterial_spot',
    'Tomato___Early_blight',
    'Tomato___Late_blight',
    'Tomato___Leaf_Mold',
    'Tomato___Septoria_leaf_spot',
    'Tomato___Spider_mites_Two_spotted_spider_mite',
    'Tomato___Target_Spot',
    'Tomato___Tomato_Yellow_Leaf_Curl_Virus',
    'Tomato___Tomato_mosaic_virus',
    'Tomato___healthy',
  ];

  final Float32List b1W, b1B;
  final Float32List b2W, b2B;
  final Float32List b3W, b3B;
  final Float32List b4W, b4B;
  final Float32List fcW, fcB;

  AgriSenseTomatoCNN({
    required this.b1W,
    required this.b1B,
    required this.b2W,
    required this.b2B,
    required this.b3W,
    required this.b3B,
    required this.b4W,
    required this.b4B,
    required this.fcW,
    required this.fcB,
  });

  static AgriSenseTomatoCNN fromBinary(ByteData byteData) {
    final all = byteData.buffer.asFloat32List(byteData.offsetInBytes, 61162);
    int offset = 0;

    Float32List slice(int count) {
      final res = all.sublist(offset, offset + count);
      offset += count;
      return res;
    }

    final b1W = slice(16 * 3 * 3 * 3); // 432
    final b1B = slice(16);             // 16
    final b2W = slice(32 * 16 * 3 * 3);// 4608
    final b2B = slice(32);             // 32
    final b3W = slice(64 * 32 * 3 * 3);// 18432
    final b3B = slice(64);             // 64
    final b4W = slice(64 * 64 * 3 * 3);// 36864
    final b4B = slice(64);             // 64
    final fcW = slice(10 * 64);        // 640
    final fcB = slice(10);             // 10

    return AgriSenseTomatoCNN(
      b1W: b1W,
      b1B: b1B,
      b2W: b2W,
      b2B: b2B,
      b3W: b3W,
      b3B: b3B,
      b4W: b4W,
      b4B: b4B,
      fcW: fcW,
      fcB: fcB,
    );
  }

  static AgriSenseTomatoCNN fromJson(Map<String, dynamic> json) {
    Float32List toF32(dynamic list) {
      final l = list as List;
      final out = Float32List(l.length);
      for (int i = 0; i < l.length; i++) {
        out[i] = (l[i] as num).toDouble();
      }
      return out;
    }

    return AgriSenseTomatoCNN(
      b1W: toF32(json['block1.0.weight']),
      b1B: toF32(json['block1.0.bias']),
      b2W: toF32(json['block2.0.weight']),
      b2B: toF32(json['block2.0.bias']),
      b3W: toF32(json['block3.0.weight']),
      b3B: toF32(json['block3.0.bias']),
      b4W: toF32(json['block4.0.weight']),
      b4B: toF32(json['block4.0.bias']),
      fcW: toF32(json['classifier.weight']),
      fcB: toF32(json['classifier.bias']),
    );
  }

  static AgriSenseTomatoCNN? _instance;

  static Future<AgriSenseTomatoCNN?> loadInstance() async {
    if (_instance != null) return _instance;
    try {
      final byteData = await rootBundle.load('assets/cnn_weights.bin');
      _instance = AgriSenseTomatoCNN.fromBinary(byteData);
      return _instance;
    } catch (_) {
      try {
        // Fallback for unit tests or standalone execution environments
        final file = File('assets/cnn_weights.bin');
        if (file.existsSync()) {
          final bytes = await file.readAsBytes();
          _instance = AgriSenseTomatoCNN.fromBinary(ByteData.sublistView(bytes));
          return _instance;
        }
      } catch (_) {}
      return null;
    }
  }

  static Float32List _convReluPool({
    required Float32List input,
    required int inC,
    required int inH,
    required int inW,
    required Float32List weights,
    required Float32List bias,
    required int outC,
  }) {
    final outH = inH ~/ 2;
    final outW = inW ~/ 2;
    final output = Float32List(outC * outH * outW);

    for (int oc = 0; oc < outC; oc++) {
      final b = bias[oc];
      final wOffsetOc = oc * inC * 9;

      for (int oh = 0; oh < outH; oh++) {
        final ih0 = oh * 2;
        for (int ow = 0; ow < outW; ow++) {
          final iw0 = ow * 2;
          double maxVal = -1e9;

          for (int ph = 0; ph < 2; ph++) {
            final ih = ih0 + ph;
            for (int pw = 0; pw < 2; pw++) {
              final iw = iw0 + pw;
              double sum = b;

              for (int ic = 0; ic < inC; ic++) {
                final wBase = wOffsetOc + ic * 9;

                for (int kh = -1; kh <= 1; kh++) {
                  final h = ih + kh;
                  if (h < 0 || h >= inH) continue;
                  final hOffset = (ic * inH + h) * inW;
                  final kwBase = wBase + (kh + 1) * 3 + 1;

                  for (int kw = -1; kw <= 1; kw++) {
                    final w = iw + kw;
                    if (w < 0 || w >= inW) continue;
                    sum += input[hOffset + w] * weights[kwBase + kw];
                  }
                }
              }

              if (sum < 0) sum = 0; // ReLU
              if (sum > maxVal) maxVal = sum; // MaxPool
            }
          }
          output[(oc * outH + oh) * outW + ow] = maxVal;
        }
      }
    }
    return output;
  }

  /// Evaluates an input image tensor of shape (3, 96, 96) normalized via PyTorch ImageNet standards.
  List<double> predict(Float32List normalizedChwImage) {
    // Block 1: (3, 96, 96) -> (16, 48, 48)
    final x1 = _convReluPool(
      input: normalizedChwImage,
      inC: 3,
      inH: 96,
      inW: 96,
      weights: b1W,
      bias: b1B,
      outC: 16,
    );

    // Block 2: (16, 48, 48) -> (32, 24, 24)
    final x2 = _convReluPool(
      input: x1,
      inC: 16,
      inH: 48,
      inW: 48,
      weights: b2W,
      bias: b2B,
      outC: 32,
    );

    // Block 3: (32, 24, 24) -> (64, 12, 12)
    final x3 = _convReluPool(
      input: x2,
      inC: 32,
      inH: 24,
      inW: 24,
      weights: b3W,
      bias: b3B,
      outC: 64,
    );

    // Block 4: (64, 12, 12) -> (64, 6, 6)
    final x4 = _convReluPool(
      input: x3,
      inC: 64,
      inH: 12,
      inW: 12,
      weights: b4W,
      bias: b4B,
      outC: 64,
    );

    // AdaptiveAvgPool2d((1, 1)) on (64, 6, 6)
    final gap = Float32List(64);
    const planeArea = 36; // 6x6
    for (int c = 0; c < 64; c++) {
      double sum = 0;
      final offset = c * planeArea;
      for (int i = 0; i < planeArea; i++) {
        sum += x4[offset + i];
      }
      gap[c] = sum / planeArea;
    }

    // Classifier Linear(64, 10)
    final logits = Float32List(10);
    double maxLogit = -1e9;
    for (int i = 0; i < 10; i++) {
      double sum = fcB[i];
      final wOffset = i * 64;
      for (int c = 0; c < 64; c++) {
        sum += gap[c] * fcW[wOffset + c];
      }
      logits[i] = sum;
      if (sum > maxLogit) maxLogit = sum;
    }

    // Softmax probabilities
    double sumExp = 0;
    final exps = Float32List(10);
    for (int i = 0; i < 10; i++) {
      exps[i] = math.exp(logits[i] - maxLogit);
      sumExp += exps[i];
    }

    final probs = List<double>.filled(10, 0);
    for (int i = 0; i < 10; i++) {
      probs[i] = exps[i] / sumExp;
    }
    return probs;
  }
}
