"use client";

import { InventoryItem } from "@/types/inventory";
import { Badge, Card, CardBody } from "@/components/ui";

/** Stock bar color by fill ratio. */
function stockColor(item: InventoryItem): string {
  if (!item.track_inventory) return "bg-gray-300";
  if (item.is_low_stock) return "bg-red-500";
  const ratio = item.low_stock_threshold
    ? item.stock_quantity / (item.low_stock_threshold * 3)
    : 1;
  if (ratio < 0.34) return "bg-amber-500";
  return "bg-green-500";
}

export function InventoryTable({ items }: { items: InventoryItem[] }) {
  if (items.length === 0) {
    return (
      <Card>
        <CardBody className="py-12 text-center text-sm text-gray-500">
          No stock records yet. Add an inventory item for an equipment unit to
          start tracking consumables.
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody className="p-0">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Equipment</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Stock level</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">In stock</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Threshold</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {item.equipment_name}
                    {!item.track_inventory && (
                      <span className="ml-2 text-xs text-gray-400">(untracked)</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-40 overflow-hidden rounded-full bg-gray-200">
                        <div
                          className={`h-full ${stockColor(item)}`}
                          style={{
                            width: `${
                              item.low_stock_threshold
                                ? Math.min(
                                    100,
                                    (item.stock_quantity /
                                      (item.low_stock_threshold * 3)) *
                                      100,
                                  )
                                : item.is_low_stock
                                  ? 10
                                  : 100
                            }%`,
                          }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">
                        min {item.low_stock_threshold}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-900">
                    {item.stock_quantity}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-600">
                    {item.low_stock_threshold}
                  </td>
                  <td className="px-4 py-3">
                    {item.is_low_stock ? (
                      <Badge variant="danger">Low stock</Badge>
                    ) : (
                      <Badge variant="success">OK</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardBody>
    </Card>
  );
}