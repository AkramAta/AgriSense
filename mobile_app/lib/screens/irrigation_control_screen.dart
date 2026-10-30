import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/farm_provider.dart';

class IrrigationControlScreen extends StatelessWidget {
  const IrrigationControlScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final farm = context.watch<FarmProvider>();
    final status = farm.latestStatus;
    final isPumpOn = status?.pumpStatus == 'ON';
    final isAuto = status?.mode == 'AUTO';
    final safetyTripped = status?.safetyTripped == true;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Irrigation Control'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: () => farm.pollTelemetry(),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          // Safety Trip Alert Banner (if tripped)
          if (safetyTripped)
            Card(
              color: Colors.red.shade100,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: Colors.red.shade400, width: 1.5),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.warning_amber_rounded, color: Colors.red.shade900, size: 28),
                        const SizedBox(width: 8),
                        Text(
                          'Safety Auto-Cutoff Tripped',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.red.shade900),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Pump exceeded maximum runtime duration (15s Auto / 30s Manual) to prevent flooding. '
                      'Check physical field lines before resetting.',
                      style: TextStyle(fontSize: 13, color: Colors.red.shade900),
                    ),
                    const SizedBox(height: 12),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red.shade800,
                        foregroundColor: Colors.white,
                      ),
                      icon: const Icon(Icons.restore),
                      label: const Text('Reset Safety Trip'),
                      onPressed: () async {
                        final ok = await farm.resetSafetyTrip();
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(ok ? 'Safety trip cleared' : 'Failed to clear trip')),
                          );
                        }
                      },
                    ),
                  ],
                ),
              ),
            ),
          if (safetyTripped) const SizedBox(height: 16),

          // Control Mode Toggle Card
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Control Mode', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          style: OutlinedButton.styleFrom(
                            backgroundColor: isAuto ? Colors.indigo.shade50 : null,
                            side: BorderSide(color: isAuto ? Colors.indigo : Colors.grey.shade400, width: isAuto ? 2 : 1),
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                          onPressed: () => farm.toggleAutoMode(true),
                          child: Column(
                            children: [
                              Icon(Icons.auto_awesome, color: isAuto ? Colors.indigo : Colors.grey),
                              const SizedBox(height: 4),
                              Text('AUTOMATIC', style: TextStyle(fontWeight: FontWeight.bold, color: isAuto ? Colors.indigo : Colors.grey)),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton(
                          style: OutlinedButton.styleFrom(
                            backgroundColor: !isAuto ? Colors.indigo.shade50 : null,
                            side: BorderSide(color: !isAuto ? Colors.indigo : Colors.grey.shade400, width: !isAuto ? 2 : 1),
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                          onPressed: () => farm.toggleAutoMode(false),
                          child: Column(
                            children: [
                              Icon(Icons.touch_app, color: !isAuto ? Colors.indigo : Colors.grey),
                              const SizedBox(height: 4),
                              Text('MANUAL OVERRIDE', style: TextStyle(fontWeight: FontWeight.bold, color: !isAuto ? Colors.indigo : Colors.grey)),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    isAuto
                        ? '• Auto Mode: Starts pump below 35% moisture; stops at 65% moisture.'
                        : '• Manual Mode: Pump controlled directly by operator with 30s safety timeout.',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Big Tactile Pump Relay Switch Card
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                children: [
                  Text(
                    isPumpOn ? 'PUMP IS RUNNING' : 'PUMP IS STOPPED',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: isPumpOn ? Colors.blue.shade700 : Colors.grey.shade800,
                    ),
                  ),
                  const SizedBox(height: 20),
                  GestureDetector(
                    onTap: () async {
                      if (safetyTripped) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Cannot start: safety trip is active!')),
                        );
                        return;
                      }
                      await farm.commandManualPump(!isPumpOn);
                    },
                    child: Container(
                      width: 140,
                      height: 140,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isPumpOn ? Colors.blue.shade600 : Colors.grey.shade200,
                        boxShadow: [
                          BoxShadow(
                            color: isPumpOn ? Colors.blue.withAlpha(102) : Colors.black12,
                            blurRadius: 16,
                            spreadRadius: 4,
                          ),
                        ],
                      ),
                      child: Icon(
                        Icons.power_settings_new,
                        size: 64,
                        color: isPumpOn ? Colors.white : Colors.grey.shade600,
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    isPumpOn ? 'Tap to Force Stop' : 'Tap to Start Pump',
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 16),
                  const Divider(),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('Origin Tracking:'),
                      Chip(
                        label: Text(
                          status?.pumpStartedByAuto == true ? 'Auto Moisture FSM' : 'Manual / Idle',
                          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                        ),
                        backgroundColor: status?.pumpStartedByAuto == true ? Colors.blue.shade50 : Colors.grey.shade200,
                      ),
                    ],
                  ),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('Max Allowed Duration:'),
                      Text(
                        isAuto ? '15 seconds (Auto)' : '30 seconds (Manual)',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
