import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:intl/intl.dart';
import '../services/gemini_service.dart';

class ChatMessage {
  final String text;
  final bool isUser;
  final String timestamp;

  const ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
  });
}

class ChatProvider extends ChangeNotifier {
  final GeminiService _geminiService;

  final List<ChatMessage> messages = [];
  bool isTyping = false;

  ChatProvider({GeminiService? geminiService})
      : _geminiService = geminiService ?? GeminiService() {
    // Welcome message
    messages.add(ChatMessage(
      text: "👋 Welcome to AgriSense AI! I'm your plant pathologist and irrigation specialist. "
          "Ask me about tomato diseases, treatment sprays, or optimal watering schedules.",
      isUser: false,
      timestamp: DateFormat('HH:mm').format(DateTime.now()),
    ));
  }

  Future<void> sendMessage(String text, {Map<String, dynamic>? activeDiagnosis}) async {
    final clean = text.trim();
    if (clean.isEmpty) return;

    final userTime = DateFormat('HH:mm').format(DateTime.now());
    messages.add(ChatMessage(text: clean, isUser: true, timestamp: userTime));
    isTyping = true;
    notifyListeners();

    try {
      final reply = await _geminiService.sendChatMessage(clean, activeDiagnosis: activeDiagnosis);
      final aiTime = DateFormat('HH:mm').format(DateTime.now());
      messages.add(ChatMessage(text: reply, isUser: false, timestamp: aiTime));
    } catch (e) {
      messages.add(ChatMessage(
        text: "Error retrieving advice: ${e.toString()}",
        isUser: false,
        timestamp: DateFormat('HH:mm').format(DateTime.now()),
      ));
    } finally {
      isTyping = false;
      notifyListeners();
    }
  }

  void clearChat() {
    messages.clear();
    messages.add(ChatMessage(
      text: "Conversation reset. How can I assist with your crops today?",
      isUser: false,
      timestamp: DateFormat('HH:mm').format(DateTime.now()),
    ));
    notifyListeners();
  }
}
