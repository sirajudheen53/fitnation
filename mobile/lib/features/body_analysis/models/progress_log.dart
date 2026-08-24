/// A weight-over-time entry used to chart progress.
class ProgressLog {
  final int? id;
  final DateTime? loggedAt;
  final double weight;
  final double? bodyFatPercentage;
  final double? muscleMass;

  const ProgressLog({
    this.id,
    this.loggedAt,
    required this.weight,
    this.bodyFatPercentage,
    this.muscleMass,
  });

  factory ProgressLog.fromJson(Map<String, dynamic> json) {
    return ProgressLog(
      id: json['id'] as int?,
      loggedAt: json['logged_at'] != null
          ? DateTime.tryParse(json['logged_at'].toString())
          : null,
      weight: (json['weight'] as num?)?.toDouble() ?? 0,
      bodyFatPercentage: (json['body_fat_percentage'] as num?)?.toDouble(),
      muscleMass: (json['muscle_mass'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        if (loggedAt != null) 'logged_at': loggedAt!.toIso8601String(),
        'weight': weight,
        if (bodyFatPercentage != null)
          'body_fat_percentage': bodyFatPercentage,
        if (muscleMass != null) 'muscle_mass': muscleMass,
      };
}
