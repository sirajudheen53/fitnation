/// A single message within an AI Coach conversation.
class ChatMessage {
  final int? id;
  final String content;
  final bool isUser;
  final DateTime? createdAt;
  final String? recommendation;

  const ChatMessage({
    this.id,
    required this.content,
    required this.isUser,
    this.createdAt,
    this.recommendation,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] as int?,
      content: json['content'] as String? ?? '',
      isUser: (json['sender'] as String?) == 'user' ||
          (json['is_user'] as bool?) == true,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
      recommendation: json['recommendation'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'content': content,
        'sender': isUser ? 'user' : 'ai',
        if (createdAt != null) 'created_at': createdAt!.toIso8601String(),
        if (recommendation != null) 'recommendation': recommendation,
      };

  /// Local message constructor used before a server id is assigned.
  ChatMessage local() => ChatMessage(
        content: content,
        isUser: isUser,
        createdAt: DateTime.now(),
        recommendation: recommendation,
      );
}
