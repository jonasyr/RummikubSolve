import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Output standalone build for Docker
  // output: "standalone",  // Uncomment when deploying via Docker

  // Strict React mode
  reactStrictMode: true,
};

export default nextConfig;
