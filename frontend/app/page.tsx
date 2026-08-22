import Link from "next/link";
import { Dumbbell, ArrowRight, CheckCircle2 } from "lucide-react";

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-brand-50 via-white to-brand-50 px-4">
      <div className="w-full max-w-2xl text-center">
        <div className="mb-6 flex justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-600 text-white">
            <Dumbbell className="h-8 w-8" />
          </div>
        </div>
        <h1 className="mb-3 text-4xl font-bold text-gray-900">FitNation FBOS</h1>
        <p className="mb-8 text-lg text-gray-500">
          The operating system for your fitness business. Manage branches, trainers,
          customers, memberships, and payments — all in one place.
        </p>

        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[
            "Multi-branch management",
            "Role-based access control",
            "Customer & membership tracking",
          ].map((feature) => (
            <div
              key={feature}
              className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-700"
            >
              <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-green-500" />
              {feature}
            </div>
          ))}
        </div>

        <Link
          href="/signup"
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-6 py-3 font-medium text-white transition-colors hover:bg-brand-700"
        >
          Get started
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}