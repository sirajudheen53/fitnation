"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { TrainerCard } from "@/features/trainers/components/TrainerCard";
import { Button, Alert, Spinner } from "@/components/ui";
import { fetchTrainers, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Trainer } from "@/types/trainer";

export default function TrainersPage() {
  const router = useRouter();
  const [trainers, setTrainers] = useState<Trainer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/trainers")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/trainers");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const res = await fetchTrainers(authToken);
        setTrainers(res.results);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const canCreate = userRole ? canAccessRoute(userRole, "/trainers") : false;

  return (
    <DashboardLayout
      title="Trainers"
      actions={
        canCreate ? (
          <Link href="/trainers">
            <Button size="sm">
              <Plus className="h-4 w-4" /> New trainer
            </Button>
          </Link>
        ) : null
      }
    >
      {error && <Alert variant="error">{error}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && trainers.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
          <p className="text-sm text-gray-500">No trainers yet.</p>
        </div>
      )}
      {!loading && trainers.length > 0 && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {trainers.map((trainer) => (
            <TrainerCard key={trainer.id} trainer={trainer} />
          ))}
        </div>
      )}
    </DashboardLayout>
  );
}
