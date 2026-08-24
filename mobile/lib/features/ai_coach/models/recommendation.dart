/// An actionable recommendation produced by the AI Coach.
class Recommendation {
  final int? id;
  final String title;
  final String description;
  final String? category;
  final int? priority;
  final bool isApplied;

  const Recommendation({
    this.id,
    required this.title,
    required this.description,
    this.category,
    this.priority,
    this.isApplied = false,
  });

  factory Recommendation.fromJson(Map<String, dynamic> json) {
    return Recommendation(
      id: json['id'] as int?,
      title: json['title'] as String? ?? 'Recommendation',
      description: json['description'] as String? ?? '',
      category: json['category'] as String?,
      priority: json['priority'] as int?,
      isApplied: (json['is_applied'] as bool?) ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'title': title,
        'description': description,
        if (category != null) 'category': category,
        if (priority != null) 'priority': priority,
        'is_applied': isApplied,
      };
}
