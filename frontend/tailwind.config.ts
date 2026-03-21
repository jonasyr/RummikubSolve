import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Rummikub tile colors — used throughout the app
      colors: {
        tile: {
          blue: "#1d4ed8",
          red: "#dc2626",
          black: "#1f2937",
          yellow: "#d97706",
        },
      },
    },
  },
  plugins: [],
};

export default config;
