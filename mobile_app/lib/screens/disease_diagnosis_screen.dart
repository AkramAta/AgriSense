import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../providers/diagnosis_provider.dart';
import 'chat_screen.dart';

class DiseaseDiagnosisScreen extends StatelessWidget {
  const DiseaseDiagnosisScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final diag = context.watch<DiagnosisProvider>();
    final active = diag.activeDiagnosis;
    final isHealthy = active?['is_healthy'] == true;
    final className = active?['class_name'] as String? ?? 'No Active Scan';
    final confidence = (active?['confidence'] as num?)?.toDouble() ?? 0.0;
    final source = active?['source'] as String? ?? '';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Disease Scanner'),
        actions: [
          if (active != null)
            IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: 'New Scan',
              onPressed: () => diag.clearActiveDiagnosis(),
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          // Mobile Camera & Gallery Capture Controls
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.teal.shade700,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  icon: const Icon(Icons.camera_alt),
                  label: const Text('Take Photo',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                  onPressed: diag.isLoading
                      ? null
                      : () => diag.pickAndDiagnose(ImageSource.camera),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.indigo.shade700,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  icon: const Icon(Icons.photo_library),
                  label: const Text('Upload Photo',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                  onPressed: diag.isLoading
                      ? null
                      : () => diag.pickAndDiagnose(ImageSource.gallery),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Engine Status Indicator
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFFE8F5E9),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFA5D6A7)),
            ),
            child: const Row(
              children: [
                Icon(
                  Icons.auto_awesome,
                  size: 18,
                  color: Color(0xFF1B5E20),
                ),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Engine: Gemini 1.5 Flash Vision AI Pathologist',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF1B5E20),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Leaf Image Preview Card
          Card(
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            clipBehavior: Clip.antiAlias,
            elevation: 2,
            child: diag.selectedImageBytes != null
                ? Column(
                    children: [
                      Image.memory(
                        diag.selectedImageBytes!,
                        height: 220,
                        width: double.infinity,
                        fit: BoxFit.cover,
                      ),
                      Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 8),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                diag.selectedImageName ?? 'Captured Leaf Photo',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                    fontSize: 12, color: Colors.grey),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Source: $source',
                              style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.indigo),
                            ),
                          ],
                        ),
                      ),
                    ],
                  )
                : Container(
                    height: 160,
                    width: double.infinity,
                    color: Colors.grey.shade100,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.add_a_photo_outlined,
                            size: 48, color: Colors.grey.shade400),
                        const SizedBox(height: 12),
                        const Text(
                          'No leaf image selected',
                          style: TextStyle(
                              fontWeight: FontWeight.w600,
                              color: Colors.black54),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Take a photo with your mobile camera or upload from gallery',
                          style: TextStyle(
                              fontSize: 12, color: Colors.grey.shade600),
                        ),
                      ],
                    ),
                  ),
          ),
          const SizedBox(height: 16),

          // Loading Progress
          if (diag.isLoading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24.0),
              child: Center(
                child: Column(
                  children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 12),
                    Text('Running AgriSense CNN INT8 Model on foliar image...'),
                  ],
                ),
              ),
            ),

          // Error Message
          if (diag.errorMessage != null)
            Card(
              color: Colors.red.shade50,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: Colors.red.shade300),
              ),
              child: Padding(
                padding: const EdgeInsets.all(12.0),
                child: Row(
                  children: [
                    Icon(Icons.error_outline, color: Colors.red.shade700),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(diag.errorMessage!,
                          style: TextStyle(color: Colors.red.shade900)),
                    ),
                  ],
                ),
              ),
            ),

          // Active Pathology Diagnosis Card
          if (active != null && !diag.isLoading)
            Card(
              elevation: 3,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16)),
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
                            isHealthy
                                ? Icons.check_circle
                                : Icons.warning_rounded,
                            color: Colors.white,
                            size: 18,
                          ),
                          label: Text(
                            isHealthy ? 'HEALTHY FOLIAGE' : 'DISEASE DETECTED',
                            style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold),
                          ),
                          backgroundColor: isHealthy
                              ? Colors.green.shade700
                              : Colors.red.shade700,
                        ),
                        Text(
                          '${(confidence * 100).toStringAsFixed(1)}% Conf.',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: isHealthy
                                ? Colors.green.shade800
                                : Colors.red.shade800,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Text(
                      className
                          .replaceAll('Tomato___', '')
                          .replaceAll('_', ' '),
                      style: const TextStyle(
                          fontSize: 22, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Scanned: ${active['timestamp'] ?? ''} • Via $source',
                      style:
                          TextStyle(fontSize: 12, color: Colors.grey.shade600),
                    ),
                    const Divider(height: 24),

                    // Treatment Prescription
                    if (!isHealthy) ...[
                      const Text('Agronomic Prescription',
                          style: TextStyle(
                              fontWeight: FontWeight.bold, fontSize: 16)),
                      const SizedBox(height: 10),
                      if (active.containsKey('symptoms')) ...[
                        const Text('Symptoms:',
                            style: TextStyle(fontWeight: FontWeight.w600)),
                        Text(active['symptoms'] ?? '',
                            style: TextStyle(color: Colors.grey.shade800)),
                        const SizedBox(height: 8),
                      ],
                      if (active.containsKey('chemical_control')) ...[
                        const Text('Chemical Spray Control:',
                            style: TextStyle(
                                fontWeight: FontWeight.w600,
                                color: Colors.blue)),
                        Text(active['chemical_control'] ?? '',
                            style: TextStyle(color: Colors.grey.shade800)),
                        const SizedBox(height: 8),
                      ],
                      if (active.containsKey('organic_control')) ...[
                        const Text('Organic Remediation:',
                            style: TextStyle(
                                fontWeight: FontWeight.w600,
                                color: Colors.green)),
                        Text(active['organic_control'] ?? '',
                            style: TextStyle(color: Colors.grey.shade800)),
                        const SizedBox(height: 8),
                      ],
                      if (active.containsKey('cultural_practices')) ...[
                        const Text('Cultural & Irrigation Practices:',
                            style: TextStyle(
                                fontWeight: FontWeight.w600,
                                color: Colors.indigo)),
                        Text(active['cultural_practices'] ?? '',
                            style: TextStyle(color: Colors.grey.shade800)),
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
                          label: const Text(
                              'Consult AI Agronomist on this Case',
                              style: TextStyle(color: Colors.indigo)),
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                  builder: (_) => const ChatScreen()),
                            );
                          },
                        ),
                      ),
                    ] else ...[
                      const Text(
                        'No foliar pathology detected! The leaf tissue exhibits healthy chlorophyl pigmentation with intact margins.',
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
