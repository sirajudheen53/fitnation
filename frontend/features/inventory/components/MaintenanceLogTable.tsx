"use client";

import { MaintenanceLog } from "@/types/inventory";
import { MAINTENANCE_STATUS_LABELS } from "@/types/inventory";
import { formatAccessTimestamp } from "@/types/access";
import { Badge, Card, CardBody } from "@/components/ui";

const STATUS_VARIANTS: Record<string, "success" | "warning" | "default"> = {
  completed: "success",
  scheduled: "warning",
  cancelled: "default",
};

export function MaintenanceLogTable({ logs }: { logs: MaintenanceLog[] }) {
  if (logs.length === 0) {
    return (
      <Card>
        <CardBody className="py-12 text-center text-sm text-gray-500">
          No maintenance logs yet. Log a service visit to keep the equipment
          history.
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
                <th className="px-4 py-3 text-left font-medium text-gray-500">Performed at</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Description</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {log.equipment_name}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-600">
                    {formatAccessTimestamp(log.performed_at)}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{log.description}</td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_VARIANTS[log.status] ?? "default"}>
                      {MAINTENANCE_STATUS_LABELS[log.status] ?? log.status}
                    </Badge>
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