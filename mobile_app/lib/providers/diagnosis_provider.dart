import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';
import '../services/gemini_service.dart';
import '../services/storage_service.dart';

class DiagnosisProvider extends ChangeNotifier {
  final GeminiService _geminiService;
  final StorageService _storageService;
  final ImagePicker _imagePicker;

  bool isLoading = false;
  String? errorMessage;
  Uint8List? selectedImageBytes;
  String? selectedImageName;
  Map<String, dynamic>? activeDiagnosis;
  List<DiagnosisHistoryItem> history = [];

  DiagnosisProvider({
    GeminiService? geminiService,
    StorageService? storageService,
    ImagePicker? imagePicker,
  })  : _geminiService = geminiService ?? GeminiService(),
        _storageService = storageService ?? StorageService(),
        _imagePicker = imagePicker ?? ImagePicker() {
    loadHistory();
  }

  Future<void> loadHistory() async {
    history = await _storageService.getAllDiagnoses();
    notifyListeners();
  }

  /// Captures photo via Mobile Camera or selects from Device Gallery, then analyzes it.
  Future<void> pickAndDiagnose(ImageSource source) async {
    try {
      final picked = await _imagePicker.pickImage(
        source: source,
        maxWidth: 1024,
        maxHeight: 1024,
        imageQuality: 85,
      );
      if (picked == null) return; // User cancelled

      final bytes = await picked.readAsBytes();
      selectedImageBytes = bytes;
      selectedImageName = picked.name;
      notifyListeners();

      final sourceLabel = (source == ImageSource.camera) ? 'Mobile Camera' : 'Gallery Upload';
      await diagnoseWithGemini(bytes, sourceLabel: sourceLabel);
    } catch (e) {
      errorMessage = 'Failed to capture or select image: ${e.toString()}';
      notifyListeners();
    }
  }

  /// Analyzes image bytes directly via Gemini Vision / Plant Pathology AI.
  Future<void> diagnoseWithGemini(Uint8List imageBytes, {String sourceLabel = 'Mobile Camera'}) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      final result = await _geminiService.diagnoseLeafImage(imageBytes);
      final nowFormatted = DateFormat('yyyy-MM-dd HH:mm').format(DateTime.now());

      result['source'] = sourceLabel;
      result['timestamp'] = nowFormatted;
      activeDiagnosis = result;

      final className = result['class_name'] as String? ?? 'Tomato Disease';
      final confidence = (result['confidence'] as num?)?.toDouble() ?? 0.9;
      final isHealthy = result['is_healthy'] == true;
      final treatment = result['chemical_control'] as String? ?? '';

      // Persist to local database (SQLite on Mobile, IndexedDB on Web)
      await _storageService.insertDiagnosis(DiagnosisHistoryItem(
        className: className,
        confidence: confidence,
        isHealthy: isHealthy,
        source: sourceLabel,
        treatmentSummary: treatment,
        createdAt: nowFormatted,
      ));

      await loadHistory();
    } catch (e) {
      errorMessage = 'Plant pathology analysis failed: ${e.toString()}';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  void clearActiveDiagnosis() {
    activeDiagnosis = null;
    selectedImageBytes = null;
    selectedImageName = null;
    errorMessage = null;
    notifyListeners();
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
