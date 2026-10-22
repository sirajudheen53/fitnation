/**
 * Shared trainer display helpers (issue #53).
 */
import { resolveMediaUrl } from "@/lib/api";
import type { Trainer, TrainerCertification } from "@/types/trainer";

/** "4.56" → "4.6"; invalid → em dash. */
export function formatRating(rating: number | string | null | undefined): string {
  if (rating === null || rating === undefined) return "—";
  const r = Number(rating);
  if (Number.isNaN(r)) return "—";
  return r.toFixed(1);
}

export function trainerName(trainer: Trainer): string {
  return `${trainer.first_name} ${trainer.last_name}`.trim() || trainer.email;
}

export function trainerInitials(trainer: Trainer): string {
  const first = trainer.first_name.charAt(0);
  const last = trainer.last_name.charAt(0);
  const initials = `${first}${last}`.trim();
  return initials || "?";
}

/** Certification entries may be plain strings or {name, issuer, year} objects. */
export function certificationLabel(cert: TrainerCertification): string {
  if (typeof cert === "string") return cert;
  const parts = [cert.name, cert.issuer, cert.year].filter(Boolean).map(String);
  return parts.join(" — ") || "Certification";
}

/** Absolute URL for the trainer photo (empty profile_photo → null). */
export function resolveTrainerPhoto(trainer: Trainer): string | null {
  return resolveMediaUrl(trainer.profile_photo || null);
}
