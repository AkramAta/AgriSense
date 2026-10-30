import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/farm_provider.dart';

class SensorDashboardScreen extends StatelessWidget {
  const SensorDashboardScreen({super.key});

  Color _getMoistureColor(double moisture) {
    if (moisture < 35.0) return Colors.orange.shade700; // Dry
    if (moisture <= 65.0) return Colors.green.shade600; // Optimal
    return Colors.blue.shade700; // Saturated
  }

  String _getMoistureStatus(double moisture) {
    if (moisture < 35.0) return 'Dry (Needs Water)';
    if (moisture <= 65.0) return 'Optimal Moisture';
    return 'Saturated / Wet';
  }

  @override
  Widget build(BuildContext context) {
    final farm = context.watch<FarmProvider>();
    final reading = farm.latestReading;
    final status = farm.latestStatus;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sensor Dashboard'),
        actions: [
          IconButton(
            icon: Icon(farm.isPolling ? Icons.pause_circle_outline : Icons.play_circle_outline),
            tooltip: farm.isPolling ? 'Pause Polling' : 'Resume Polling',
            onPressed: () {
              if (farm.isPolling) {
                farm.stopPolling();
              } else {
                farm.startPolling();
              }
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh Now',
            onPressed: () => farm.pollTelemetry(),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => farm.pollTelemetry(),
        child: ListView(
          padding: const EdgeInsets.all(16.0),
          children: [
            // Connectivity Status Banner
            Card(
              elevation: 0,
              color: farm.isConnectedIrrigation ? Colors.green.shade50 : Colors.red.shade50,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(
                  color: farm.isConnectedIrrigation ? Colors.green.shade300 : Colors.red.shade300,
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                child: Row(
                  children: [
                    Icon(
                      farm.isConnectedIrrigation ? Icons.check_circle : Icons.error_outline,
                      color: farm.isConnectedIrrigation ? Colors.green.shade700 : Colors.red.shade700,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            farm.isConnectedIrrigation ? 'ESP32 Node Online' : 'ESP32 Node Offline',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: farm.isConnectedIrrigation ? Colors.green.shade900 : Colors.red.shade900,
                            ),
                          ),
                          Text(
                            'Host: ${farm.irrigationHost}',
                            style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                          ),
                        ],
                      ),
                    ),
                    if (status != null)
                      Chip(
                        label: Text(
                          status.pumpStatus == 'ON' ? 'PUMP ACTIVE' : 'PUMP IDLE',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: status.pumpStatus == 'ON' ? Colors.white : Colors.grey.shade800,
                          ),
                        ),
                        backgroundColor: status.pumpStatus == 'ON' ? Colors.blue.shade600 : Colors.grey.shade300,
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Soil Moisture Card
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.water_drop, color: Colors.blue),
                            SizedBox(width: 8),
                            Text('Soil Moisture', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                          ],
                        ),
                        Text(
                          reading != null ? '${reading.moisturePercent.toStringAsFixed(1)}%' : '--%',
                          style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                            color: reading != null ? _getMoistureColor(reading.moisturePercent) : Colors.grey,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: LinearProgressIndicator(
                        value: reading != null ? (reading.moisturePercent / 100.0).clamp(0.0, 1.0) : 0.0,
                        minHeight: 12,
                        backgroundColor: Colors.grey.shade200,
                        valueColor: AlwaysStoppedAnimation(
                          reading != null ? _getMoistureColor(reading.moisturePercent) : Colors.grey,
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      reading != null ? _getMoistureStatus(reading.moisturePercent) : 'Awaiting sensor reading...',
                      style: TextStyle(fontSize: 13, color: Colors.grey.shade700),
                    ),
                    const Divider(height: 24),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('Raw ADC: ${reading?.rawAdc.toStringAsFixed(0) ?? "--"}', style: const TextStyle(fontSize: 12, color: Colors.grey)),
                        Text('Filtered ADC: ${reading?.filteredAdc.toStringAsFixed(0) ?? "--"}', style: const TextStyle(fontSize: 12, color: Colors.grey)),
                      ],
                    )
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Climate Row: Temperature & Humidity Cards
            Row(
              children: [
                Expanded(
                  child: Card(
                    elevation: 2,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Row(
                            children: [
                              Icon(Icons.thermostat, color: Colors.deepOrange),
                              SizedBox(width: 6),
                              Text('Temperature', style: TextStyle(fontWeight: FontWeight.bold)),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Text(
                            reading != null ? '${reading.temperatureC.toStringAsFixed(1)}°C' : '--°C',
                            style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.deepOrange),
                          ),
                          const SizedBox(height: 4),
                          const Text('Ambient DHT11', style: TextStyle(fontSize: 11, color: Colors.grey)),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Card(
                    elevation: 2,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Row(
                            children: [
                              Icon(Icons.cloud, color: Colors.teal),
                              SizedBox(width: 6),
                              Text('Humidity', style: TextStyle(fontWeight: FontWeight.bold)),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Text(
                            reading != null ? '${reading.humidityPercent.toStringAsFixed(1)}%' : '--%',
                            style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.teal),
                          ),
                          const SizedBox(height: 4),
                          const Text('Relative Humidity', style: TextStyle(fontSize: 11, color: Colors.grey)),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Mode & Safety Summary Card
            Card(
              elevation: 1,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Irrigation Subsystem State', style: TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 12),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Operational Mode:'),
                        Text(
                          status?.mode ?? 'AUTO',
                          style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.indigo),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Origin Tracking:'),
                        Text(
                          status?.pumpStartedByAuto == true ? 'Automatic Threshold' : 'Manual / Idle',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: status?.pumpStartedByAuto == true ? Colors.blue : Colors.grey.shade700,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Safety Safeguard:'),
                        Text(
                          status?.safetyTripped == true ? 'TRIPPED (Cutoff)' : 'Normal',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: status?.safetyTripped == true ? Colors.red : Colors.green,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

