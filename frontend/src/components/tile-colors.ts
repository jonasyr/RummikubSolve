import type { TileColor } from "../types/api";

// Static map — Tailwind JIT must see all class names in this file at build time.
export const TILE_BG_CLASSES: Record<TileColor, string> = {
  blue:   "bg-tile-blue text-white",
  red:    "bg-tile-red text-white",
  black:  "bg-tile-black text-white",
  yellow: "bg-tile-yellow text-gray-900",
};

export const JOKER_BG_CLASSES = "bg-gray-800 text-yellow-400";
export const PLACEHOLDER_BG_CLASSES = "bg-gray-300 text-gray-600";
