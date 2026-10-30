import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:intl/intl.dart';
import '../services/esp32_service.dart';
import '../services/gemini_service.dart';
import '../services/storage_service.dart';

class DiagnosisProvider extends ChangeNotifier {
  final Esp32Service _esp32Service;
  final GeminiService _geminiService;
  final StorageService _storageService;

  bool isLoading = false;
  String? errorMessage;
  Map<String, dynamic>? activeDiagnosis;
  List<DiagnosisHistoryItem> history = [];

  DiagnosisProvider({
    Esp32Service? esp32Service,
    GeminiService? geminiService,
    StorageService? storageService,
  })  : _esp32Service = esp32Service ?? Esp32Service(),
        _geminiService = geminiService ?? GeminiService(),
        _storageService = storageService ?? StorageService() {
    loadHistory();
  }

  Future<void> loadHistory() async {
    history = await _storageService.getAllDiagnoses();
    notifyListeners();
  }

  /// Triggers diagnosis fetch from the physical ESP32-CAM over local Wi-Fi.
  Future<void> fetchFromEsp32Cam(String visionHost) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      final diag = await _esp32Service.getLatestDiagnosis(visionHost);
      final nowFormatted = DateFormat('yyyy-MM-dd HH:mm').format(DateTime.now());

      final diagnosisMap = {
        'class_name': diag.className,
        'confidence': diag.confidence,
        'is_healthy': diag.isHealthy,
        'source': 'ESP32-CAM (On-Device TFLite)',
        'inference_time_ms': diag.inferenceTimeMs,
        'timestamp': nowFormatted,
      };

      activeDiagnosis = diagnosisMap;

      // Persist to local SQLite / Web IndexedDB
      await _storageService.insertDiagnosis(DiagnosisHistoryItem(
        className: diag.className,
        confidence: diag.confidence,
        isHealthy: diag.isHealthy,
        source: 'ESP32-CAM',
        treatmentSummary: diag.isHealthy ? 'Healthy foliage' : 'Foliar infection detected',
        createdAt: nowFormatted,
      ));

      await loadHistory();
    } catch (e) {
      errorMessage = 'ESP32-CAM diagnosis failed: ${e.toString()}';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  /// Analyzes image bytes from gallery/camera via Gemini Vision.
  Future<void> diagnoseWithGemini(Uint8List imageBytes) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      final result = await _geminiService.diagnoseLeafImage(imageBytes);
      final nowFormatted = DateFormat('yyyy-MM-dd HH:mm').format(DateTime.now());

      result['source'] = 'Cloud AI (Gemini Vision)';
      result['timestamp'] = nowFormatted;
      activeDiagnosis = result;

      final className = result['class_name'] as String? ?? 'Tomato Disease';
      final confidence = (result['confidence'] as num?)?.toDouble() ?? 0.9;
      final isHealthy = result['is_healthy'] == true;
      final treatment = result['chemical_control'] as String? ?? '';

      await _storageService.insertDiagnosis(DiagnosisHistoryItem(
        className: className,
        confidence: confidence,
        isHealthy: isHealthy,
        source: 'Cloud Gemini',
        treatmentSummary: treatment,
        createdAt: nowFormatted,
      ));

      await loadHistory();
    } catch (e) {
      errorMessage = 'Gemini diagnosis failed: ${e.toString()}';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<void> deleteHistoryItem(int id) async {
    await _storageService.deleteDiagnosis(id);
    await loadHistory();
  }

  Future<void> clearAllHistory() async {
    await _storageService.clearAll();
    await loadHistory();
  }
}
