import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart' as ffi;
import 'package:sqflite_common_ffi_web/sqflite_ffi_web.dart' as web_ffi;

/// Historical diagnostic scan model.
class DiagnosisHistoryItem {
  final int? id;
  final String className;
  final double confidence;
  final bool isHealthy;
  final String source; // "ESP32_CAM" or "MOBILE_GALLERY" or "CLOUD"
  final String treatmentSummary;
  final String createdAt;

  const DiagnosisHistoryItem({
    this.id,
    required this.className,
    required this.confidence,
    required this.isHealthy,
    required this.source,
    required this.treatmentSummary,
    required this.createdAt,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'class_name': className,
      'confidence': confidence,
      'is_healthy': isHealthy ? 1 : 0,
      'source': source,
      'treatment_summary': treatmentSummary,
      'created_at': createdAt,
    };
  }

  factory DiagnosisHistoryItem.fromMap(Map<String, dynamic> map) {
    return DiagnosisHistoryItem(
      id: map['id'] as int?,
      className: map['class_name'] as String? ?? 'Unknown',
      confidence: (map['confidence'] as num?)?.toDouble() ?? 0.0,
      isHealthy: (map['is_healthy'] as int?) == 1,
      source: map['source'] as String? ?? 'LOCAL',
      treatmentSummary: map['treatment_summary'] as String? ?? '',
      createdAt: map['created_at'] as String? ?? '',
    );
  }
}

/// Cross-platform local persistence layer (SQLite on Mobile/Desktop, IndexedDB on Web).
class StorageService {
  static final StorageService _instance = StorageService._internal();
  factory StorageService() => _instance;
  StorageService._internal();

  Database? _db;
  final List<DiagnosisHistoryItem> _inMemoryFallback = [];
  final Map<String, String> _settingsFallback = {};

  Future<Database> get database async {
    if (_db != null) return _db!;
    _db = await _initDatabase();
    return _db!;
  }

  Future<Database> _initDatabase() async {
    if (kIsWeb) {
      // Web IndexedDB backing via sqflite_common_ffi_web
      databaseFactory = web_ffi.databaseFactoryFfiWeb;
      return await databaseFactory.openDatabase('agrisense_diagnoses_web.db',
          options: OpenDatabaseOptions(
            version: 1,
            onCreate: _createTables,
          ));
    } else {
      // Mobile / Desktop SQLite backing
      try {
        final dbPath = await getDatabasesPath();
        final path = p.join(dbPath, 'agrisense_diagnoses.db');
        return await openDatabase(
          path,
          version: 1,
          onCreate: _createTables,
        );
      } catch (_) {
        // Fallback for native test runners
        ffi.sqfliteFfiInit();
        databaseFactory = ffi.databaseFactoryFfi;
        return await databaseFactory.openDatabase(inMemoryDatabasePath,
            options: OpenDatabaseOptions(
              version: 1,
              onCreate: _createTables,
            ));
      }
    }
  }

  Future<void> _createTables(Database db, int version) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS diagnoses_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name TEXT NOT NULL,
        confidence REAL NOT NULL,
        is_healthy INTEGER NOT NULL,
        source TEXT NOT NULL,
        treatment_summary TEXT,
        created_at TEXT NOT NULL
      )
    ''');
    await db.execute('''
      CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
    ''');
  }

  Future<void> saveSetting(String key, String value) async {
    _settingsFallback[key] = value;
    try {
      final db = await database;
      await db.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        )
      ''');
      await db.insert(
        'app_settings',
        {'key': key, 'value': value},
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    } catch (_) {}
  }

  Future<String?> getSetting(String key) async {
    try {
      final db = await database;
      await db.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        )
      ''');
      final res = await db.query(
        'app_settings',
        where: 'key = ?',
        whereArgs: [key],
        limit: 1,
      );
      if (res.isNotEmpty) {
        return res.first['value'] as String?;
      }
    } catch (_) {}
    return _settingsFallback[key];
  }

  Future<int> insertDiagnosis(DiagnosisHistoryItem item) async {
    try {
      final db = await database;
      return await db.insert('diagnoses_history', item.toMap());
    } catch (_) {
      // In-memory fallback
      final id = _inMemoryFallback.length + 1;
      _inMemoryFallback.insert(0, DiagnosisHistoryItem(
        id: id,
        className: item.className,
        confidence: item.confidence,
        isHealthy: item.isHealthy,
        source: item.source,
        treatmentSummary: item.treatmentSummary,
        createdAt: item.createdAt,
      ));
      return id;
    }
  }

  Future<List<DiagnosisHistoryItem>> getAllDiagnoses() async {
    try {
      final db = await database;
      final maps = await db.query('diagnoses_history', orderBy: 'id DESC');
      return maps.map((m) => DiagnosisHistoryItem.fromMap(m)).toList();
    } catch (_) {
      return List.unmodifiable(_inMemoryFallback);
    }
  }

  Future<void> deleteDiagnosis(int id) async {
    try {
      final db = await database;
      await db.delete('diagnoses_history', where: 'id = ?', whereArgs: [id]);
    } catch (_) {
      _inMemoryFallback.removeWhere((item) => item.id == id);
    }
  }

  Future<void> clearAll() async {
    try {
      final db = await database;
      await db.delete('diagnoses_history');
    } catch (_) {
      _inMemoryFallback.clear();
    }
  }
}

