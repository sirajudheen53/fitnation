import type { Metadata } from "next";
import { Toaster } from "sonner";
import { Providers } from "@/lib/providers";
import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://dev.yougetfitwithus.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "FitNation FBOS",
  description: "Fitness Business Operating System — manage your gym, trainers, and customers",
  openGraph: {
    title: "FitNation — Fitness Business Operating System",
    description:
      "Manage your gym, trainers, and customers — workouts, diet plans, attendance and analytics in one platform.",
    url: SITE_URL,
    siteName: "FitNation",
    images: [
      {
        url: "/og/dashboard.jpg",
        width: 1200,
        height: 630,
        alt: "Training session at the gym",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "FitNation — Fitness Business Operating System",
    description:
      "Manage your gym, trainers, and customers — workouts, diet plans, attendance and analytics in one platform.",
    images: ["/og/dashboard.jpg"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <Providers>
          {children}
          <Toaster position="top-right" richColors closeButton />
        </Providers>
      </body>
    </html>
  );
}