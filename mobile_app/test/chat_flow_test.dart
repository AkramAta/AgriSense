import 'package:flutter_test/flutter_test.dart';
import 'package:agrisense_mobile/services/gemini_service.dart';

void main() {
  group('GeminiService Dynamic Offline Chat Flow Tests', () {
    late GeminiService service;
    final activeEarlyBlightDiag = {
      'class_name': 'Tomato___Early_blight',
      'confidence': 0.954,
      'symptoms': 'Concentric rings resembling a target board with dark brown necrotic tissue.',
      'chemical_control': 'Apply Chlorothalonil or Mancozeb every 7-10 days.',
      'organic_control': 'Apply copper soap or potassium bicarbonate.',
      'cultural_practices': 'Prune lower foliage 12 inches above soil line.',
    };

    setUp(() {
      service = GeminiService();
    });

    test('Response for "help me" gives direct guidance without repetitive menus', () async {
      final reply = await service.sendChatMessage('help me', activeDiagnosis: activeEarlyBlightDiag);
      expect(reply, contains('Early Blight'));
      expect(reply, contains('Immediate Fix'));
      expect(reply, contains('Protective Spray'));
    });

    test('Response for "I don\'t understand explain" gives plain-English simplified guidance', () async {
      final reply = await service.sendChatMessage(
        "I don't understand explain",
        activeDiagnosis: activeEarlyBlightDiag,
        previousBotAnswers: ['Here is your initial advice...'],
      );
      expect(reply, contains('No problem at all! Let me explain this in simple, everyday language'));
      expect(reply, contains('Early Blight'));
      expect(reply, contains('Snip off the sick leaves'));
      expect(reply, contains('Water only the roots'));
      expect(reply, contains('Apply a protective spray'));
    });

    test('Response for "I want steps" gives 5-stage action plan', () async {
      final reply = await service.sendChatMessage('I want steps', activeDiagnosis: activeEarlyBlightDiag);
      expect(reply, contains('5-Stage Action Plan for Early Blight Remediation'));
      expect(reply, contains('Step 1: Immediate Sanitation & Leaf Pruning'));
      expect(reply, contains('Step 2: Targeted Foliar Spray Application'));
      expect(reply, contains('Step 3: Canopy Aeration & Trellising'));
      expect(reply, contains('Step 4: Irrigation Guard & Soil Barrier'));
      expect(reply, contains('Step 5: Follow-Up Scouting & Resistance Management'));
    });

    test('Response for "is there another solution ?" gives alternative & biological solutions', () async {
      final reply = await service.sendChatMessage('is there another solution ?', activeDiagnosis: activeEarlyBlightDiag);
      expect(reply, contains('Alternative & Organic Solutions for Early Blight'));
      expect(reply, contains('Bacillus subtilis'));
      expect(reply, contains('Systemic Resistance Inducer'));
    });

    test('Response for "how often should I spray?" gives dosage & intervals', () async {
      final reply = await service.sendChatMessage('how often should I spray?', activeDiagnosis: activeEarlyBlightDiag);
      expect(reply, contains('Spray Dosage & Application Protocol for Early Blight'));
      expect(reply, contains('7 to 10 days'));
      expect(reply, contains('6:00 AM – 9:00 AM'));
    });

    test('Multi-turn conversation: "help me" followed by "I don\'t understand explain" never repeats', () async {
      // Turn 1
      final r1 = await service.sendChatMessage('help me', activeDiagnosis: activeEarlyBlightDiag);
      // Turn 2
      final r2 = await service.sendChatMessage("I don't understand explain",
          activeDiagnosis: activeEarlyBlightDiag, previousBotAnswers: [r1]);
      // Turn 3
      final r3 = await service.sendChatMessage('I want steps',
          activeDiagnosis: activeEarlyBlightDiag, previousBotAnswers: [r1, r2]);

      expect(r1 != r2, isTrue);
      expect(r2 != r3, isTrue);
      expect(r1 != r3, isTrue);
      expect(r2.contains("simple, everyday language"), isTrue);
      expect(r3.contains("5-Stage Action Plan"), isTrue);
    });

    test('Healthy diagnosis responses are polite, informative, and adaptive', () async {
      final healthyDiag = {
        'class_name': 'Tomato___healthy',
        'confidence': 0.965,
        'is_healthy': true,
      };

      final rHelp = await service.sendChatMessage('help me', activeDiagnosis: healthyDiag);
      expect(rHelp, contains('Healthy'));
      expect(rHelp, contains('Watering Schedules'));

      final rExplain = await service.sendChatMessage('explain', activeDiagnosis: healthyDiag, previousBotAnswers: [rHelp]);
      expect(rExplain != rHelp, isTrue);
      expect(rExplain, contains('great shape'));
    });
  });
}
