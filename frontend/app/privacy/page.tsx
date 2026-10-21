import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck, Lock, Trash2, Mail } from "lucide-react";

export const metadata: Metadata = {
  title: "Privacy Policy — FitNation",
  description:
    "What the FitNation member app collects, why, how it is protected in transit, and how you can delete it.",
};

const SUPPORT_EMAIL = "support@yougetfitwithus.com";

const collected: { title: string; body: string }[] = [
  {
    title: "Your identity",
    body:
      "Your name and phone number, so your gym can sign you in with a one-time password (OTP) sent over WhatsApp or SMS — no passwords, ever. Email address is optional.",
  },
  {
    title: "Health profile & body measurements",
    body:
      "Height, weight, body measurement history with timestamps, fitness goals, and injury or medical notes your trainer must know about.",
  },
  {
    title: "Progress photos",
    body:
      "Body-progress photos you choose to attach to your progress records. They are private to you.",
  },
  {
    title: "Activity in your gym",
    body:
      "Workout and diet check-ins, class bookings, attendance records when you check in with your QR code, and chat messages between you and your gym's trainers.",
  },
  {
    title: "Device & technical data",
    body:
      "Your push-notification token (so your gym can remind you about booked classes) and a minimal offline cache of your own profile and in-flight uploads on the device.",
  },
];

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:py-16">
        <header className="mb-10">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h1 className="text-3xl font-bold text-gray-900">Privacy Policy</h1>
          </div>
          <p className="text-gray-600">
            FitNation is the official member app of your gym. This policy covers
            what the app collects, why, how it is protected, and how it can be
            deleted. Plain language, no legal fog.
          </p>
        </header>

        <section className="mb-10">
          <h2 className="mb-4 text-xl font-semibold text-gray-900">What we collect</h2>
          <dl className="space-y-4">
            {collected.map((item) => (
              <div
                key={item.title}
                className="rounded-lg border border-gray-200 bg-gray-50 p-4"
              >
                <dt className="font-medium text-gray-900">{item.title}</dt>
                <dd className="mt-1 text-sm leading-relaxed text-gray-600">
                  {item.body}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="mb-10">
          <h2 className="mb-3 text-xl font-semibold text-gray-900">Why we collect it</h2>
          <p className="text-gray-600">
            Only to run your gym membership: so your trainers can build your
            workouts and diet plan, your gym can manage attendance and classes,
            and you can see your own progress. Your data is never sold and never
            shared with advertisers, and it is not used for advertising.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="mb-3 text-xl font-semibold text-gray-900">
            Who can see your data
          </h2>
          <p className="text-gray-600">
            You, and the authorized staff of your own gym through their FitNation
            dashboards. Your data moves only between your phone and FitNation&apos;s
            servers — no ad networks, no data brokers. FitNation does not provide
            medical advice; your health entries exist so your gym can coach you.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-gray-900">
            <Lock className="h-5 w-5 text-brand-600" />
            How it is protected
          </h2>
          <p className="text-gray-600">
            Everything you log — measurements, progress photos, injuries — is
            transmitted over encrypted HTTPS (TLS 1.2 or newer). There is no
            plaintext fallback in release builds. On your phone the app keeps
            only a minimal offline cache, which you can clear by logging out or
            from your device&apos;s storage settings.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="mb-3 text-xl font-semibold text-gray-900">Retention</h2>
          <p className="text-gray-600">
            Your entries are kept while your membership is active so your history
            and trend lines remain available. You can delete individual entries —
            a measurement or a progress photo — yourself, in the app, at any
            time.
          </p>
        </section>

        <section className="mb-10">
          <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-gray-900">
            <Trash2 className="h-5 w-5 text-brand-600" />
            Deleting your account
          </h2>
          <p className="text-gray-600">
            You can have your whole account deleted — permanently.{" "}
            <Link
              href="/data-deletion"
              className="font-medium text-brand-600 hover:text-brand-700"
            >
              See how to delete your account
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
            Questions about this policy or your data? Write to{" "}
            <a
              href={`mailto:${SUPPORT_EMAIL}`}
              className="font-medium text-brand-600 hover:text-brand-700"
            >
              {SUPPORT_EMAIL}
            </a>
            , or ask at your gym&apos;s front desk.
          </p>
        </section>
      </div>
    </div>
  );
}