import 'package:flutter_test/flutter_test.dart';
import 'package:agrisense_mobile/services/gemini_service.dart';

void main() {
  group('GeminiService Dynamic Offline Chat Flow Tests', () {
    late GeminiService service;
    final activeSeptoriaDiag = {
      'class_name': 'Tomato___Septoria_leaf_spot',
      'confidence': 0.94,
      'symptoms': 'Circular necrotic lesions with dark borders.',
      'chemical_control': 'Apply Chlorothalonil or Mancozeb every 7-14 days.',
      'organic_control': 'Spray copper soap or bio-fungicide.',
      'cultural_practices': 'Prune lower foliage and stake vines.',
    };

    setUp(() {
      service = GeminiService();
    });

    test('Response for "can you help me" gives specialist clinical consultation without menus', () async {
      final reply = await service.sendChatMessage('can you help me', activeDiagnosis: activeSeptoriaDiag);
      expect(reply, contains('Specialist Clinical Consultation: Septoria Leaf Spot'));
      expect(reply, contains('Fungal Pathology Assessment'));
      expect(reply, contains('Prescribed Clinical Remediation Plan'));
      expect(reply.contains('How would you like to proceed?'), isFalse);
      expect(reply.contains('Say "I want steps"'), isFalse);
    });

    test('Response for "I want steps" gives 5-stage action plan', () async {
      final reply = await service.sendChatMessage('I want steps', activeDiagnosis: activeSeptoriaDiag);
      expect(reply, contains('5-Stage Action Plan for Septoria Leaf Spot Remediation'));
      expect(reply, contains('Step 1: Immediate Sanitation & Leaf Pruning'));
      expect(reply, contains('Step 2: Targeted Foliar Spray Application'));
      expect(reply, contains('Step 3: Canopy Aeration & Trellising'));
      expect(reply, contains('Step 4: Irrigation Guard & Soil Barrier'));
      expect(reply, contains('Step 5: Follow-Up Scouting & Resistance Management'));
    });

    test('Response for "is there another solution ?" gives alternative & biological solutions', () async {
      final reply = await service.sendChatMessage('is there another solution ?', activeDiagnosis: activeSeptoriaDiag);
      expect(reply, contains('Alternative & Biological Solutions for Septoria Leaf Spot'));
      expect(reply, contains('Bacillus subtilis'));
      expect(reply, contains('Systemic Resistance Inducer'));
    });

    test('Response for "how often should I spray?" gives dosage & intervals', () async {
      final reply = await service.sendChatMessage('how often should I spray?', activeDiagnosis: activeSeptoriaDiag);
      expect(reply, contains('Spray Dosage & Application Protocol for Septoria Leaf Spot'));
      expect(reply, contains('7 to 10 days'));
      expect(reply, contains('6:00 AM – 9:00 AM'));
    });

    test('Sequential questions produce completely different answers', () async {
      final r1 = await service.sendChatMessage('can you help me', activeDiagnosis: activeSeptoriaDiag);
      final r2 = await service.sendChatMessage('I want steps', activeDiagnosis: activeSeptoriaDiag);
      final r3 = await service.sendChatMessage('is there another solution ?', activeDiagnosis: activeSeptoriaDiag);

      expect(r1 != r2, isTrue);
      expect(r2 != r3, isTrue);
      expect(r1 != r3, isTrue);
    });
  });
}

