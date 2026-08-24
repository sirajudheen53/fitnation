/// A photo uploaded for body analysis, tagged by view type.
class BodyPhoto {
  final int? id;
  final String? url;
  final String photoType;
  final DateTime? uploadedAt;
  final String? status;

  const BodyPhoto({
    this.id,
    this.url,
    required this.photoType,
    this.uploadedAt,
    this.status,
  });

  /// Allowed photo view types.
  static const List<String> types = ['front', 'side', 'back'];

  factory BodyPhoto.fromJson(Map<String, dynamic> json) {
    return BodyPhoto(
      id: json['id'] as int?,
      url: json['url'] as String?,
      photoType: json['photo_type'] as String? ?? 'front',
      uploadedAt: json['uploaded_at'] != null
          ? DateTime.tryParse(json['uploaded_at'].toString())
          : null,
      status: json['status'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        if (url != null) 'url': url,
        'photo_type': photoType,
        if (uploadedAt != null) 'uploaded_at': uploadedAt!.toIso8601String(),
        if (status != null) 'status': status,
      };
}
