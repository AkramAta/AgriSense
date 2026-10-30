import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

/// Protocol-accurate dual-port ESP32 & ESP32-CAM Simulator.
/// Simulates physical microcontroller firmware for rapid desktop/web testing.
void main(List<String> args) async {
  print('====================================================');
  print('Starting AgriSense Dual-Node Hardware Simulator...');
  print('====================================================');

  final irrigationSim = IrrigationNodeSimulator(port: 8080);
  await irrigationSim.start();

  final visionSim = VisionNodeSimulator(port: 8081);
  await visionSim.start();

  print('Irrigation Node listening at: http://127.0.0.1:8080');
  print('Vision Node listening at:     http://127.0.0.1:8081');
  print('Press Ctrl+C to terminate simulator.');
}

void applyCors(HttpResponse res) {
  res.headers.set('Access-Control-Allow-Origin', '*');
  res.headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.headers.set('Access-Control-Allow-Headers', 'Content-Type, Origin, Accept');
}

class IrrigationNodeSimulator {
  final int port;
  HttpServer? _server;

  // State
  String mode = 'AUTO'; // AUTO or MANUAL
  String pumpStatus = 'OFF'; // ON or OFF
  bool pumpStartedByAuto = false;
  int pumpStartTimeMs = 0;
  int lastPumpStopTimeMs = 0;
  bool safetyTripped = false;
  int tripReason = 0;

  double moisturePercent = 28.0; // Starts dry
  double temperatureC = 25.4;
  double humidityPercent = 54.2;
  double rawAdc = 2650.0;
  double filteredAdc = 2650.0;

  final int maxAutoRunMs = 15000;
  final int maxManualRunMs = 30000;
  final int cooldownMs = 10000;

  Timer? _ticker;

  IrrigationNodeSimulator({required this.port});

  Future<void> start() async {
    _server = await HttpServer.bind(InternetAddress.anyIPv4, port);
    _server!.listen(_handleRequest);

    _ticker = Timer.periodic(const Duration(milliseconds: 500), (_) => _tick());
  }

  void stop() {
    _ticker?.cancel();
    _server?.close();
  }

  void _tick() {
    final now = DateTime.now().millisecondsSinceEpoch;

    // Simulate soil moisture dynamics: if pump is ON, moisture increases; if OFF, dries slowly
    if (pumpStatus == 'ON') {
      moisturePercent = min(85.0, moisturePercent + 2.5);
      rawAdc = max(1400.0, rawAdc - 45.0);
    } else {
      moisturePercent = max(15.0, moisturePercent - 0.2);
      rawAdc = min(3200.0, rawAdc + 4.0);
    }
    filteredAdc = (0.25 * rawAdc) + (0.75 * filteredAdc);

    // State machine check
    if (pumpStatus == 'ON') {
      final elapsed = now - pumpStartTimeMs;
      if (pumpStartedByAuto && elapsed >= maxAutoRunMs) {
        pumpStatus = 'OFF';
        pumpStartedByAuto = false;
        lastPumpStopTimeMs = now;
        safetyTripped = true;
        tripReason = 1; // AUTO_TIMEOUT
        print('[SIMULATOR] Pump shutoff triggered: AUTO TIMEOUT SAFETY CUTOFF');
      } else if (!pumpStartedByAuto && elapsed >= maxManualRunMs) {
        pumpStatus = 'OFF';
        pumpStartedByAuto = false;
        lastPumpStopTimeMs = now;
        safetyTripped = true;
        tripReason = 2; // MANUAL_TIMEOUT
        print('[SIMULATOR] Pump shutoff triggered: MANUAL TIMEOUT SAFETY CUTOFF');
      }
    }

    if (mode == 'AUTO') {
      if (pumpStatus == 'OFF') {
        if (moisturePercent < 35.0 && !safetyTripped) {
          if (lastPumpStopTimeMs == 0 || (now - lastPumpStopTimeMs) >= cooldownMs) {
            pumpStatus = 'ON';
            pumpStartedByAuto = true;
            pumpStartTimeMs = now;
            print('[SIMULATOR] Auto Pump Started: Moisture $moisturePercent% < 35%');
          }
        }
      } else if (pumpStatus == 'ON' && pumpStartedByAuto) {
        if (moisturePercent >= 65.0) {
          pumpStatus = 'OFF';
          pumpStartedByAuto = false;
          lastPumpStopTimeMs = now;
          print('[SIMULATOR] Auto Pump Stopped: Moisture $moisturePercent% >= 65%');
        }
      }
    }
  }

  void _handleRequest(HttpRequest req) async {
    applyCors(req.response);
    if (req.method == 'OPTIONS') {
      req.response.statusCode = 204;
      await req.response.close();
      return;
    }

    final path = req.uri.path;
    req.response.headers.contentType = ContentType.json;

    if (path == '/sensors' && req.method == 'GET') {
      final payload = {
        'moisture_percent': moisturePercent,
        'temperature_c': temperatureC,
        'humidity_percent': humidityPercent,
        'raw_adc': rawAdc,
        'filtered_adc': filteredAdc,
        'timestamp_ms': DateTime.now().millisecondsSinceEpoch,
      };
      req.response.write(json.encode(payload));
    } else if (path == '/status' && req.method == 'GET') {
      final payload = {
        'mode': mode,
        'pump_status': pumpStatus,
        'pump_started_by_auto': pumpStartedByAuto,
        'safety_tripped': safetyTripped,
        'trip_reason': tripReason,
        'uptime_seconds': 120,
        'moisture_percent': moisturePercent,
        'temperature_c': temperatureC,
        'humidity_percent': humidityPercent,
      };
      req.response.write(json.encode(payload));
    } else if (path == '/pump/auto' && req.method == 'POST') {
      final content = await utf8.decoder.bind(req).join();
      final body = content.isNotEmpty ? json.decode(content) : {};
      final enable = body['enabled'] != false;
      mode = enable ? 'AUTO' : 'MANUAL';
      req.response.write(json.encode({'status': 'success', 'mode': mode}));
    } else if (path == '/pump/manual' && req.method == 'POST') {
      final content = await utf8.decoder.bind(req).join();
      final body = content.isNotEmpty ? json.decode(content) : {};
      final turnOn = body['action'] == 'start' || body['state'] == 'on';
      final now = DateTime.now().millisecondsSinceEpoch;

      if (turnOn) {
        mode = 'MANUAL';
        pumpStatus = 'ON';
        pumpStartedByAuto = false;
        pumpStartTimeMs = now;
        safetyTripped = false;
        tripReason = 0;
      } else {
        pumpStatus = 'OFF';
        pumpStartedByAuto = false;
        lastPumpStopTimeMs = now;
      }
      req.response.write(json.encode({
        'status': 'success',
        'pump_status': pumpStatus,
        'safety_tripped': safetyTripped,
      }));
    } else if (path == '/status/reset' && req.method == 'POST') {
      safetyTripped = false;
      tripReason = 0;
      req.response.write(json.encode({'status': 'success', 'safety_tripped': false}));
    } else {
      req.response.statusCode = 404;
      req.response.write(json.encode({'error': 'Not found'}));
    }
    await req.response.close();
  }
}

class VisionNodeSimulator {
  final int port;
  HttpServer? _server;
  int _scanCount = 0;

  final List<String> classes = [
    'Tomato___Bacterial_spot',
    'Tomato___Early_blight',
    'Tomato___Late_blight',
    'Tomato___Leaf_Mold',
    'Tomato___Septoria_leaf_spot',
    'Tomato___Spider_mites_Two_spotted_spider_mite',
    'Tomato___Target_Spot',
    'Tomato___healthy',
  ];

  VisionNodeSimulator({required this.port});

  Future<void> start() async {
    _server = await HttpServer.bind(InternetAddress.anyIPv4, port);
    _server!.listen(_handleRequest);
  }

  void _handleRequest(HttpRequest req) async {
    applyCors(req.response);
    if (req.method == 'OPTIONS') {
      req.response.statusCode = 204;
      await req.response.close();
      return;
    }

    final path = req.uri.path;
    req.response.headers.contentType = ContentType.json;

    if (path == '/latest' && req.method == 'GET') {
      _scanCount++;
      // Alternate between a disease and healthy
      final idx = (_scanCount % 2 == 1) ? 1 : 7; // Early blight or Healthy
      final payload = {
        'class_index': idx,
        'class_name': classes[idx],
        'confidence': 0.942,
        'is_healthy': idx == 7,
        'inference_time_ms': 74,
        'timestamp_ms': DateTime.now().millisecondsSinceEpoch,
      };
      req.response.write(json.encode(payload));
    } else if (path == '/status' && req.method == 'GET') {
      req.response.write(json.encode({
        'device': 'ESP32-CAM Simulator',
        'model_version': '4-block-int8',
        'psram_enabled': true,
        'uptime_seconds': 240,
      }));
    } else {
      req.response.statusCode = 404;
      req.response.write(json.encode({'error': 'Not found'}));
    }
    await req.response.close();
  }
}
