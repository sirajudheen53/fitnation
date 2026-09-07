import type { Metadata } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://dev.yougetfitwithus.com";

export const metadata: Metadata = {
  title: "FitNation — Gym Dashboard",
  description:
    "Track members, revenue, attendance and trainers in real time — the FitNation gym dashboard.",
  openGraph: {
    title: "FitNation — Gym Dashboard",
    description:
      "Track members, revenue, attendance and trainers in real time — the FitNation gym dashboard.",
    url: `${SITE_URL}/dashboard`,
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
    title: "FitNation — Gym Dashboard",
    description:
      "Track members, revenue, attendance and trainers in real time — the FitNation gym dashboard.",
    images: ["/og/dashboard.jpg"],
  },
};

export default function DashboardLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}