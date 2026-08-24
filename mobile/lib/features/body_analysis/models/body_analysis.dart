/// A completed body analysis with key metrics.
class BodyAnalysis {
  final int? id;
  final DateTime? analyzedAt;
  final double? bmi;
  final double? bodyFatPercentage;
  final double? postureScore;
  final double? weight;
  final double? height;
  final String? status;
  final String? notes;

  const BodyAnalysis({
    this.id,
    this.analyzedAt,
    this.bmi,
    this.bodyFatPercentage,
    this.postureScore,
    this.weight,
    this.height,
    this.status,
    this.notes,
  });

  factory BodyAnalysis.fromJson(Map<String, dynamic> json) {
    return BodyAnalysis(
      id: json['id'] as int?,
      analyzedAt: json['analyzed_at'] != null
          ? DateTime.tryParse(json['analyzed_at'].toString())
          : null,
      bmi: (json['bmi'] as num?)?.toDouble(),
      bodyFatPercentage: (json['body_fat_percentage'] as num?)?.toDouble(),
      postureScore: (json['posture_score'] as num?)?.toDouble(),
      weight: (json['weight'] as num?)?.toDouble(),
      height: (json['height'] as num?)?.toDouble(),
      status: json['status'] as String?,
      notes: json['notes'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        if (analyzedAt != null) 'analyzed_at': analyzedAt!.toIso8601String(),
        if (bmi != null) 'bmi': bmi,
        if (bodyFatPercentage != null) 'body_fat_percentage': bodyFatPercentage,
        if (postureScore != null) 'posture_score': postureScore,
        if (weight != null) 'weight': weight,
        if (height != null) 'height': height,
        if (status != null) 'status': status,
        if (notes != null) 'notes': notes,
      };
}
