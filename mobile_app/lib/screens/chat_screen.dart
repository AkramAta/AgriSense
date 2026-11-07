import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/env_config.dart';
import '../providers/chat_provider.dart';
import '../providers/diagnosis_provider.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  int _lastMessageCount = 0;
  bool _lastTyping = false;

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _send([String? customText]) {
    final text = customText ?? _controller.text;
    if (text.trim().isEmpty) return;

    final diag = context.read<DiagnosisProvider>();
    context.read<ChatProvider>().sendMessage(text, activeDiagnosis: diag.activeDiagnosis);
    _controller.clear();
    _scrollToBottom();
  }

  List<InlineSpan> _parseInlineSpans(String text, TextStyle baseStyle, Color boldColor) {
    final spans = <InlineSpan>[];
    final regex = RegExp(r'\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`');
    int lastEnd = 0;

    for (final match in regex.allMatches(text)) {
      if (match.start > lastEnd) {
        spans.add(TextSpan(
          text: text.substring(lastEnd, match.start),
          style: baseStyle,
        ));
      }

      if (match.group(1) != null) {
        // Bold: **text**
        spans.add(TextSpan(
          text: match.group(1),
          style: baseStyle.copyWith(
            fontWeight: FontWeight.bold,
            color: boldColor,
          ),
        ));
      } else if (match.group(2) != null) {
        // Italic: *text*
        spans.add(TextSpan(
          text: match.group(2),
          style: baseStyle.copyWith(
            fontStyle: FontStyle.italic,
          ),
        ));
      } else if (match.group(3) != null) {
        // Code: `code`
        spans.add(TextSpan(
          text: match.group(3),
          style: baseStyle.copyWith(
            fontFamily: 'monospace',
            backgroundColor: Colors.black12,
          ),
        ));
      }

      lastEnd = match.end;
    }

    if (lastEnd < text.length) {
      spans.add(TextSpan(
        text: text.substring(lastEnd),
        style: baseStyle,
      ));
    }

    return spans;
  }

  Widget _buildMessageContent(String rawText, bool isUser) {
    // Clean raw prefixes if any
    final cleanText = rawText.replaceAll('Tomato___', '').replaceAll('___', ' ');
    final lines = cleanText.split('\n');

    final baseTextColor = isUser ? Colors.white : Colors.black87;
    final boldTextColor = isUser ? Colors.white : Colors.black;
    final bulletColor = isUser ? Colors.white70 : Colors.indigo.shade700;

    final baseStyle = TextStyle(
      color: baseTextColor,
      fontSize: 14,
      height: 1.4,
    );

    final List<Widget> widgets = [];

    for (int i = 0; i < lines.length; i++) {
      final line = lines[i].trim();
      if (line.isEmpty) {
        if (i > 0 && i < lines.length - 1) {
          widgets.add(const SizedBox(height: 6));
        }
        continue;
      }

      final isBullet = line.startsWith('• ') || line.startsWith('- ') || line.startsWith('* ');
      final lineBody = isBullet ? line.substring(2).trim() : line;
      final spans = _parseInlineSpans(lineBody, baseStyle, boldTextColor);

      if (isBullet) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(top: 2.0, bottom: 2.0, left: 4.0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '• ',
                  style: TextStyle(
                    color: bulletColor,
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                    height: 1.4,
                  ),
                ),
                Expanded(
                  child: RichText(
                    text: TextSpan(children: spans),
                  ),
                ),
              ],
            ),
          ),
        );
      } else {
        widgets.add(
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2.0),
            child: RichText(
              text: TextSpan(children: spans),
            ),
          ),
        );
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: widgets,
    );
  }

  @override
  Widget build(BuildContext context) {
    final chat = context.watch<ChatProvider>();
    final diag = context.watch<DiagnosisProvider>();
    final activeDiag = diag.activeDiagnosis;

    // Trigger auto-scroll on new message or typing state change
    if (chat.messages.length != _lastMessageCount || chat.isTyping != _lastTyping) {
      _lastMessageCount = chat.messages.length;
      _lastTyping = chat.isTyping;
      _scrollToBottom();
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Agronomist Chat'),
        actions: [
          IconButton(
            icon: const Icon(Icons.key),
            tooltip: 'Gemini API Key Security Settings',
            onPressed: () {
              final diag = context.read<DiagnosisProvider>();
              final keyController = TextEditingController(text: diag.apiKey);
              final obscureNotifier = ValueNotifier<bool>(true);

              showDialog(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Row(
                    children: [
                      Icon(Icons.security, color: Colors.green),
                      SizedBox(width: 8),
                      Text('Gemini API Key Security'),
                    ],
                  ),
                  content: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: Colors.grey.shade100,
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: Colors.grey.shade300),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.lock, size: 16, color: Colors.green),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                'Current: ${EnvConfig.maskApiKey(diag.apiKey)}',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  fontFamily: 'monospace',
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        'Your API key is stored securely in local device storage and is never transmitted to third parties. Enter a new key or leave blank for offline specialist consultation.',
                        style: TextStyle(fontSize: 11, color: Colors.black87),
                      ),
                      const SizedBox(height: 12),
                      ValueListenableBuilder<bool>(
                        valueListenable: obscureNotifier,
                        builder: (context, isObscured, _) {
                          return TextField(
                            controller: keyController,
                            obscureText: isObscured,
                            decoration: InputDecoration(
                              labelText: 'Google Gemini API Key',
                              border: const OutlineInputBorder(),
                              suffixIcon: IconButton(
                                icon: Icon(
                                  isObscured ? Icons.visibility_off : Icons.visibility,
                                  size: 20,
                                ),
                                tooltip: isObscured ? 'Show Key' : 'Hide Key',
                                onPressed: () => obscureNotifier.value = !isObscured,
                              ),
                            ),
                          );
                        },
                      ),
                    ],
                  ),
                  actions: [
                    TextButton(
                      onPressed: () async {
                        await diag.setApiKey('');
                        if (ctx.mounted) Navigator.pop(ctx);
                      },
                      child: const Text('Reset', style: TextStyle(color: Colors.red)),
                    ),
                    TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('Cancel'),
                    ),
                    ElevatedButton(
                      onPressed: () async {
                        await diag.setApiKey(keyController.text.trim());
                        if (ctx.mounted) Navigator.pop(ctx);
                      },
                      child: const Text('Save'),
                    ),
                  ],
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Clear Chat',
            onPressed: () => chat.clearChat(),
          ),
        ],
      ),
      body: Column(
        children: [
          // Active Diagnosis Context Pill
          if (activeDiag != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: Colors.indigo.shade50,
              child: Row(
                children: [
                  const Icon(Icons.info_outline, size: 18, color: Colors.indigo),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Context: ${(activeDiag['class_name'] as String).replaceAll('Tomato___', '').replaceAll('_', ' ')}',
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.indigo),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),

          // Message List
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.fromLTRB(16.0, 16.0, 16.0, 16.0),
              itemCount: chat.messages.length,
              itemBuilder: (context, index) {
                final msg = chat.messages[index];
                return Align(
                  alignment: msg.isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(vertical: 4.0),
                    padding: const EdgeInsets.symmetric(horizontal: 14.0, vertical: 10.0),
                    constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.82),
                    decoration: BoxDecoration(
                      color: msg.isUser ? Colors.indigo.shade600 : Colors.grey.shade200,
                      borderRadius: BorderRadius.circular(16).copyWith(
                        bottomRight: msg.isUser ? const Radius.circular(0) : null,
                        bottomLeft: !msg.isUser ? const Radius.circular(0) : null,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildMessageContent(msg.text, msg.isUser),
                        const SizedBox(height: 6),
                        Align(
                          alignment: Alignment.bottomRight,
                          child: Text(
                            msg.timestamp,
                            style: TextStyle(
                              fontSize: 10,
                              color: msg.isUser ? Colors.white70 : Colors.black54,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),

          // Typing Indicator
          if (chat.isTyping)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16.0, vertical: 4.0),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text('AI Agronomist is preparing recommendations...', style: TextStyle(fontSize: 12, fontStyle: FontStyle.italic, color: Colors.grey)),
              ),
            ),

          // Quick Suggestion Chips (Context-Aware)
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: Row(
              children: activeDiag != null
                  ? [
                      ActionChip(
                        avatar: const Icon(Icons.format_list_numbered, size: 16),
                        label: const Text('Action Steps'),
                        onPressed: () => _send('I want steps'),
                      ),
                      const SizedBox(width: 6),
                      ActionChip(
                        avatar: const Icon(Icons.spa, size: 16),
                        label: const Text('Alternative Remedies'),
                        onPressed: () => _send('Is there another solution?'),
                      ),
                      const SizedBox(width: 6),
                      ActionChip(
                        avatar: const Icon(Icons.sanitizer, size: 16),
                        label: const Text('Spray Dosage'),
                        onPressed: () => _send('What is the spray dosage and application interval?'),
                      ),
                      const SizedBox(width: 6),
                      ActionChip(
                        avatar: const Icon(Icons.water_drop, size: 16),
                        label: const Text('Irrigation Guard'),
                        onPressed: () => _send('What soil moisture range should I maintain?'),
                      ),
                    ]
                  : [
                      ActionChip(
                        avatar: const Icon(Icons.eco, size: 16),
                        label: const Text('Disease Scout'),
                        onPressed: () => _send('How do I identify and treat leaf diseases?'),
                      ),
                      const SizedBox(width: 6),
                      ActionChip(
                        avatar: const Icon(Icons.water_drop, size: 16),
                        label: const Text('Irrigation Schedule'),
                        onPressed: () => _send('What soil moisture range should I maintain?'),
                      ),
                      const SizedBox(width: 6),
                      ActionChip(
                        avatar: const Icon(Icons.grass, size: 16),
                        label: const Text('Organic Sprays'),
                        onPressed: () => _send('What organic fungicide or soap can I spray?'),
                      ),
                    ],
            ),
          ),

          // Message Input Field
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12.0, vertical: 8.0),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      decoration: InputDecoration(
                        hintText: 'Ask about plant health or watering...',
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(24)),
                      ),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    icon: const Icon(Icons.send),
                    onPressed: () => _send(),
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

