"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, VenetianMask } from "lucide-react";
import { toast } from "sonner";
import {
  endImpersonationSession,
  getImpersonationSession,
  type ImpersonationSession,
} from "@/lib/auth";

function formatRemaining(expiresAt: string, now: number): string {
  const seconds = Math.max(0, Math.floor((new Date(expiresAt).getTime() - now) / 1000));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

/**
 * Persistent "you are impersonating" banner (issue #45).
 *
 * Rendered by DashboardLayout on every page so an impersonated session can
 * never be forgotten: it shows the owner, the gym, and a live countdown, and
 * offers one-click exit. When the 30-minute token expires, the session is
 * ended automatically and the admin is returned to the gyms dashboard.
 */
export function ImpersonationBanner() {
  const router = useRouter();
  const [session, setSession] = useState<ImpersonationSession | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    // One-time hydration-safe sync from localStorage: reading during render
    // (lazy useState init) would diverge from the server-rendered null.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSession(getImpersonationSession());
    const timer = setInterval(() => {
      setNow(Date.now());
      setSession(getImpersonationSession());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!session) return;
    if (new Date(session.expires_at).getTime() <= now) {
      // Token lifetime over — end the session and go back to the operator view.
      endImpersonationSession();
      // Clearing synchronously stops this effect from re-firing on every tick
      // while `session` still holds the stale value.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSession(null);
      toast.info("Impersonation session ended.");
      router.replace("/admin");
    }
  }, [session, now, router]);

  function exit() {
    const ended = endImpersonationSession();
    setSession(null);
    toast.success(
      ended ? `Exited ${ended.owner_email} — back to admin.` : "Impersonation ended.",
    );
    router.replace("/admin");
  }

  if (!session) return null;

  return (
    <div
      className="border-b border-amber-300 bg-amber-100 px-4 py-2.5 text-amber-900 sm:px-6"
      role="status"
      data-testid="impersonation-banner"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <VenetianMask className="h-4 w-4 shrink-0" aria-hidden />
          <span>
            You are impersonating{" "}
            <span className="font-semibold">{session.owner_email}</span> in{" "}
            <span className="font-semibold">{session.tenant_name}</span>. This session
            is audited and ends in{" "}
            <span className="font-mono tabular-nums">
              {formatRemaining(session.expires_at, now)}
            </span>
            .
          </span>
        </div>
        <button
          onClick={exit}
          className="flex items-center gap-1.5 rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-sm font-semibold text-amber-900 hover:bg-amber-50"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          Exit Impersonation
        </button>
      </div>
    </div>
  );
}
