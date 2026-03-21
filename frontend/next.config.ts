import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  // Standalone output bundles everything needed to run inside Docker without
  // node_modules being present in the runtime image.
  output: "standalone",

  reactStrictMode: true,
};

export default withNextIntl(nextConfig);
