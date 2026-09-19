"use client";

import { Pencil, Trash2, Wrench } from "lucide-react";
import { Badge, Button, Card, CardBody, Spinner } from "@/components/ui";
import { formatAccessTimestamp } from "@/types/access";
import type { Equipment } from "@/types/inventory";

interface EquipmentTableProps {
  equipment: Equipment[];
  loading: boolean;
  onEdit: (equipment: Equipment) => void;
  onDelete: (equipment: Equipment) => void;
  onViewMaintenance: (equipment: Equipment) => void;
}

export function EquipmentTable({
  equipment,
  loading,
  onEdit,
  onDelete,
  onViewMaintenance,
}: EquipmentTableProps) {
  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (equipment.length === 0) {
    return (
      <Card>
        <CardBody className="py-12 text-center text-sm text-gray-500">
          No equipment registered yet. Add your first machine to start
          tracking stock and maintenance.
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
                <th className="px-4 py-3 text-left font-medium text-gray-500">Name</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Serial No.</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Purchased</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Added</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {equipment.map((eq) => (
                <tr key={eq.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{eq.name}</div>
                    {eq.description && (
                      <div className="mt-0.5 max-w-md truncate text-xs text-gray-500">
                        {eq.description}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">
                    {eq.serial_number || <span className="text-gray-400">—</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {eq.purchase_date || <span className="text-gray-400">—</span>}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {formatAccessTimestamp(eq.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onViewMaintenance(eq)}
                        aria-label={`Maintenance for ${eq.name}`}
                      >
                        <Wrench className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onEdit(eq)}
                        aria-label={`Edit ${eq.name}`}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDelete(eq)}
                        aria-label={`Delete ${eq.name}`}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
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