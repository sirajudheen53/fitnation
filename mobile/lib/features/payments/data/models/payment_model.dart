/// One payment record of the logged-in customer.
///
/// Mirrors the payload of GET /api/v1/payments/ (issue #95), which is
/// self-scoped server-side when the caller is a customer.
class PaymentModel {
  final int id;

  /// membership | admission.
  final String kind;

  /// Decimal string from the API, e.g. "1500.00".
  final String amount;

  /// pending | completed | failed | refunded.
  final String status;
  final String? planName;

  /// Never null from the API (falls back to created_at server-side).
  final DateTime paymentDate;
  final String? notes;

  const PaymentModel({
    required this.id,
    required this.kind,
    required this.amount,
    required this.status,
    this.planName,
    required this.paymentDate,
    this.notes,
  });

  factory PaymentModel.fromJson(Map<String, dynamic> json) {
    return PaymentModel(
      id: json['id'] as int,
      kind: json['kind'] as String,
      amount: json['amount'] as String,
      status: json['status'] as String,
      planName: json['plan_name'] as String?,
      paymentDate: DateTime.parse(
        (json['payment_date'] ?? json['created_at']) as String,
      ),
      notes: json['notes'] as String?,
    );
  }

  bool get isPending => status == 'pending';

  /// Sum of the payments' amounts, parsed from their decimal strings.
  static num totalAmount(List<PaymentModel> payments) => payments.fold(
        0,
        (sum, p) => sum + (num.tryParse(p.amount) ?? 0),
      );

  @override
  String toString() =>
      'PaymentModel(id: $id, kind: $kind, amount: $amount, status: $status)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is PaymentModel && other.id == id;

  @override
  int get hashCode => id.hashCode;
}
