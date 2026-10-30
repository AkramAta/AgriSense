import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

/// Base exception for ESP32 hardware node communications.
class Esp32Exception implements Exception {
  final String message;
  final int? statusCode;
  final String? endpoint;

  Esp32Exception(this.message, {this.statusCode, this.endpoint});

  @override
  String toString() => 'Esp32Exception: $message (endpoint: $endpoint, status: $statusCode)';
}

/// Raised when ESP32 does not respond within the network timeout window.
class Esp32ConnectionTimeoutException extends Esp32Exception {
  Esp32ConnectionTimeoutException(String endpoint)
      : super('Connection to ESP32 node timed out', endpoint: endpoint);
}

/// Raised when irrigation safety cutoff is actively tripped.
class Esp32SafetyTrippedException extends Esp32Exception {
  final int tripReason;

  Esp32SafetyTrippedException(this.tripReason, String endpoint)
      : super('Irrigation safety trip active (reason: $tripReason)', endpoint: endpoint);
}

/// Raised when JSON response from microcontroller is malformed or invalid.
class Esp32InvalidResponseException extends Esp32Exception {
  final String rawBody;

  Esp32InvalidResponseException(this.rawBody, String endpoint, {String? details})
      : super('Malformed JSON payload received from ESP32: ${details ?? ""}', endpoint: endpoint);
}

/// Environmental sensor telemetry packet.
class SensorReading {
  final double moisturePercent;
  final double temperatureC;
  final double humidityPercent;
  final double rawAdc;
  final double filteredAdc;
  final int timestampMs;

  const SensorReading({
    required this.moisturePercent,
    required this.temperatureC,
    required this.humidityPercent,
    required this.rawAdc,
    required this.filteredAdc,
    required this.timestampMs,
  });

  factory SensorReading.fromJson(Map<String, dynamic> json) {
    return SensorReading(
      moisturePercent: (json['moisture_percent'] as num?)?.toDouble() ?? 0.0,
      temperatureC: (json['temperature_c'] as num?)?.toDouble() ?? 0.0,
      humidityPercent: (json['humidity_percent'] as num?)?.toDouble() ?? 0.0,
      rawAdc: (json['raw_adc'] as num?)?.toDouble() ?? 0.0,
      filteredAdc: (json['filtered_adc'] as num?)?.toDouble() ?? 0.0,
      timestampMs: (json['timestamp_ms'] as num?)?.toInt() ?? 0,
    );
  }
}

/// Irrigation state machine status and safety audit record.
class IrrigationStatus {
  final String mode; // "AUTO" or "MANUAL"
  final String pumpStatus; // "ON" or "OFF"
  final bool pumpStartedByAuto;
  final bool safetyTripped;
  final int tripReason;
  final int uptimeSeconds;
  final double moisturePercent;
  final double temperatureC;
  final double humidityPercent;

  const IrrigationStatus({
    required this.mode,
    required this.pumpStatus,
    required this.pumpStartedByAuto,
    required this.safetyTripped,
    required this.tripReason,
    required this.uptimeSeconds,
    required this.moisturePercent,
    required this.temperatureC,
    required this.humidityPercent,
  });

  bool get isPumpOn => pumpStatus == "ON";
  bool get isAutoMode => mode == "AUTO";

  factory IrrigationStatus.fromJson(Map<String, dynamic> json) {
    return IrrigationStatus(
      mode: json['mode'] as String? ?? 'AUTO',
      pumpStatus: json['pump_status'] as String? ?? 'OFF',
      pumpStartedByAuto: json['pump_started_by_auto'] == true,
      safetyTripped: json['safety_tripped'] == true,
      tripReason: (json['trip_reason'] as num?)?.toInt() ?? 0,
      uptimeSeconds: (json['uptime_seconds'] as num?)?.toInt() ?? 0,
      moisturePercent: (json['moisture_percent'] as num?)?.toDouble() ?? 0.0,
      temperatureC: (json['temperature_c'] as num?)?.toDouble() ?? 0.0,
      humidityPercent: (json['humidity_percent'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

/// Edge vision inference result from ESP32-CAM.
class VisionDiagnosis {
  final int classIndex;
  final String className;
  final double confidence;
  final bool isHealthy;
  final int inferenceTimeMs;
  final int timestampMs;

  const VisionDiagnosis({
    required this.classIndex,
    required this.className,
    required this.confidence,
    required this.isHealthy,
    required this.inferenceTimeMs,
    required this.timestampMs,
  });

  factory VisionDiagnosis.fromJson(Map<String, dynamic> json) {
    return VisionDiagnosis(
      classIndex: (json['class_index'] as num?)?.toInt() ?? 7,
      className: json['class_name'] as String? ?? 'Tomato___healthy',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      isHealthy: json['is_healthy'] == true,
      inferenceTimeMs: (json['inference_time_ms'] as num?)?.toInt() ?? 0,
      timestampMs: (json['timestamp_ms'] as num?)?.toInt() ?? 0,
    );
  }
}

/// Robust HTTP client service for interacting with ESP32 microcontrollers.
class Esp32Service {
  final http.Client _client;
  final Duration timeout;

  Esp32Service({http.Client? client, this.timeout = const Duration(seconds: 4)})
      : _client = client ?? http.Client();

  Uri _buildUri(String host, String path, [Map<String, String>? query]) {
    String cleanHost = host.trim().replaceFirst(RegExp(r'^https?://'), '');
    int port = 80;
    if (cleanHost.contains(':')) {
      final parts = cleanHost.split(':');
      cleanHost = parts[0];
      port = int.tryParse(parts[1]) ?? 80;
    }
    return Uri(scheme: 'http', host: cleanHost, port: port, path: path, queryParameters: query);
  }

  Future<Map<String, dynamic>> _get(String host, String path) async {
    final uri = _buildUri(host, path);
    try {
      final res = await _client.get(uri).timeout(timeout);
      if (res.statusCode != 200) {
        throw Esp32Exception('HTTP GET request failed', statusCode: res.statusCode, endpoint: uri.toString());
      }
      return json.decode(res.body) as Map<String, dynamic>;
    } on TimeoutException {
      throw Esp32ConnectionTimeoutException(uri.toString());
    } on FormatException catch (e) {
      throw Esp32InvalidResponseException('', uri.toString(), details: e.message);
    } on SocketException catch (e) {
      throw Esp32Exception('Network error reaching ESP32: ${e.message}', endpoint: uri.toString());
    }
  }

  Future<Map<String, dynamic>> _post(String host, String path, {Map<String, dynamic>? body, Map<String, String>? query}) async {
    final uri = _buildUri(host, path, query);
    try {
      final res = await _client.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: body != null ? json.encode(body) : null,
      ).timeout(timeout);

      if (res.statusCode == 429) {
        throw Esp32SafetyTrippedException(1, uri.toString());
      }
      if (res.statusCode != 200) {
        throw Esp32Exception('HTTP POST request failed', statusCode: res.statusCode, endpoint: uri.toString());
      }
      return json.decode(res.body) as Map<String, dynamic>;
    } on TimeoutException {
      throw Esp32ConnectionTimeoutException(uri.toString());
    } on FormatException catch (e) {
      throw Esp32InvalidResponseException('', uri.toString(), details: e.message);
    }
  }

  /// Polls current environmental sensor values.
  Future<SensorReading> getSensors(String host) async {
    final data = await _get(host, '/sensors');
    return SensorReading.fromJson(data);
  }

  /// Polls full irrigation node status including relay and safety trips.
  Future<IrrigationStatus> getStatus(String host) async {
    final data = await _get(host, '/status');
    return IrrigationStatus.fromJson(data);
  }

  /// Toggles automatic threshold-based irrigation control.
  Future<bool> setAutoMode(String host, bool enabled) async {
    final data = await _post(host, '/pump/auto', body: {'enabled': enabled});
    return data['status'] == 'success';
  }

  /// Manually starts or stops the irrigation pump relay.
  Future<bool> setManualPump(String host, bool turnOn) async {
    final data = await _post(host, '/pump/manual', body: {'action': turnOn ? 'start' : 'stop'});
    return data['status'] == 'success';
  }

  /// Resets an active safety trip cutoff after inspecting field conditions.
  Future<bool> resetSafetyTrip(String host) async {
    final data = await _post(host, '/status/reset');
    return data['status'] == 'success';
  }

  /// Triggers on-device TFLite Micro inference on ESP32-CAM and returns prediction.
  Future<VisionDiagnosis> getLatestDiagnosis(String host) async {
    final data = await _get(host, '/latest');
    return VisionDiagnosis.fromJson(data);
  }

  /// Tests device reachability and returns round-trip latency in milliseconds.
  Future<int?> pingDevice(String host) async {
    final stopwatch = Stopwatch()..start();
    try {
      await _get(host, '/status');
      stopwatch.stop();
      return stopwatch.elapsedMilliseconds;
    } catch (_) {
      return null;
    }
  }
}

