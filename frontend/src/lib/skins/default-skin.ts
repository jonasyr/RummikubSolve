import type { CssSkinSpec, SkinManifest } from "./types";
import { createCssRenderer } from "./css-renderer";

// All class names must appear as complete string literals here for Tailwind JIT.
const defaultCssSpec: CssSkinSpec = {
  colors: {
    blue:   { bg: "bg-tile-blue",   fg: "text-white" },
    red:    { bg: "bg-tile-red",    fg: "text-white" },
    black:  { bg: "bg-tile-black",  fg: "text-white" },
    yellow: { bg: "bg-tile-yellow", fg: "text-gray-900" },
  },
  joker:       { bg: "bg-gray-800", fg: "text-yellow-400", symbol: "★" },
  placeholder: { bg: "bg-gray-300", fg: "text-gray-600" },
};

const defaultManifest: SkinManifest = {
  id: "default",
  version: "1.0.0",
  kind: "css",
  displayName: { en: "Default", de: "Standard" },
  description: { en: "Built-in CSS skin", de: "Eingebaute CSS-Skin" },
  thumbnail: "",
  css: defaultCssSpec,
};

export const defaultSkinRenderer = createCssRenderer(defaultManifest, defaultCssSpec);
