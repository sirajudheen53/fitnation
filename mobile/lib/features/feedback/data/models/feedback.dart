/// Feedback submitted by a customer.
class Feedback {
  final int? id;
  final int? customerId;
  final String? subject;
  final String message;
  final int? rating;
  final String? category;
  final DateTime? submittedAt;
  final String? status;

  const Feedback({
    this.id,
    this.customerId,
    this.subject,
    required this.message,
    this.rating,
    this.category,
    this.submittedAt,
    this.status,
  });

  factory Feedback.fromJson(Map<String, dynamic> json) {
    return Feedback(
      id: json['id'] as int?,
      customerId: json['customer'] as int? ?? json['customer_id'] as int?,
      subject: json['subject'] as String?,
      message: json['message'] as String? ?? '',
      rating: json['rating'] as int?,
      category: json['category'] as String?,
      submittedAt: json['submitted_at'] != null
          ? DateTime.tryParse(json['submitted_at'].toString())
          : null,
      status: json['status'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        if (customerId != null) 'customer': customerId,
        if (subject != null) 'subject': subject,
        'message': message,
        if (rating != null) 'rating': rating,
        if (category != null) 'category': category,
        if (submittedAt != null) 'submitted_at': submittedAt!.toIso8601String(),
        if (status != null) 'status': status,
      };
}
