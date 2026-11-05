import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/farm_provider.dart';

class NetworkDiagnosticScreen extends StatefulWidget {
  const NetworkDiagnosticScreen({super.key});

  @override
  State<NetworkDiagnosticScreen> createState() => _NetworkDiagnosticScreenState();
}

class _NetworkDiagnosticScreenState extends State<NetworkDiagnosticScreen> {
  late TextEditingController _irrigationController;

  @override
  void initState() {
    super.initState();
    final farm = context.read<FarmProvider>();
    _irrigationController = TextEditingController(text: farm.irrigationHost);
  }

  @override
  void dispose() {
    _irrigationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final farm = context.watch<FarmProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Device Connectivity'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          // Quick Presets
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Configuration Presets', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      OutlinedButton.icon(
                        icon: const Icon(Icons.android, size: 16),
                        onPressed: () {
                          setState(() {
                            _irrigationController.text = '10.0.2.2:8080';
                          });
                          farm.updateHosts(irrigation: '10.0.2.2:8080');
                        },
                        label: const Text('Android Emulator (10.0.2.2:8080)'),
                      ),
                      OutlinedButton.icon(
                        icon: const Icon(Icons.computer, size: 16),
                        onPressed: () {
                          setState(() {
                            _irrigationController.text = '127.0.0.1:8080';
                          });
                          farm.updateHosts(irrigation: '127.0.0.1:8080');
                        },
                        label: const Text('Web / Localhost (127.0.0.1:8080)'),
                      ),
                      OutlinedButton.icon(
                        icon: const Icon(Icons.wifi, size: 16),
                        onPressed: () {
                          setState(() {
                            _irrigationController.text = '192.168.4.1';
                          });
                          farm.updateHosts(irrigation: '192.168.4.1');
                        },
                        label: const Text('Physical ESP32 (192.168.4.1)'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Host Inputs Card
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('ESP32 Irrigation Node Endpoint', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _irrigationController,
                    decoration: const InputDecoration(
                      labelText: 'ESP32 Node IP / Host:Port',
                      hintText: 'e.g. 192.168.1.100 or 127.0.0.1:8080',
                      prefixIcon: Icon(Icons.router),
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (val) => farm.updateHosts(irrigation: val),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.indigo,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      icon: const Icon(Icons.network_check),
                      label: const Text('Test Connection & Latency'),
                      onPressed: () => farm.testConnectivity(),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Ping Results Card
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Diagnostics & Latency', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                  const SizedBox(height: 12),
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      farm.isConnectedIrrigation ? Icons.check_circle : Icons.cancel,
                      color: farm.isConnectedIrrigation ? Colors.green : Colors.red,
                    ),
                    title: const Text('ESP32 Irrigation Node Ping'),
                    subtitle: Text(farm.irrigationHost),
                    trailing: Text(
                      farm.irrigationPingMs != null ? '${farm.irrigationPingMs} ms' : 'Offline',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: farm.isConnectedIrrigation ? Colors.green : Colors.red,
                      ),
                    ),
                  ),
                  const Divider(),
                  const ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(Icons.smartphone, color: Colors.blue),
                    title: Text('Leaf Pathology Scanner'),
                    subtitle: Text('Mobile Device Camera & Photo Gallery'),
                    trailing: Chip(
                      label: Text('ACTIVE', style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
                      backgroundColor: Colors.blue,
                    ),
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
