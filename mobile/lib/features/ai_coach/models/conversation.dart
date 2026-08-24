/// A conversation thread in the AI Coach.
class Conversation {
  final int id;
  final String title;
  final DateTime? createdAt;
  final DateTime? lastMessageAt;
  final int? messageCount;

  const Conversation({
    required this.id,
    required this.title,
    this.createdAt,
    this.lastMessageAt,
    this.messageCount,
  });

  factory Conversation.fromJson(Map<String, dynamic> json) {
    return Conversation(
      id: json['id'] as int,
      title: json['title'] as String? ?? 'New Chat',
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
      lastMessageAt: json['last_message_at'] != null
          ? DateTime.tryParse(json['last_message_at'].toString())
          : null,
      messageCount: json['message_count'] as int?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        if (createdAt != null) 'created_at': createdAt!.toIso8601String(),
        if (lastMessageAt != null)
          'last_message_at': lastMessageAt!.toIso8601String(),
        if (messageCount != null) 'message_count': messageCount,
      };
}
