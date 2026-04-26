import type { CssSkinSpec, SkinManifest } from "./types";
import { createCssRenderer } from "./css-renderer";

// All class names must appear as complete string literals here for Tailwind JIT.
const highContrastCssSpec: CssSkinSpec = {
  colors: {
    blue:   { bg: "bg-blue-600",   fg: "text-white" },
    red:    { bg: "bg-red-600",    fg: "text-white" },
    black:  { bg: "bg-black",      fg: "text-white" },
    yellow: { bg: "bg-yellow-300", fg: "text-black" },
  },
  joker:       { bg: "bg-white",    fg: "text-black",     symbol: "★" },
  placeholder: { bg: "bg-gray-200", fg: "text-gray-800" },
};

const highContrastManifest: SkinManifest = {
  id: "high-contrast",
  version: "1.0.0",
  kind: "css",
  displayName: { en: "High Contrast", de: "Hoher Kontrast" },
  description: {
    en: "High contrast CSS skin for accessibility",
    de: "Hoher-Kontrast-CSS-Skin für Barrierefreiheit",
  },
  thumbnail: "",
  css: highContrastCssSpec,
};

export const highContrastSkinRenderer = createCssRenderer(
  highContrastManifest,
  highContrastCssSpec,
);
