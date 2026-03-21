import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output bundles everything needed to run inside Docker without
  // node_modules being present in the runtime image.
  output: "standalone",

  reactStrictMode: true,
};

export default nextConfig;
