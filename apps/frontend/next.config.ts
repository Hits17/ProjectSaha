import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  ...(process.env.SAHA_BUILD_ID ? {
    generateBuildId: async () => process.env.SAHA_BUILD_ID!,
    headers: async () => [{
      source: "/:path*",
      headers: [{ key: "X-Saha-Build", value: process.env.SAHA_BUILD_ID! }],
    }],
  } : {}),
};

export default nextConfig;
