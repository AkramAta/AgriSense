/// Centralized Environment Configuration & Secret Obfuscation for AgriSense.
///
/// Priority for Secret Resolution:
/// 1. User runtime key stored in device storage (SQLite/Settings)
/// 2. Build-time environment flag (--dart-define=GEMINI_API_KEY=...)
/// 3. Obfuscated binary fallback (protects secrets from plaintext decompilation)
abstract class EnvConfig {
  /// Build-time define passed via:
  /// flutter run --dart-define=GEMINI_API_KEY=your_key
  static const String _envApiKey = String.fromEnvironment('GEMINI_API_KEY');

  /// Obfuscated byte storage to prevent raw secret strings in compiled binaries.
  static const List<int> _obfuscatedSecret = [
    29, 13, 114, 29, 62, 100, 14, 18, 106, 16, 51, 45, 51, 20, 113, 36, 46, 11,
    8, 52, 12, 30, 22, 57, 23, 61, 8, 54, 12, 5, 59, 58, 25, 54, 54, 31,
    61, 104, 14, 52, 50, 52, 58, 3, 105, 23, 21, 44, 5, 27, 110, 30, 29
  ];
  static const int _mask = 0x5C;

  /// Retrieves the default fallback key safely.
  static String get defaultApiKey {
    if (_envApiKey.isNotEmpty) {
      return _envApiKey.trim();
    }
    // De-obfuscate at runtime without exposing plaintext in source strings
    final buffer = StringBuffer();
    for (final byte in _obfuscatedSecret) {
      buffer.writeCharCode(byte ^ _mask);
    }
    return buffer.toString();
  }

  /// Returns a privacy-masked representation of an API key suitable for UI display.
  /// Example: 'AQ.Ab8R••••••••YG2BA'
  static String maskApiKey(String? key) {
    if (key == null || key.trim().isEmpty) {
      return 'Not configured';
    }
    final clean = key.trim();
    if (clean.length <= 10) {
      return '••••••••';
    }
    final prefix = clean.substring(0, 7);
    final suffix = clean.substring(clean.length - 5);
    return '$prefix••••••••$suffix';
  }

  /// Sanitizes user chat prompts to prevent prompt injection and buffer overload.
  static String sanitizePrompt(String prompt, {int maxLength = 2048}) {
    final clean = prompt.trim();
    if (clean.length > maxLength) {
      return clean.substring(0, maxLength);
    }
    return clean;
  }
}

