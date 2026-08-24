import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../models/chat_message.dart';

/// A chat bubble that renders either a user (right) or AI (left) message.
class MessageBubble extends StatelessWidget {
  final ChatMessage message;
  final bool isLast;

  const MessageBubble({
    super.key,
    required this.message,
    this.isLast = false,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;

    final bubble = Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: isUser ? AppTheme.primary : AppTheme.surface,
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(16),
          topRight: const Radius.circular(16),
          bottomLeft: Radius.circular(isUser ? 16 : 4),
          bottomRight: Radius.circular(isUser ? 4 : 16),
        ),
        border: isUser ? null : Border.all(color: AppTheme.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            message.content,
            style: TextStyle(
              color: isUser ? Colors.white : AppTheme.textPrimary,
              fontSize: 15,
              height: 1.35,
            ),
          ),
          if (message.recommendation != null &&
              message.recommendation!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.accent.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.lightbulb_outline,
                    size: 16,
                    color: AppTheme.primaryDark,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      message.recommendation!,
                      style: const TextStyle(
                        color: AppTheme.primaryDark,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            const CircleAvatar(
              radius: 16,
              backgroundColor: AppTheme.primaryLight,
              child: Icon(Icons.smart_toy, size: 18, color: Colors.white),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(child: bubble),
        ],
      ),
    );
  }
}
