"use client";

import { useRef } from "react";
import { Camera, X } from "lucide-react";
import { resolveMediaUrl } from "@/lib/api";

/** Allowed profile photo types - mirrors the backend serializer validation. */
export const ALLOWED_PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;

/** 5 MB, matching the backend limit for profile_photo uploads. */
export const MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024;

/**
 * Validate a selected profile photo client-side.
 * Returns an inline error message, or null when the file is acceptable.
 */
export function validateProfilePhoto(file: File): string | null {
  if (!ALLOWED_PHOTO_TYPES.includes(file.type as (typeof ALLOWED_PHOTO_TYPES)[number])) {
    return "Please choose a JPEG, PNG, or WebP image.";
  }
  if (file.size > MAX_PHOTO_SIZE_BYTES) {
    return "Photo must be 5 MB or smaller.";
  }
  return null;
}

/** Local preview URL for a selected File (empty string when unavailable). */
function previewUrlFor(file: File | null): string {
  if (!file) return "";
  try {
    return URL.createObjectURL(file);
  } catch {
    return "";
  }
}

interface ProfilePhotoPickerProps {
  /** Resolved URL of the customer's current photo (edit mode), if any. */
  existingPhotoUrl?: string | null;
  /** Newly selected file (parent state). */
  file: File | null;
  /** True when the user explicitly removed the existing photo. */
  removed?: boolean;
  /** Inline error message from failed validation. */
  error?: string | null;
  onChange: (file: File | null) => void;
  onRemove: () => void;
  disabled?: boolean;
}

/**
 * Circular profile photo picker for the customer form.
 *
 * Click the avatar to choose a file; a preview replaces the camera
 * placeholder; the X button removes the selection (or the existing photo
 * on edit). Validation errors render inline below the avatar.
 */
export function ProfilePhotoPicker({
  existingPhotoUrl,
  file,
  removed = false,
  error = null,
  onChange,
  onRemove,
  disabled = false,
}: ProfilePhotoPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const previewUrl = previewUrlFor(file);
  const photoUrl = previewUrl || (removed ? null : existingPhotoUrl ?? null);
  const hasPhoto = photoUrl !== null && photoUrl !== "";

  return (
    <div>
      <div className="flex items-center gap-3">
        <div className="relative">
          <button
            type="button"
            aria-label={hasPhoto ? "Change profile photo" : "Upload profile photo"}
            className="group relative flex h-20 w-20 cursor-pointer items-center justify-center overflow-hidden rounded-full border-2 border-dashed border-gray-300 bg-gray-50 transition-colors hover:border-brand-500 hover:bg-brand-50"
            onClick={() => inputRef.current?.click()}
          >
            {hasPhoto ? (
              // eslint-disable-next-line @next/next/no-img-element -- user-selected/local preview, not a Next-optimised asset
              <img src={photoUrl} alt="Profile photo preview" className="h-full w-full object-cover" />
            ) : (
              <Camera className="h-6 w-6 text-gray-400" aria-hidden="true" />
            )}
          </button>
          {hasPhoto && (
            <button
              type="button"
              aria-label="Remove profile photo"
              className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-full bg-gray-700 text-white shadow-sm transition-colors hover:bg-red-600"
              onClick={onRemove}
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
        <div className="text-sm">
          <p className="font-medium text-gray-700">Profile photo</p>
          <p className="text-gray-500">JPEG, PNG, or WebP - up to 5 MB</p>
          {error && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {error}
            </p>
          )}
        </div>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={ALLOWED_PHOTO_TYPES.join(",")}
        className="hidden"
        aria-label="Profile photo file"
        disabled={disabled}
        onChange={(e) => {
          const selected = e.target.files?.[0] ?? null;
          onChange(selected);
          // Allow re-selecting the same file after a remove.
          e.target.value = "";
        }}
      />
    </div>
  );
}
