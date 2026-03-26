import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { version } = require("./package.json") as { version: string };

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  // Standalone output bundles everything needed to run inside Docker without
  // node_modules being present in the runtime image.
  output: "standalone",

  reactStrictMode: true,

  env: {
    NEXT_PUBLIC_APP_VERSION: version,
  },
};

export default withNextIntl(nextConfig);
