import type { Metadata } from "next";
import Link from "next/link";
import { Trash2, ShieldCheck, Mail, ArrowLeft, Dumbbell, CheckCircle2, FileText } from "lucide-react";

export const metadata: Metadata = {
  title: "Delete your account — FitNation",
  description:
    "How to permanently delete your FitNation member account — what is erased, what is kept for legal reasons, and who to contact.",
};

const SUPPORT_EMAIL = "support@yougetfitwithus.com";

const erased = [
  "Your health profile, body measurements and measurement history",
  "Your progress photos",
  "Your workout and diet logs, class bookings and trainer chat",
  "Your name, phone number and email — your identity is erased so nothing left behind can be linked back to you",
  "Your sign-in sessions: you are logged out on every device",
];


export default function DataDeletionPage() {
  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:py-16">
        <header className="mb-10">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white">
              <Trash2 className="h-5 w-5" />
            </div>
            <h1 className="text-3xl font-bold text-gray-900">Delete your account</h1>
          </div>
          <p className="text-gray-600">
            You can permanently delete your FitNation account and everything in
            it. Deletion is permanent and cannot be undone.
          </p>
        </header>

        <section className="mb-10">
          <h2 className="mb-4 text-xl font-semibold text-gray-900">How to delete</h2>
          <ol className="space-y-4">
            {[
              {
                title: "1. Request deletion",
                body:
                  "Ask at your gym's front desk, or request it in the app from your profile. If you cannot reach your gym, write to us.",
              },
              {
                title: "2. Your gym confirms",
                body:
                  "A staff member of your gym verifies the request. This protects your account from being deleted by someone else.",
              },
              {
                title: "3. FitNation erases your data",
                body:
                  "Once confirmed, your account is permanently deleted from FitNation's servers — not just deactivated.",
              },
            ].map((step) => (
              <li
                key={step.title}
                className="rounded-lg border border-gray-200 bg-gray-50 p-4"
              >
                <p className="font-medium text-gray-900">{step.title}</p>
                <p className="mt-1 text-sm leading-relaxed text-gray-600">
                  {step.body}
                </p>
              </li>
            ))}
          </ol>
        </section>

        <section className="mb-10">
          <h2 className="mb-3 text-xl font-semibold text-gray-900">What is removed</h2>
          <ul className="space-y-2">
            {erased.map((item) => (
              <li key={item} className="flex items-start gap-2 text-gray-600">
                <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand-600" />
                {item}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-gray-600">
            Before deleting your whole account, you can also delete individual
            entries — a measurement or a progress photo — yourself in the app,
            from the Progress screen.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-gray-900">
            <FileText className="h-5 w-5 text-brand-600" />
            What we must keep
          </h2>
          <p className="text-gray-600">
            Gym business records — memberships, payments, invoices, and
            attendance entries — are retained for statutory and financial
            reasons, as the law requires. After your deletion these records no
            longer contain your identity — they cannot be linked back to you.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-gray-900">
            <ShieldCheck className="h-5 w-5 text-brand-600" />
            Your data in the meantime
          </h2>
          <p className="text-gray-600">
            Everything the app collects, why, and how it is protected is
            described in our{" "}
            <Link
              href="/privacy"
              className="font-medium text-brand-600 hover:text-brand-700"
            >
              Privacy Policy
            </Link>
            .
          </p>
        </section>

        <section className="mb-4">
          <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-gray-900">
            <Mail className="h-5 w-5 text-brand-600" />
            Contact
          </h2>
          <p className="text-gray-600">
            Deletion requests and questions:{" "}
            <a
              href={`mailto:${SUPPORT_EMAIL}`}
              className="font-medium text-brand-600 hover:text-brand-700"
            >
              {SUPPORT_EMAIL}
            </a>
          </p>
        </section>

        <footer className="mt-12 border-t border-gray-200 pt-6 text-sm text-gray-500">
          <Link
            href="/"
            className="inline-flex items-center gap-2 font-medium text-brand-600 hover:text-brand-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to FitNation
          </Link>
          <p className="mt-3 flex items-center gap-2">
            <Dumbbell className="h-4 w-4" />
            FitNation — the official member app of your gym.
          </p>
        </footer>
      </div>
    </div>
  );
}