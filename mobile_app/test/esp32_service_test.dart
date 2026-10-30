import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:agrisense_mobile/services/esp32_service.dart';

class MockHttpClient extends http.BaseClient {
  final Future<http.Response> Function(http.BaseRequest request) handler;

  MockHttpClient(this.handler);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final response = await handler(request);
    return http.StreamedResponse(
      Stream.value(response.bodyBytes),
      response.statusCode,
      headers: response.headers,
    );
  }
}

void main() {
  group('Esp32Service Tests', () {
    test('getSensors parses valid JSON payload correctly', () async {
      final mockClient = MockHttpClient((req) async {
        expect(req.url.path, '/sensors');
        return http.Response(
          json.encode({
            'moisture_percent': 42.5,
            'temperature_c': 26.1,
            'humidity_percent': 58.4,
            'raw_adc': 2400.0,
            'filtered_adc': 2410.0,
            'timestamp_ms': 123456,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = Esp32Service(client: mockClient);
      final reading = await service.getSensors('192.168.4.1');

      expect(reading.moisturePercent, 42.5);
      expect(reading.temperatureC, 26.1);
      expect(reading.humidityPercent, 58.4);
      expect(reading.rawAdc, 2400.0);
    });

    test('getStatus parses full irrigation status and safety fields', () async {
      final mockClient = MockHttpClient((req) async {
        expect(req.url.path, '/status');
        return http.Response(
          json.encode({
            'mode': 'AUTO',
            'pump_status': 'ON',
            'pump_started_by_auto': true,
            'safety_tripped': false,
            'trip_reason': 0,
            'uptime_seconds': 300,
            'moisture_percent': 31.0,
            'temperature_c': 24.0,
            'humidity_percent': 60.0,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = Esp32Service(client: mockClient);
      final status = await service.getStatus('192.168.4.1');

      expect(status.mode, 'AUTO');
      expect(status.isPumpOn, true);
      expect(status.pumpStartedByAuto, true);
      expect(status.safetyTripped, false);
    });

    test('getLatestDiagnosis parses vision node inference response', () async {
      final mockClient = MockHttpClient((req) async {
        expect(req.url.path, '/latest');
        return http.Response(
          json.encode({
            'class_index': 1,
            'class_name': 'Tomato___Early_blight',
            'confidence': 0.942,
            'is_healthy': false,
            'inference_time_ms': 68,
            'timestamp_ms': 55555,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = Esp32Service(client: mockClient);
      final diag = await service.getLatestDiagnosis('192.168.4.2');

      expect(diag.classIndex, 1);
      expect(diag.className, 'Tomato___Early_blight');
      expect(diag.confidence, 0.942);
      expect(diag.isHealthy, false);
      expect(diag.inferenceTimeMs, 68);
    });

    test('HTTP 429 wraps into Esp32SafetyTrippedException', () async {
      final mockClient = MockHttpClient((req) async {
        return http.Response('{"status":"rejected_cooldown"}', 429);
      });

      final service = Esp32Service(client: mockClient);
      expect(
        () async => await service.setManualPump('192.168.4.1', true),
        throwsA(isA<Esp32SafetyTrippedException>()),
      );
    });

    test('Malformed JSON response wraps into Esp32InvalidResponseException', () async {
      final mockClient = MockHttpClient((req) async {
        return http.Response('<html>502 Bad Gateway</html>', 200);
      });

      final service = Esp32Service(client: mockClient);
      expect(
        () async => await service.getSensors('192.168.4.1'),
        throwsA(isA<Esp32InvalidResponseException>()),
      );
    });
  });
}
