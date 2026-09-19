"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { EquipmentTable } from "@/features/inventory/components/EquipmentTable";
import { InventoryTable } from "@/features/inventory/components/InventoryTable";
import { MaintenanceLogTable } from "@/features/inventory/components/MaintenanceLogTable";
import { Button, Input, Card, CardBody } from "@/components/ui";
import {
  createEquipment,
  createInventoryItem,
  createMaintenanceLog,
  deleteEquipment,
  errorMessage,
  fetchEquipment,
  fetchInventoryItems,
  fetchMaintenanceLogs,
  updateEquipment,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import {
  MAINTENANCE_STATUSES,
  MAINTENANCE_STATUS_LABELS,
  type Equipment,
  type EquipmentFormData,
  type InventoryItem,
  type InventoryItemFormData,
  type MaintenanceLog,
  type MaintenanceLogFormData,
} from "@/types/inventory";

type SectionKey = "equipment" | "stock" | "maintenance";

const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: "equipment", label: "Equipment" },
  { key: "stock", label: "Stock" },
  { key: "maintenance", label: "Maintenance" },
];

const emptyEquipment: EquipmentFormData = {
  name: "",
  description: "",
  serial_number: "",
  purchase_date: null,
};

export default function InventoryPage() {
  const router = useRouter();
  const [section, setSection] = useState<SectionKey>("equipment");

  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [stock, setStock] = useState<InventoryItem[]>([]);
  const [logs, setLogs] = useState<MaintenanceLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Equipment add/edit form
  const [showEquipmentForm, setShowEquipmentForm] = useState(false);
  const [editingEquipment, setEditingEquipment] = useState<Equipment | null>(null);
  const [equipmentForm, setEquipmentForm] = useState<EquipmentFormData>(emptyEquipment);
  const [savingEquipment, setSavingEquipment] = useState(false);

  // Stock add form
  const [showStockForm, setShowStockForm] = useState(false);
  const [stockForm, setStockForm] = useState<InventoryItemFormData>({
    equipment: 0,
    stock_quantity: 0,
    low_stock_threshold: 5,
    track_inventory: true,
  });
  const [savingStock, setSavingStock] = useState(false);

  // Maintenance add form
  const [showMaintenanceForm, setShowMaintenanceForm] = useState(false);
  const [maintenanceForm, setMaintenanceForm] = useState<MaintenanceLogFormData>({
    equipment: 0,
    performed_at: new Date().toISOString().slice(0, 16),
    description: "",
    status: "scheduled",
  });
  const [maintenanceEquipmentId, setMaintenanceEquipmentId] = useState<number | null>(null);
  const [savingMaintenance, setSavingMaintenance] = useState(false);

  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/inventory")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/inventory");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [eq, items, logs] = await Promise.all([
          fetchEquipment(authToken),
          fetchInventoryItems(authToken),
          fetchMaintenanceLogs(authToken),
        ]);
        setEquipment(eq);
        setStock(items);
        setLogs(logs);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [router, userRole]);

  /* ── Equipment actions ─────────────────────────────────────── */

  function openEquipmentForm(equipment?: Equipment) {
    if (equipment) {
      setEditingEquipment(equipment);
      setEquipmentForm({
        name: equipment.name,
        description: equipment.description,
        serial_number: equipment.serial_number,
        purchase_date: equipment.purchase_date,
      });
    } else {
      setEditingEquipment(null);
      setEquipmentForm(emptyEquipment);
    }
    setShowEquipmentForm(true);
  }

  async function saveEquipment() {
    if (!equipmentForm.name.trim()) {
      toast.error("Equipment name is required.");
      return;
    }
    const token = getToken();
    if (!token) return;
    setSavingEquipment(true);
    try {
      if (editingEquipment) {
        const updated = await updateEquipment(editingEquipment.id, equipmentForm, token);
        setEquipment((prev) =>
          prev.map((eq) => (eq.id === updated.id ? updated : eq)),
        );
        toast.success("Equipment updated");
      } else {
        const created = await createEquipment(equipmentForm, token);
        setEquipment((prev) => [...prev, created]);
        toast.success("Equipment added");
      }
      setShowEquipmentForm(false);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSavingEquipment(false);
    }
  }

  async function removeEquipment(eq: Equipment) {
    const token = getToken();
    if (!token) return;
    try {
      await deleteEquipment(eq.id, token);
      setEquipment((prev) => prev.filter((e) => e.id !== eq.id));
      setStock((prev) => prev.filter((s) => s.equipment !== eq.id));
      setLogs((prev) => prev.filter((l) => l.equipment !== eq.id));
      toast.success(`${eq.name} deleted`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  /* ── Stock actions ─────────────────────────────────────────── */

  async function saveStock() {
    if (!stockForm.equipment) {
      toast.error("Select an equipment unit.");
      return;
    }
    const token = getToken();
    if (!token) return;
    setSavingStock(true);
    try {
      const created = await createInventoryItem(stockForm, token);
      setStock((prev) => [...prev, created]);
      toast.success("Stock record added");
      setShowStockForm(false);
      setStockForm({
        equipment: 0,
        stock_quantity: 0,
        low_stock_threshold: 5,
        track_inventory: true,
      });
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSavingStock(false);
    }
  }

  /* ── Maintenance actions ───────────────────────────────────── */

  async function saveMaintenance() {
    if (!maintenanceForm.equipment || !maintenanceForm.description.trim()) {
      toast.error("Select equipment and describe the work.");
      return;
    }
    const token = getToken();
    if (!token) return;
    setSavingMaintenance(true);
    try {
      const created = await createMaintenanceLog(
        { ...maintenanceForm, performed_at: new Date(maintenanceForm.performed_at).toISOString() },
        token,
      );
      setLogs((prev) => [created, ...prev]);
      toast.success("Maintenance logged");
      setShowMaintenanceForm(false);
      setMaintenanceEquipmentId(null);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSavingMaintenance(false);
    }
  }

  /* ── Render ────────────────────────────────────────────────── */

  return (
    <DashboardLayout
      title="Equipment & Inventory"
      actions={
        section === "equipment" ? (
          <Button onClick={() => openEquipmentForm()}>
            <Plus className="mr-2 h-4 w-4" /> Add Equipment
          </Button>
        ) : section === "stock" ? (
          <Button onClick={() => setShowStockForm(true)}>
            <Plus className="mr-2 h-4 w-4" /> Add Stock Record
          </Button>
        ) : (
          <Button
            onClick={() => {
              setMaintenanceForm((f) => ({ ...f, equipment: 0 }));
              setShowMaintenanceForm(true);
            }}
          >
            <Plus className="mr-2 h-4 w-4" /> Log Maintenance
          </Button>
        )
      }
    >
      {error && (
        <Card className="mb-4">
          <CardBody className="text-sm text-red-600">{error}</CardBody>
        </Card>
      )}

      {/* Section tabs */}
      <div className="mb-4 flex gap-1 border-b border-gray-200">
        {SECTIONS.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setSection(s.key)}
            className={`border-b-2 px-3 py-2.5 text-sm font-medium transition-colors ${
              section === s.key
                ? "border-brand-600 text-brand-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {section === "equipment" && (
        <EquipmentTable
          equipment={equipment}
          loading={loading}
          onEdit={openEquipmentForm}
          onDelete={removeEquipment}
          onViewMaintenance={(eq) => {
            setMaintenanceEquipmentId(eq.id);
            setSection("maintenance");
          }}
        />
      )}

      {section === "stock" &&
        (loading ? (
          <div className="flex justify-center py-12 text-sm text-gray-500">Loading…</div>
        ) : (
          <InventoryTable items={stock} />
        ))}

      {section === "maintenance" &&
        (loading ? (
          <div className="flex justify-center py-12 text-sm text-gray-500">Loading…</div>
        ) : (
          <>
            {maintenanceEquipmentId !== null && !showMaintenanceForm && (
              <div className="mb-3 flex items-center justify-between rounded-lg bg-gray-50 px-4 py-2 text-sm text-gray-600">
                Filtered to one equipment — showing all logs.
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMaintenanceEquipmentId(null)}
                >
                  Clear
                </Button>
              </div>
            )}
            <MaintenanceLogTable
              logs={
                maintenanceEquipmentId
                  ? logs.filter((l) => l.equipment === maintenanceEquipmentId)
                  : logs
              }
            />
          </>
        ))}

      {/* Equipment add/edit dialog */}
      {showEquipmentForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-lg">
            <CardBody className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-gray-900">
                  {editingEquipment ? "Edit Equipment" : "Add Equipment"}
                </h3>
                <Button variant="ghost" size="sm" onClick={() => setShowEquipmentForm(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <Input
                label="Name"
                value={equipmentForm.name}
                onChange={(e) => setEquipmentForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Treadmill Pro"
              />
              <Input
                label="Serial number"
                value={equipmentForm.serial_number}
                onChange={(e) =>
                  setEquipmentForm((f) => ({ ...f, serial_number: e.target.value }))
                }
                placeholder="TM-2041"
              />
              <Input
                label="Purchase date"
                type="date"
                value={equipmentForm.purchase_date ?? ""}
                onChange={(e) =>
                  setEquipmentForm((f) => ({
                    ...f,
                    purchase_date: e.target.value || null,
                  }))
                }
              />
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">Description</label>
                <textarea
                  className="block w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  rows={3}
                  value={equipmentForm.description}
                  onChange={(e) =>
                    setEquipmentForm((f) => ({ ...f, description: e.target.value }))
                  }
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowEquipmentForm(false)}>
                  Cancel
                </Button>
                <Button onClick={saveEquipment} disabled={savingEquipment}>
                  {savingEquipment ? "Saving…" : editingEquipment ? "Save Changes" : "Add Equipment"}
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      )}

      {/* Stock add dialog */}
      {showStockForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-md">
            <CardBody className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-gray-900">Add Stock Record</h3>
                <Button variant="ghost" size="sm" onClick={() => setShowStockForm(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">Equipment</label>
                <select
                  className="block w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  value={stockForm.equipment || ""}
                  onChange={(e) =>
                    setStockForm((f) => ({ ...f, equipment: Number(e.target.value) }))
                  }
                >
                  <option value="" disabled>
                    Select equipment…
                  </option>
                  {equipment.map((eq) => (
                    <option key={eq.id} value={eq.id}>
                      {eq.name}
                    </option>
                  ))}
                </select>
              </div>
              <Input
                label="Stock quantity"
                type="number"
                min={0}
                value={stockForm.stock_quantity}
                onChange={(e) =>
                  setStockForm((f) => ({ ...f, stock_quantity: Number(e.target.value) }))
                }
              />
              <Input
                label="Low stock threshold"
                type="number"
                min={0}
                value={stockForm.low_stock_threshold}
                onChange={(e) =>
                  setStockForm((f) => ({ ...f, low_stock_threshold: Number(e.target.value) }))
                }
              />
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={stockForm.track_inventory}
                  onChange={(e) =>
                    setStockForm((f) => ({ ...f, track_inventory: e.target.checked }))
                  }
                />
                Track inventory (warn below threshold)
              </label>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowStockForm(false)}>
                  Cancel
                </Button>
                <Button onClick={saveStock} disabled={savingStock}>
                  {savingStock ? "Saving…" : "Add Record"}
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      )}

      {/* Maintenance log dialog */}
      {showMaintenanceForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-md">
            <CardBody className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-gray-900">Log Maintenance</h3>
                <Button variant="ghost" size="sm" onClick={() => setShowMaintenanceForm(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">Equipment</label>
                <select
                  className="block w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  value={maintenanceForm.equipment || ""}
                  onChange={(e) =>
                    setMaintenanceForm((f) => ({ ...f, equipment: Number(e.target.value) }))
                  }
                >
                  <option value="" disabled>
                    Select equipment…
                  </option>
                  {equipment.map((eq) => (
                    <option key={eq.id} value={eq.id}>
                      {eq.name}
                    </option>
                  ))}
                </select>
              </div>
              <Input
                label="Performed at"
                type="datetime-local"
                value={maintenanceForm.performed_at}
                onChange={(e) =>
                  setMaintenanceForm((f) => ({ ...f, performed_at: e.target.value }))
                }
              />
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">Status</label>
                <select
                  className="block w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  value={maintenanceForm.status}
                  onChange={(e) =>
                    setMaintenanceForm((f) => ({
                      ...f,
                      status: e.target.value as MaintenanceLogFormData["status"],
                    }))
                  }
                >
                  {MAINTENANCE_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {MAINTENANCE_STATUS_LABELS[s]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">Description</label>
                <textarea
                  className="block w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  rows={3}
                  value={maintenanceForm.description}
                  onChange={(e) =>
                    setMaintenanceForm((f) => ({ ...f, description: e.target.value }))
                  }
                  placeholder="Replaced running belt, lubricated deck…"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowMaintenanceForm(false)}>
                  Cancel
                </Button>
                <Button onClick={saveMaintenance} disabled={savingMaintenance}>
                  {savingMaintenance ? "Saving…" : "Log Maintenance"}
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      )}
    </DashboardLayout>
  );
}