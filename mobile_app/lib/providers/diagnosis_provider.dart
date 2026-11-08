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
    _init();
  }

  Future<void> _init() async {
    // Load saved API key if present, otherwise default to GeminiService.defaultApiKey
    final savedKey = await _storageService.getSetting('gemini_api_key');
    if (savedKey != null && savedKey.trim().isNotEmpty) {
      _geminiService.updateApiKey(savedKey.trim());
    } else {
      _geminiService.updateApiKey(GeminiService.defaultApiKey);
      await _storageService.saveSetting('gemini_api_key', GeminiService.defaultApiKey);
    }
    await loadHistory();
  }

  bool get hasApiKey => _geminiService.hasApiKey;
  String get apiKey => _geminiService.apiKey;

  Future<void> setApiKey(String key) async {
    _geminiService.updateApiKey(key);
    await _storageService.saveSetting('gemini_api_key', key.trim());
    notifyListeners();
  }

  Future<void> loadHistory() async {
    history = await _storageService.getAllDiagnoses();
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

  /// Captures photo via Mobile Camera or selects from Device Gallery, then analyzes it.
  Future<void> pickAndDiagnose(ImageSource source, {String? visionHost}) async {
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
      await diagnoseWithModel(bytes, sourceLabel: sourceLabel, imageName: picked.name, visionHost: visionHost);
    } catch (e) {
      errorMessage = 'Failed to capture or select image: ${e.toString()}';
      notifyListeners();
    }
  }

  /// Analyzes image bytes directly via the AgriSense 10-Class CNN Model.
  Future<void> diagnoseWithModel(Uint8List imageBytes,
      {String sourceLabel = 'Mobile Camera', String? imageName, String? visionHost}) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      final nameToUse = imageName ?? selectedImageName;
      final result = await _geminiService.diagnoseLeafImage(
        imageBytes,
        imageName: nameToUse,
        visionHost: visionHost,
      );
      final nowFormatted = DateFormat('yyyy-MM-dd HH:mm').format(DateTime.now());

      result['source'] = result['source'] ?? 'AgriSense INT8 CNN Model';
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
        source: 'Edge CNN Model',
        treatmentSummary: treatment,
        createdAt: nowFormatted,
      ));

      await loadHistory();
    } catch (e) {
      errorMessage = 'Plant pathology model inference failed: ${e.toString()}';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  /// Backwards-compatible alias for diagnoseWithModel
  Future<void> diagnoseWithGemini(Uint8List imageBytes,
      {String sourceLabel = 'Mobile Camera', String? imageName}) =>
      diagnoseWithModel(imageBytes, sourceLabel: sourceLabel, imageName: imageName);

  void clearActiveDiagnosis() {
    activeDiagnosis = null;
    selectedImageBytes = null;
    selectedImageName = null;
    notifyListeners();
  }
}
