import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Lint/type checks run in CI (GitHub Actions). Skip them at build time
  // so deployment isn't blocked by style rules; keeps deploys fast and reliable.
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  },
};

export default nextConfig;
