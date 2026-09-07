"use client";

import { useState } from "react";
import { resolveMediaUrl } from "@/lib/api";
import type { Customer } from "@/types/customer";

/** Best display name for a customer: backend `name`, legacy parts, then email. */
export function getCustomerDisplayName(customer: {
  name?: string;
  email: string;
  first_name?: string;
  last_name?: string;
}): string {
  const fromName = (customer.name ?? "").trim();
  if (fromName) return fromName;
  const fromParts = `${customer.first_name ?? ""} ${customer.last_name ?? ""}`.trim();
  return fromParts || customer.email;
}

/** Up to two leading initials from a display name (falls back to "?"). */
export function getCustomerInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return parts
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

const SIZES = {
  sm: "h-9 w-9 text-xs",
  md: "h-12 w-12 text-sm",
  lg: "h-16 w-16 text-base",
} as const;

export type CustomerAvatarSize = keyof typeof SIZES;

interface CustomerAvatarProps {
  customer: Pick<Customer, "name" | "email" | "profile_photo" | "first_name" | "last_name">;
  size?: CustomerAvatarSize;
  className?: string;
}

/**
 * Circular customer photo with an initials fallback.
 *
 * A broken or missing photo URL degrades to initials instead of rendering
 * a broken-image glyph.
 */
export function CustomerAvatar({ customer, size = "md", className = "" }: CustomerAvatarProps) {
  const [broken, setBroken] = useState(false);
  const url = resolveMediaUrl(customer.profile_photo);
  const showPhoto = url !== null && !broken;
  const initials = getCustomerInitials(getCustomerDisplayName(customer));

  return (
    <span
      aria-hidden="true"
      className={`flex flex-shrink-0 select-none items-center justify-center overflow-hidden rounded-full bg-brand-100 font-semibold text-brand-700 ${SIZES[size]} ${className}`}
    >
      {showPhoto ? (
        // eslint-disable-next-line @next/next/no-img-element -- backend serves an arbitrary media URL, not a Next-optimised asset
        <img
          src={url}
          alt=""
          className="h-full w-full object-cover"
          onError={() => setBroken(true)}
          data-testid="customer-avatar-photo"
        />
      ) : (
        initials
      )}
    </span>
  );
}
