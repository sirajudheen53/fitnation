"use client";

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SpinnerProps {
  className?: string;
  size?: number;
}

export function Spinner({ className, size = 24 }: SpinnerProps) {
  return (
    <Loader2
      size={size}
      className={cn("animate-spin text-brand-600", className)}
      aria-label="Loading"
    />
  );
}
