import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Smartphone } from "lucide-react";

// Same shape the mobile deep-link parser accepts
// (mobile/lib/core/deeplink/join_link.dart): 8-4-4-4-12 hex.
const INVITE_UUID =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

const PLAY_PACKAGE = "com.getfitwithus.app";

export const metadata: Metadata = {
  title: "Join your gym on FitNation",
  description:
    "You've been invited to join your gym on FitNation. Open this invite on your phone.",
  robots: { index: false, follow: false },
};

export default async function InviteLandingPage({
  params,
}: {
  params: Promise<{ uuid: string }>;
}) {
  const { uuid } = await params;
  if (!INVITE_UUID.test(uuid)) notFound();

  return (
    <InviteLanding
      appLink={`fitnation://g/${uuid}`}
      playLink={`https://play.google.com/store/apps/details?id=${PLAY_PACKAGE}&referrer=gym%3D${uuid}`}
    />
  );
}

function InviteLanding({
  appLink,
  playLink,
}: {
  appLink: string;
  playLink: string;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-white">
      <main className="w-full max-w-md px-4 py-12 text-center">
        <div className="mx-auto mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
          <Smartphone className="h-6 w-6" />
        </div>

        <h1 className="text-3xl font-bold text-gray-900">
          You&apos;ve been invited to join your gym on FitNation
        </h1>
        <p className="mt-4 text-gray-600">
          Your gym runs your workouts, diet plan and check-ins on FitNation.
          Open this invite in the app to accept it.
        </p>

        <div className="mt-8 space-y-3">
          <a
            href={appLink}
            className="block rounded-xl bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700"
          >
            Open App
          </a>
          <a
            href={playLink}
            className="block rounded-xl border border-gray-300 px-4 py-3 font-medium text-gray-900 hover:bg-gray-50"
          >
            Get it on Google Play
          </a>
        </div>

        <p className="mt-8 text-sm text-gray-500">
          On a computer? Open this invite on your phone — the Google Play link
          above installs the app and carries your gym invite with it, so start
          right where you should.
        </p>
      </main>
    </div>
  );
}