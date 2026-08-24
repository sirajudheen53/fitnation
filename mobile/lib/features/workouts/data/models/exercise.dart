/// Exercise model from the exercise library.
class Exercise {
  final int id;
  final String name;
  final String? description;
  final String? category;
  final String? difficulty;
  final String? muscleGroup;
  final String? equipment;
  final String? imageUrl;
  final String? videoUrl;
  final List<String> instructions;

  const Exercise({
    required this.id,
    required this.name,
    this.description,
    this.category,
    this.difficulty,
    this.muscleGroup,
    this.equipment,
    this.imageUrl,
    this.videoUrl,
    this.instructions = const [],
  });

  factory Exercise.fromJson(Map<String, dynamic> json) {
    return Exercise(
      id: json['id'] as int,
      name: json['name'] as String? ?? 'Exercise',
      description: json['description'] as String?,
      category: json['category'] as String?,
      difficulty: json['difficulty'] as String?,
      muscleGroup: json['muscle_group'] as String?,
      equipment: json['equipment'] as String?,
      imageUrl: json['image_url'] as String?,
      videoUrl: json['video_url'] as String?,
      instructions: (json['instructions'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'description': description,
        'category': category,
        'difficulty': difficulty,
        'muscle_group': muscleGroup,
        'equipment': equipment,
        'image_url': imageUrl,
        'video_url': videoUrl,
        'instructions': instructions,
      };
}
