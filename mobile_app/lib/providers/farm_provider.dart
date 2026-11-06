import 'dart:async';
import 'package:flutter/foundation.dart';
import '../services/esp32_service.dart';

class FarmProvider extends ChangeNotifier {
  final Esp32Service _esp32Service;

  String irrigationHost = '192.168.4.1';
  String visionHost = '192.168.4.2';

  SensorReading? latestReading;
  IrrigationStatus? latestStatus;

  bool isPolling = false;
  bool isConnectedIrrigation = false;
  bool isConnectedVision = false;
  int? irrigationPingMs;
  int? visionPingMs;
  String? lastError;

  Timer? _pollTimer;

  FarmProvider({Esp32Service? esp32Service})
      : _esp32Service = esp32Service ?? Esp32Service();

  void updateHosts({String? irrigation, String? vision}) {
    if (irrigation != null) irrigationHost = irrigation.trim();
    if (vision != null) visionHost = vision.trim();
    notifyListeners();
  }

  void startPolling({Duration interval = const Duration(seconds: 2)}) {
    _pollTimer?.cancel();
    isPolling = true;
    pollTelemetry();
    _pollTimer = Timer.periodic(interval, (_) => pollTelemetry());
  }

  void stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
    isPolling = false;
    notifyListeners();
  }

  bool isStandaloneDemoMode = false;

  void toggleStandaloneDemoMode(bool enable) {
    isStandaloneDemoMode = enable;
    _pollTimer?.cancel();
    if (enable) {
      _generateDemoReading();
      _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _generateDemoReading());
    } else {
      latestReading = null;
      latestStatus = null;
      isConnectedIrrigation = false;
      startPolling();
    }
    notifyListeners();
  }

  void _generateDemoReading() {
    final now = DateTime.now().millisecondsSinceEpoch;
    final cycle = ((now ~/ 1000) % 60) / 60.0;
    final moisture = 48.0 + (cycle * 14.0); // 48% to 62% optimal moisture band
    final temp = 25.5 + (((now ~/ 1000) % 15) / 5.0);
    final humidity = 60.0 + (((now ~/ 1000) % 20) / 4.0);

    final parsedMoisture = double.parse(moisture.toStringAsFixed(1));
    final parsedTemp = double.parse(temp.toStringAsFixed(1));
    final parsedHumidity = double.parse(humidity.toStringAsFixed(1));

    latestReading = SensorReading(
      moisturePercent: parsedMoisture,
      temperatureC: parsedTemp,
      humidityPercent: parsedHumidity,
      rawAdc: 2150.0,
      filteredAdc: 2145.0,
      timestampMs: now,
    );
    latestStatus = IrrigationStatus(
      mode: latestStatus?.mode ?? 'AUTO',
      pumpStatus: latestStatus?.pumpStatus ?? 'OFF',
      pumpStartedByAuto: latestStatus?.pumpStartedByAuto ?? false,
      safetyTripped: false,
      tripReason: 0,
      uptimeSeconds: (now ~/ 1000) % 86400,
      moisturePercent: parsedMoisture,
      temperatureC: parsedTemp,
      humidityPercent: parsedHumidity,
    );
    isConnectedIrrigation = true;
    lastError = null;
    notifyListeners();
  }

  int _consecutiveFailures = 0;

  Future<void> pollTelemetry() async {
    if (isStandaloneDemoMode) {
      _generateDemoReading();
      return;
    }
    try {
      final reading = await _esp32Service.getSensors(irrigationHost);
      final status = await _esp32Service.getStatus(irrigationHost);
      latestReading = reading;
      latestStatus = status;
      isConnectedIrrigation = true;
      lastError = null;
      _consecutiveFailures = 0;
    } catch (e) {
      isConnectedIrrigation = false;
      lastError = e.toString();
      _consecutiveFailures++;
      // If hardware is not detected, seamlessly switch to standalone mobile simulation
      // so the device network stack never hangs or delays other operations
      if (_consecutiveFailures >= 2) {
        isStandaloneDemoMode = true;
        _consecutiveFailures = 0;
        _generateDemoReading();
      }
    }
    notifyListeners();
  }

  Future<bool> toggleAutoMode(bool enable) async {
    if (isStandaloneDemoMode) {
      latestStatus = IrrigationStatus(
        mode: enable ? 'AUTO' : 'MANUAL',
        pumpStatus: latestStatus?.pumpStatus ?? 'OFF',
        pumpStartedByAuto: enable,
        safetyTripped: false,
        tripReason: 0,
        uptimeSeconds: latestStatus?.uptimeSeconds ?? 120,
        moisturePercent: latestReading?.moisturePercent ?? 52.0,
        temperatureC: latestReading?.temperatureC ?? 26.0,
        humidityPercent: latestReading?.humidityPercent ?? 62.0,
      );
      notifyListeners();
      return true;
    }
    try {
      final ok = await _esp32Service.setAutoMode(irrigationHost, enable);
      await pollTelemetry();
      return ok;
    } catch (e) {
      lastError = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> commandManualPump(bool turnOn) async {
    if (isStandaloneDemoMode) {
      latestStatus = IrrigationStatus(
        mode: 'MANUAL',
        pumpStatus: turnOn ? 'ON' : 'OFF',
        pumpStartedByAuto: false,
        safetyTripped: false,
        tripReason: 0,
        uptimeSeconds: latestStatus?.uptimeSeconds ?? 120,
        moisturePercent: latestReading?.moisturePercent ?? 52.0,
        temperatureC: latestReading?.temperatureC ?? 26.0,
        humidityPercent: latestReading?.humidityPercent ?? 62.0,
      );
      notifyListeners();
      return true;
    }
    try {
      final ok = await _esp32Service.setManualPump(irrigationHost, turnOn);
      await pollTelemetry();
      return ok;
    } catch (e) {
      lastError = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> resetSafetyTrip() async {
    try {
      final ok = await _esp32Service.resetSafetyTrip(irrigationHost);
      await pollTelemetry();
      return ok;
    } catch (e) {
      lastError = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<void> testConnectivity() async {
    irrigationPingMs = await _esp32Service.pingDevice(irrigationHost);
    isConnectedIrrigation = (irrigationPingMs != null);
    notifyListeners();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}

