import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/diagnosis_provider.dart';

class DiagnosisHistoryScreen extends StatelessWidget {
  const DiagnosisHistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final diag = context.watch<DiagnosisProvider>();
    final history = diag.history;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Diagnosis History'),
        actions: [
          if (history.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.delete_sweep),
              tooltip: 'Clear History',
              onPressed: () async {
                final confirm = await showDialog<bool>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    title: const Text('Clear All History?'),
                    content: const Text('This will delete all saved diagnostic records from local storage.'),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                      TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Clear All', style: TextStyle(color: Colors.red))),
                    ],
                  ),
                );
                if (confirm == true) {
                  await diag.clearAllHistory();
                }
              },
            ),
        ],
      ),
      body: history.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.history_edu, size: 64, color: Colors.grey.shade400),
                  const SizedBox(height: 12),
                  const Text('No diagnosis records saved yet', style: TextStyle(fontSize: 16, color: Colors.grey)),
                  const SizedBox(height: 4),
                  const Text('Scans from ESP32-CAM and Cloud AI will appear here.', style: TextStyle(fontSize: 12, color: Colors.grey)),
                ],
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(12.0),
              itemCount: history.length,
              itemBuilder: (context, index) {
                final item = history[index];
                final readableName = item.className.replaceAll('Tomato___', '').replaceAll('_', ' ');

                return Dismissible(
                  key: Key('diag_${item.id}_$index'),
                  direction: DismissDirection.endToStart,
                  background: Container(
                    alignment: Alignment.centerRight,
                    padding: const EdgeInsets.only(right: 20),
                    color: Colors.red.shade700,
                    child: const Icon(Icons.delete, color: Colors.white),
                  ),
                  onDismissed: (_) {
                    if (item.id != null) {
                      diag.deleteHistoryItem(item.id!);
                    }
                  },
                  child: Card(
                    margin: const EdgeInsets.symmetric(vertical: 6),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    child: ListTile(
                      leading: CircleAvatar(
                        backgroundColor: item.isHealthy ? Colors.green.shade100 : Colors.red.shade100,
                        child: Icon(
                          item.isHealthy ? Icons.eco : Icons.coronavirus,
                          color: item.isHealthy ? Colors.green.shade800 : Colors.red.shade800,
                        ),
                      ),
                      title: Text(readableName, style: const TextStyle(fontWeight: FontWeight.bold)),
                      subtitle: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SizedBox(height: 2),
                          Text('${item.source} • ${item.createdAt}', style: const TextStyle(fontSize: 11)),
                          if (item.treatmentSummary.isNotEmpty)
                            Text(
                              item.treatmentSummary,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
                            ),
                        ],
                      ),
                      trailing: Text(
                        '${(item.confidence * 100).toStringAsFixed(0)}%',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: item.isHealthy ? Colors.green.shade800 : Colors.red.shade800,
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
    );
  }
}
