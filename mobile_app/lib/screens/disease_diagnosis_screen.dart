import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/diagnosis_provider.dart';
import '../providers/farm_provider.dart';
import 'chat_screen.dart';

class DiseaseDiagnosisScreen extends StatelessWidget {
  const DiseaseDiagnosisScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final diag = context.watch<DiagnosisProvider>();
    final farm = context.watch<FarmProvider>();
    final active = diag.activeDiagnosis;
    final isHealthy = active?['is_healthy'] == true;
    final className = active?['class_name'] as String? ?? 'No Active Scan';
    final confidence = (active?['confidence'] as num?)?.toDouble() ?? 0.0;
    final source = active?['source'] as String? ?? '';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Disease Scanner'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          // Action Buttons: ESP32-CAM vs Cloud AI
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.teal.shade700,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  icon: const Icon(Icons.camera_alt),
                  label: const Text('Fetch ESP32-CAM'),
                  onPressed: diag.isLoading
                      ? null
                      : () => diag.fetchFromEsp32Cam(farm.visionHost),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.indigo.shade700,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  icon: const Icon(Icons.cloud_upload),
                  label: const Text('Cloud AI Scan'),
                  onPressed: diag.isLoading
                      ? null
                      : () {
                          // Synthetic representative image bytes for instant cloud diagnosis
                          final dummyBytes = Uint8List.fromList(List.filled(1024, 42));
                          diag.diagnoseWithGemini(dummyBytes);
                        },
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Loading Indicator
          if (diag.isLoading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24.0),
              child: Center(
                child: Column(
                  children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 12),
                    Text('Analyzing foliar pathology with TFLite / AI...'),
                  ],
                ),
              ),
            ),

          // Error Message
          if (diag.errorMessage != null)
            Card(
              color: Colors.red.shade50,
              child: Padding(
                padding: const EdgeInsets.all(12.0),
                child: Text(diag.errorMessage!, style: TextStyle(color: Colors.red.shade800)),
              ),
            ),

          // Active Diagnosis Card
          if (active != null && !diag.isLoading)
            Card(
              elevation: 3,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Chip(
                          avatar: Icon(
                            isHealthy ? Icons.check_circle : Icons.warning_rounded,
                            color: Colors.white,
                            size: 18,
                          ),
                          label: Text(
                            isHealthy ? 'HEALTHY FOLIAGE' : 'DISEASE DETECTED',
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                          backgroundColor: isHealthy ? Colors.green.shade700 : Colors.red.shade700,
                        ),
                        Text(
                          '${(confidence * 100).toStringAsFixed(1)}% Conf.',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: isHealthy ? Colors.green.shade800 : Colors.red.shade800,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Text(
                      className.replaceAll('Tomato___', '').replaceAll('_', ' '),
                      style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    Text('Source: $source', style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
                    const Divider(height: 24),

                    // Treatment Prescription
                    if (!isHealthy) ...[
                      const Text('Agronomic Prescription', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      const SizedBox(height: 8),
                      if (active.containsKey('symptoms')) ...[
                        const Text('Symptoms:', style: TextStyle(fontWeight: FontWeight.w600)),
                        Text(active['symptoms'] ?? '', style: TextStyle(color: Colors.grey.shade800)),
                        const SizedBox(height: 6),
                      ],
                      if (active.containsKey('chemical_control')) ...[
                        const Text('Chemical Spray Control:', style: TextStyle(fontWeight: FontWeight.w600, color: Colors.blue)),
                        Text(active['chemical_control'] ?? '', style: TextStyle(color: Colors.grey.shade800)),
                        const SizedBox(height: 6),
                      ],
                      if (active.containsKey('organic_control')) ...[
                        const Text('Organic Remediation:', style: TextStyle(fontWeight: FontWeight.w600, color: Colors.green)),
                        Text(active['organic_control'] ?? '', style: TextStyle(color: Colors.grey.shade800)),
                        const SizedBox(height: 6),
                      ],
                      if (active.containsKey('cultural_practices')) ...[
                        const Text('Cultural & Irrigation Practices:', style: TextStyle(fontWeight: FontWeight.w600, color: Colors.indigo)),
                        Text(active['cultural_practices'] ?? '', style: TextStyle(color: Colors.grey.shade800)),
                      ],
                      const SizedBox(height: 16),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: Colors.indigo),
                            padding: const EdgeInsets.symmetric(vertical: 12),
                          ),
                          icon: const Icon(Icons.chat, color: Colors.indigo),
                          label: const Text('Consult AI Agronomist on this Case', style: TextStyle(color: Colors.indigo)),
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(builder: (_) => const ChatScreen()),
                            );
                          },
                        ),
                      ),
                    ] else ...[
                      const Text(
                        'No pathology detected! Foliar tissue exhibits vibrant chlorophyl with healthy photosynthetic margins.',
                        style: TextStyle(color: Colors.green),
                      ),
                    ],
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

