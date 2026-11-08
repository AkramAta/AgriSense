import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter_test/flutter_test.dart';
import 'package:agrisense_mobile/services/agrisense_cnn.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('Test AgriSenseTomatoCNN binary loader and prediction', () async {
    final file = File('assets/cnn_weights.bin');
    final bytes = await file.readAsBytes();
    final byteData = ByteData.sublistView(bytes);

    final cnn = AgriSenseTomatoCNN.fromBinary(byteData);
    expect(cnn.b1W.length, 432);
    expect(cnn.fcW.length, 640);
    expect(cnn.fcB.length, 10);

    final dummy = Float32List(3 * 96 * 96);
    final probs = cnn.predict(dummy);
    expect(probs.length, 10);

    double sum = probs.reduce((a, b) => a + b);
    expect((sum - 1.0).abs() < 1e-4, isTrue);
  });

  test('Test AgriSenseTomatoCNN on Early Blight image', () async {
    final binFile = File('assets/cnn_weights.bin');
    final binBytes = await binFile.readAsBytes();
    final byteData = ByteData.sublistView(binBytes);
    final cnn = AgriSenseTomatoCNN.fromBinary(byteData);

    final leafFile = File(r'C:\Users\Raya\Desktop\Eng A\level 400\Semester 1\AgriSense\leaf_crop.jpg');
    if (!leafFile.existsSync()) return;

    final imgBytes = await leafFile.readAsBytes();
    final buffer = await ui.ImmutableBuffer.fromUint8List(imgBytes);
    final descriptor = await ui.ImageDescriptor.encoded(buffer);
    final codec = await descriptor.instantiateCodec(targetWidth: 96, targetHeight: 96);
    final frame = await codec.getNextFrame();
    final rawData = await frame.image.toByteData(format: ui.ImageByteFormat.rawRgba);
    final rawRgba = rawData!.buffer.asUint8List();

    final chw = Float32List(3 * 96 * 96);
    const plane = 96 * 96;
    for (int i = 0; i < plane; i++) {
      final r = rawRgba[i * 4] / 255.0;
      final g = rawRgba[i * 4 + 1] / 255.0;
      final b = rawRgba[i * 4 + 2] / 255.0;

      chw[i] = (r - 0.485) / 0.229;
      chw[plane + i] = (g - 0.456) / 0.224;
      chw[2 * plane + i] = (b - 0.406) / 0.225;
    }

    final probs = cnn.predict(chw);
    final maxVal = probs.reduce(math.max);
    final topIndex = probs.indexOf(maxVal);
    expect(AgriSenseTomatoCNN.classNames[topIndex].contains('blight'), isTrue);
  });
}
