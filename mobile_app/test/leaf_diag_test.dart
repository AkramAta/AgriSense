import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:agrisense_mobile/services/gemini_service.dart';

void main() {
  test('Diagnose real leaf image, cropped leaf, and healthy leaf', () async {
    final service = GeminiService();

    final file1 = File(r'C:\Users\Raya\.gemini\antigravity\brain\86077a1b-9c30-4b4d-a9dd-d8c217d78786\.user_uploaded\media_1794098251583_91ae0899.jpg');
    if (file1.existsSync()) {
      final bytes1 = await file1.readAsBytes();
      final res1 = await service.diagnoseLeafImage(bytes1, imageName: 'scaled_image_123.jpg');
      expect(res1['class_name'], equals('Tomato___Early_blight'));
    }

    final file2 = File('build/leaf_crop.jpg');
    if (file2.existsSync()) {
      final bytes2 = await file2.readAsBytes();
      final res2 = await service.diagnoseLeafImage(bytes2, imageName: 'camera_leaf.jpg');
      expect(res2['class_name'], equals('Tomato___Early_blight'));
    }

    final healthyDir = Directory(r'C:\Users\Raya\Desktop\Eng A\level 400\Semester 1\AgriSense\ml\dataset\tomato\val\Tomato___healthy');
    if (healthyDir.existsSync()) {
      final healthyFiles = healthyDir.listSync().whereType<File>().toList();
      if (healthyFiles.isNotEmpty) {
        final healthyBytes = await healthyFiles.first.readAsBytes();
        final healthyRes = await service.diagnoseLeafImage(healthyBytes, imageName: 'photo_001.jpg');
        expect(healthyRes['class_name'], equals('Tomato___healthy'));
      }
    }
  });
}
