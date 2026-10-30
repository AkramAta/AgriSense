import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:agrisense_mobile/main.dart';

void main() {
  testWidgets('AgriSense App boots and displays Sensor Dashboard and Navigation tabs', (WidgetTester tester) async {
    await tester.pumpWidget(const AgriSenseApp());
    await tester.pumpAndSettle();

    // Verify Dashboard Title
    expect(find.text('Sensor Dashboard'), findsOneWidget);

    // Verify Telemetry Cards
    expect(find.text('Soil Moisture'), findsOneWidget);
    expect(find.text('Temperature'), findsOneWidget);
    expect(find.text('Humidity'), findsOneWidget);

    // Verify Bottom Navigation Bar Destinations
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.text('Telemetry'), findsOneWidget);
    expect(find.text('Irrigation'), findsOneWidget);
    expect(find.text('Scanner'), findsOneWidget);
    expect(find.text('History'), findsOneWidget);
    expect(find.text('AI Chat'), findsOneWidget);

    // Tap on Irrigation Tab
    await tester.tap(find.text('Irrigation'));
    await tester.pumpAndSettle();
    expect(find.text('Irrigation Control'), findsOneWidget);
    expect(find.text('AUTOMATIC'), findsOneWidget);
    expect(find.text('MANUAL OVERRIDE'), findsOneWidget);

    // Tap on Scanner Tab
    await tester.tap(find.text('Scanner'));
    await tester.pumpAndSettle();
    expect(find.text('Disease Scanner'), findsOneWidget);
    expect(find.text('Fetch ESP32-CAM'), findsOneWidget);
    expect(find.text('Cloud AI Scan'), findsOneWidget);

    // Tap on AI Chat Tab
    await tester.tap(find.text('AI Chat'));
    await tester.pumpAndSettle();
    expect(find.text('AI Agronomist Chat'), findsOneWidget);
  });
}

