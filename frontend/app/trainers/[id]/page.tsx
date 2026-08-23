"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Pencil, Star, TrendingUp, Users } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardHeader, CardBody, Badge, Spinner, Alert, Button } from "@/components/ui";
import { fetchTrainer, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Trainer } from "@/types/trainer";
import { formatRating, formatRevenue } from "@/features/trainers/components/TrainerCard";

export default function TrainerDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [trainer, setTrainer] = useState<Trainer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/trainers");
      return;
    }
    const authToken: string = token;
    async function load() {
      try {
        const data = await fetchTrainer(id, authToken);
        setTrainer(data);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  return (
    <DashboardLayout
      title="Trainer profile"
      actions={
        trainer ? (
          <Link href={`/trainers/${trainer.id}/edit`}>
            <Button size="sm" variant="outline">
              <Pencil className="h-4 w-4" /> Edit
            </Button>
          </Link>
        ) : null
      }
    >
      <div className="mb-4">
        <Link
          href="/trainers"
          className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" /> Back to trainers
        </Link>
      </div>

      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && error != null && !trainer && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && trainer && (
        <div className="space-y-6">
          <Card>
            <CardBody>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 text-xl font-semibold text-brand-700">
                    {trainer.first_name.charAt(0)}
                    {trainer.last_name.charAt(0)}
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-gray-900">
                      {trainer.first_name} {trainer.last_name}
                    </h2>
                    {trainer.specialization && (
                      <p className="text-sm text-gray-500">{trainer.specialization}</p>
                    )}
                    <div className="mt-1 flex items-center gap-2">
                      {trainer.is_active ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <Badge variant="danger">Inactive</Badge>
                      )}
                      <span className="text-sm text-gray-500">{trainer.email}</span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-6">
                  <div className="flex items-center gap-2">
                    <Star className="h-4 w-4 text-amber-500" />
                    <div>
                      <p className="text-lg font-semibold text-gray-900">
                        {formatRating(trainer.rating)}
                      </p>
                      <p className="text-xs text-gray-500">Rating</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-green-600" />
                    <div>
                      <p className="text-lg font-semibold text-gray-900">
                        {formatRevenue(trainer.revenue)}
                      </p>
                      <p className="text-xs text-gray-500">Revenue</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-brand-600" />
                    <div>
                      <p className="text-lg font-semibold text-gray-900">
                        {trainer.active_clients}
                      </p>
                      <p className="text-xs text-gray-500">Clients</p>
                    </div>
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <h3 className="text-lg font-semibold text-gray-900">Profile</h3>
              </CardHeader>
              <CardBody>
                <dl className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Phone</dt>
                    <dd className="text-gray-900">{trainer.phone ?? "—"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Experience</dt>
                    <dd className="text-gray-900">
                      {trainer.experience_years != null
                        ? `${trainer.experience_years} years`
                        : "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Branch</dt>
                    <dd className="text-gray-900">{trainer.branch_id ? `#${trainer.branch_id}` : "—"}</dd>
                  </div>
                  {trainer.bio && (
                    <div>
                      <dt className="mb-1 text-gray-500">Bio</dt>
                      <dd className="text-gray-700">{trainer.bio}</dd>
                    </div>
                  )}
                </dl>
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="text-lg font-semibold text-gray-900">Certifications</h3>
              </CardHeader>
              <CardBody>
                {trainer.certifications.length === 0 ? (
                  <p className="text-sm text-gray-500">No certifications listed.</p>
                ) : (
                  <ul className="space-y-2">
                    {trainer.certifications.map((cert, i) => (
                      <li
                        key={i}
                        className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-700"
                      >
                        {cert}
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
