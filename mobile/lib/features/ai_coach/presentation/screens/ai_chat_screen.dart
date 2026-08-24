import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../models/conversation.dart';
import '../providers/ai_coach_provider.dart';
import '../widgets/message_bubble.dart';

/// AI Coach chat interface.
class AiChatScreen extends ConsumerStatefulWidget {
  const AiChatScreen({super.key, this.conversationId});

  final int? conversationId;

  @override
  ConsumerState<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends ConsumerState<AiChatScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    if (widget.conversationId != null) {
      Future.microtask(
        () => ref.read(chatProvider.notifier).loadMessages(widget.conversationId!),
      );
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

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

  Future<void> _send() async {
    final text = _controller.text;
    if (text.trim().isEmpty) return;
    _controller.clear();
    final success = await ref.read(chatProvider.notifier).sendMessage(text);
    if (success) _scrollToBottom();
  }

  void _openHistoryDrawer() {
    _scaffoldKey.currentState?.openDrawer();
  }

  void _startNewChat() async {
    ref.read(chatProvider.notifier).reset();
  }

  void _selectConversation(Conversation conversation) {
    ref.read(chatProvider.notifier).loadMessages(conversation.id);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);

    return Scaffold(
      key: _scaffoldKey,
      appBar: AppBar(
        title: const Text('AI Coach'),
        leading: IconButton(
          icon: const Icon(Icons.history),
          onPressed: _openHistoryDrawer,
          tooltip: 'Conversation history',
        ),
      ),
      drawer: _buildHistoryDrawer(),
      body: Column(
        children: [
          Expanded(
            child: chatState.messages.isEmpty
                ? _buildWelcome()
                : _buildMessageList(chatState),
          ),
          if (chatState.errorMessage != null)
            _ErrorBanner(message: chatState.errorMessage!),
          _buildChatInput(chatState),
        ],
      ),
    );
  }

  Widget _buildWelcome() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: const BoxDecoration(
                color: AppTheme.primaryLight,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.smart_toy,
                size: 36,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Ask your AI Coach',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            const Text(
              'Get workout advice, form tips, and motivation tailored to your goals.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 24),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: const [
                Chip(label: Text('💪 Workout tips')),
                Chip(label: Text('🍎 Nutrition')),
                Chip(label: Text('🎯 Goal setting')),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageList(ChatState chatState) {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(16),
      itemCount: chatState.messages.length + (chatState.isSending ? 1 : 0),
      itemBuilder: (context, index) {
        if (index >= chatState.messages.length) {
          return const Padding(
            padding: EdgeInsets.only(left: 40, bottom: 12),
            child: Align(
              alignment: Alignment.centerLeft,
              child: SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(strokeWidth: 2.5),
              ),
            ),
          );
        }
        final message = chatState.messages[index];
        return MessageBubble(
          message: message,
          isLast: index == chatState.messages.length - 1,
        );
      },
    );
  }

  Widget _buildChatInput(ChatState chatState) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        border: Border(top: BorderSide(color: AppTheme.divider)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: _controller,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _send(),
              decoration: const InputDecoration(
                hintText: 'Type your message…',
                contentPadding: EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 52,
            height: 52,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                padding: EdgeInsets.zero,
                minimumSize: const Size(52, 52),
                shape: const CircleBorder(),
              ),
              onPressed: chatState.isSending ? null : _send,
              child: chatState.isSending
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.send),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHistoryDrawer() {
    final conversationsAsync = ref.watch(conversationsProvider);

    return Drawer(
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  const Icon(Icons.history, color: AppTheme.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Conversations',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.add),
                    onPressed: _startNewChat,
                    tooltip: 'New chat',
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: conversationsAsync.when(
                data: (conversations) {
                  if (conversations.isEmpty) {
                    return const Center(
                      child: Text('No conversations yet'),
                    );
                  }
                  return ListView.separated(
                    itemCount: conversations.length,
                    separatorBuilder: (_, _) =>
                        const Divider(height: 1, indent: 56),
                    itemBuilder: (context, index) {
                      final conversation = conversations[index];
                      return ListTile(
                        leading: const CircleAvatar(
                          backgroundColor: AppTheme.primary,
                          child: Icon(
                            Icons.chat_bubble_outline,
                            color: Colors.white,
                            size: 18,
                          ),
                        ),
                        title: Text(
                          conversation.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: conversation.lastMessageAt != null
                            ? Text(
                                _formatTime(conversation.lastMessageAt!),
                                style: const TextStyle(fontSize: 12),
                              )
                            : null,
                        onTap: () => _selectConversation(conversation),
                      );
                    },
                  );
                },
                loading: () =>
                    const Center(child: CircularProgressIndicator()),
                error: (e, _) => Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    'Could not load history.',
                    style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatTime(DateTime time) {
    return '${time.day}/${time.month}/${time.year}';
  }
}

class _ErrorBanner extends StatelessWidget {
  final String message;
  const _ErrorBanner({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppTheme.error.withValues(alpha: 0.1),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: AppTheme.error, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: AppTheme.error, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}
