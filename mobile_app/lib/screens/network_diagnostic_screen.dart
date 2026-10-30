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
  late TextEditingController _visionController;

  @override
  void initState() {
    super.initState();
    final farm = context.read<FarmProvider>();
    _irrigationController = TextEditingController(text: farm.irrigationHost);
    _visionController = TextEditingController(text: farm.visionHost);
  }

  @override
  void dispose() {
    _irrigationController.dispose();
    _visionController.dispose();
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
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () {
                            setState(() {
                              _irrigationController.text = '127.0.0.1:8080';
                              _visionController.text = '127.0.0.1:8081';
                            });
                            farm.updateHosts(irrigation: '127.0.0.1:8080', vision: '127.0.0.1:8081');
                          },
                          child: const Text('Simulator (Local)'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () {
                            setState(() {
                              _irrigationController.text = '192.168.4.1';
                              _visionController.text = '192.168.4.2';
                            });
                            farm.updateHosts(irrigation: '192.168.4.1', vision: '192.168.4.2');
                          },
                          child: const Text('ESP32 Soft AP'),
                        ),
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
                  const Text('Network Endpoints', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _irrigationController,
                    decoration: const InputDecoration(
                      labelText: 'ESP32 Irrigation Node Host:Port',
                      hintText: 'e.g. 192.168.1.100 or 127.0.0.1:8080',
                      prefixIcon: Icon(Icons.router),
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (val) => farm.updateHosts(irrigation: val),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _visionController,
                    decoration: const InputDecoration(
                      labelText: 'ESP32-CAM Vision Node Host:Port',
                      hintText: 'e.g. 192.168.1.101 or 127.0.0.1:8081',
                      prefixIcon: Icon(Icons.videocam),
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (val) => farm.updateHosts(vision: val),
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
                      label: const Text('Test Network Connectivity'),
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
                    title: const Text('Irrigation Node Ping'),
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
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      farm.isConnectedVision ? Icons.check_circle : Icons.cancel,
                      color: farm.isConnectedVision ? Colors.green : Colors.red,
                    ),
                    title: const Text('Vision Node Ping'),
                    subtitle: Text(farm.visionHost),
                    trailing: Text(
                      farm.visionPingMs != null ? '${farm.visionPingMs} ms' : 'Offline',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: farm.isConnectedVision ? Colors.green : Colors.red,
                      ),
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
