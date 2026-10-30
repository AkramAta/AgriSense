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

  Future<void> pollTelemetry() async {
    try {
      final reading = await _esp32Service.getSensors(irrigationHost);
      final status = await _esp32Service.getStatus(irrigationHost);
      latestReading = reading;
      latestStatus = status;
      isConnectedIrrigation = true;
      lastError = null;
    } catch (e) {
      isConnectedIrrigation = false;
      lastError = e.toString();
    }
    notifyListeners();
  }

  Future<bool> toggleAutoMode(bool enable) async {
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

