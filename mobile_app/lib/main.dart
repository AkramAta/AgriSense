import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/chat_provider.dart';
import 'providers/diagnosis_provider.dart';
import 'providers/farm_provider.dart';
import 'screens/chat_screen.dart';
import 'screens/diagnosis_history_screen.dart';
import 'screens/disease_diagnosis_screen.dart';
import 'screens/irrigation_control_screen.dart';
import 'screens/sensor_dashboard_screen.dart';
import 'services/gemini_service.dart';
import 'services/storage_service.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final geminiService = GeminiService();
  final storageService = StorageService();
  runApp(AgriSenseApp(
    geminiService: geminiService,
    storageService: storageService,
  ));
}

class AgriSenseApp extends StatelessWidget {
  final GeminiService geminiService;
  final StorageService storageService;

  AgriSenseApp({
    super.key,
    GeminiService? geminiService,
    StorageService? storageService,
  })  : geminiService = geminiService ?? GeminiService(),
        storageService = storageService ?? StorageService();

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => FarmProvider()..startPolling()),
        ChangeNotifierProvider(
          create: (_) => DiagnosisProvider(
            geminiService: geminiService,
            storageService: storageService,
          ),
        ),
        ChangeNotifierProvider(
          create: (_) => ChatProvider(
            geminiService: geminiService,
          ),
        ),
      ],
      child: MaterialApp(
        title: 'AgriSense',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF2E7D32), // Forest Green
            primary: const Color(0xFF1B5E20),
            secondary: const Color(0xFF0277BD),
          ),
          cardTheme: const CardThemeData(
            elevation: 1.5,
          ),
          appBarTheme: const AppBarTheme(
            centerTitle: true,
            elevation: 0,
          ),
        ),
        home: const MainNavigationShell(),
      ),
    );
  }
}

class MainNavigationShell extends StatefulWidget {
  const MainNavigationShell({super.key});

  @override
  State<MainNavigationShell> createState() => _MainNavigationShellState();
}

class _MainNavigationShellState extends State<MainNavigationShell> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    SensorDashboardScreen(),
    IrrigationControlScreen(),
    DiseaseDiagnosisScreen(),
    DiagnosisHistoryScreen(),
    ChatScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      drawer: Drawer(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            const DrawerHeader(
              decoration: BoxDecoration(
                color: Color(0xFF1B5E20),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Icon(Icons.eco, size: 48, color: Colors.white),
                  SizedBox(height: 8),
                  Text(
                    'AgriSense Precision IoT',
                    style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  Text(
                    'Smart Irrigation & Pathology',
                    style: TextStyle(color: Colors.white70, fontSize: 12),
                  ),
                ],
              ),
            ),
            ListTile(
              leading: const Icon(Icons.dashboard),
              title: const Text('Sensor Dashboard'),
              selected: _currentIndex == 0,
              onTap: () {
                setState(() => _currentIndex = 0);
                Navigator.pop(context);
              },
            ),
            ListTile(
              leading: const Icon(Icons.water_drop),
              title: const Text('Irrigation Control'),
              selected: _currentIndex == 1,
              onTap: () {
                setState(() => _currentIndex = 1);
                Navigator.pop(context);
              },
            ),
            ListTile(
              leading: const Icon(Icons.coronavirus),
              title: const Text('Disease Scanner'),
              selected: _currentIndex == 2,
              onTap: () {
                setState(() => _currentIndex = 2);
                Navigator.pop(context);
              },
            ),
            ListTile(
              leading: const Icon(Icons.history),
              title: const Text('Diagnosis History'),
              selected: _currentIndex == 3,
              onTap: () {
                setState(() => _currentIndex = 3);
                Navigator.pop(context);
              },
            ),
            ListTile(
              leading: const Icon(Icons.chat),
              title: const Text('AI Agronomist Chat'),
              selected: _currentIndex == 4,
              onTap: () {
                setState(() => _currentIndex = 4);
                Navigator.pop(context);
              },
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.settings_ethernet),
              title: const Text('Device Connectivity'),
              onTap: () {
                Navigator.pop(context);
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const NetworkDiagnosticScreen()),
                );
              },
            ),
          ],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (idx) => setState(() => _currentIndex = idx),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard_outlined), selectedIcon: Icon(Icons.dashboard), label: 'Telemetry'),
          NavigationDestination(icon: Icon(Icons.water_drop_outlined), selectedIcon: Icon(Icons.water_drop), label: 'Irrigation'),
          NavigationDestination(icon: Icon(Icons.camera_alt_outlined), selectedIcon: Icon(Icons.camera_alt), label: 'Scanner'),
          NavigationDestination(icon: Icon(Icons.history_outlined), selectedIcon: Icon(Icons.history), label: 'History'),
          NavigationDestination(icon: Icon(Icons.chat_outlined), selectedIcon: Icon(Icons.chat), label: 'AI Chat'),
        ],
      ),
    );
  }
}
