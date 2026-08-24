/// An item in a generated shopping list.
class ShoppingListItem {
  final int? id;
  final String name;
  final double? quantity;
  final String? unit;
  final bool isChecked;

  const ShoppingListItem({
    this.id,
    required this.name,
    this.quantity,
    this.unit,
    this.isChecked = false,
  });

  factory ShoppingListItem.fromJson(Map<String, dynamic> json) {
    return ShoppingListItem(
      id: json['id'] as int?,
      name: json['name'] as String? ?? 'Item',
      quantity: (json['quantity'] as num?)?.toDouble(),
      unit: json['unit'] as String?,
      isChecked: (json['is_checked'] as bool?) ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'name': name,
        if (quantity != null) 'quantity': quantity,
        if (unit != null) 'unit': unit,
        'is_checked': isChecked,
      };
}
