/// A body measurement record for a customer.
class BodyMeasurement {
  final int id;
  final DateTime? measuredAt;
  final double? weight;
  final double? height;
  final double? bmi;
  final double? bodyFat;
  final double? chest;
  final double? waist;
  final double? hips;
  final double? arms;
  final double? thighs;

  const BodyMeasurement({
    required this.id,
    this.measuredAt,
    this.weight,
    this.height,
    this.bmi,
    this.bodyFat,
    this.chest,
    this.waist,
    this.hips,
    this.arms,
    this.thighs,
  });

  factory BodyMeasurement.fromJson(Map<String, dynamic> json) {
    return BodyMeasurement(
      id: json['id'] as int,
      measuredAt: json['measured_at'] != null
          ? DateTime.tryParse(json['measured_at'].toString())
          : null,
      weight: (json['weight'] as num?)?.toDouble(),
      height: (json['height'] as num?)?.toDouble(),
      bmi: (json['bmi'] as num?)?.toDouble(),
      bodyFat: (json['body_fat'] as num?)?.toDouble(),
      chest: (json['chest'] as num?)?.toDouble(),
      waist: (json['waist'] as num?)?.toDouble(),
      hips: (json['hips'] as num?)?.toDouble(),
      arms: (json['arms'] as num?)?.toDouble(),
      thighs: (json['thighs'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (measuredAt != null) 'measured_at': measuredAt!.toIso8601String(),
        if (weight != null) 'weight': weight,
        if (height != null) 'height': height,
        if (bmi != null) 'bmi': bmi,
        if (bodyFat != null) 'body_fat': bodyFat,
        if (chest != null) 'chest': chest,
        if (waist != null) 'waist': waist,
        if (hips != null) 'hips': hips,
        if (arms != null) 'arms': arms,
        if (thighs != null) 'thighs': thighs,
      };
}

/// A fitness goal for a customer.
class FitnessGoal {
  final int id;
  final String? goalType;
  final String? description;
  final double? targetWeight;
  final DateTime? targetDate;
  final String? status;

  const FitnessGoal({
    required this.id,
    this.goalType,
    this.description,
    this.targetWeight,
    this.targetDate,
    this.status,
  });

  factory FitnessGoal.fromJson(Map<String, dynamic> json) {
    return FitnessGoal(
      id: json['id'] as int,
      goalType: json['goal_type'] as String?,
      description: json['description'] as String?,
      targetWeight: (json['target_weight'] as num?)?.toDouble(),
      targetDate: json['target_date'] != null
          ? DateTime.tryParse(json['target_date'].toString())
          : null,
      status: json['status'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (goalType != null) 'goal_type': goalType,
        if (description != null) 'description': description,
        if (targetWeight != null) 'target_weight': targetWeight,
        if (targetDate != null) 'target_date': targetDate!.toIso8601String(),
        if (status != null) 'status': status,
      };
}

/// A progress photo for a customer.
class ProgressPhoto {
  final int id;
  final String? imageUrl;
  final DateTime? takenAt;
  final String? note;

  const ProgressPhoto({
    required this.id,
    this.imageUrl,
    this.takenAt,
    this.note,
  });

  factory ProgressPhoto.fromJson(Map<String, dynamic> json) {
    return ProgressPhoto(
      id: json['id'] as int,
      imageUrl: json['image_url'] as String?,
      takenAt: json['taken_at'] != null
          ? DateTime.tryParse(json['taken_at'].toString())
          : null,
      note: json['note'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (imageUrl != null) 'image_url': imageUrl,
        if (takenAt != null) 'taken_at': takenAt!.toIso8601String(),
        if (note != null) 'note': note,
      };
}
