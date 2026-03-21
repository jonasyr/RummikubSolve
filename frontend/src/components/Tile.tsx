"use client";

import { useTranslations } from "next-intl";
import type { TileColor } from "../types/api";

interface TileProps {
  color?: TileColor | null;
  number?: number | null;
  isJoker?: boolean;
  highlighted?: boolean;
  onRemove?: () => void;
  size?: "xs" | "sm" | "md";
}

// Static map so Tailwind JIT can detect all class names at build time.
const BG: Record<TileColor, string> = {
  blue: "bg-tile-blue text-white",
  red: "bg-tile-red text-white",
  black: "bg-tile-black text-white",
  yellow: "bg-tile-yellow text-gray-900",
};

export default function Tile({
  color,
  number,
  isJoker = false,
  highlighted = false,
  onRemove,
  size = "md",
}: TileProps) {
  const t = useTranslations("tile");

  const sizeClass =
    size === "xs"
      ? "w-5 h-6 text-[10px]"
      : size === "sm"
        ? "w-7 h-8 text-xs"
        : "w-9 h-10 text-sm";

  const bgClass = isJoker
    ? "bg-gray-800 text-yellow-400"
    : color
      ? BG[color]
      : "bg-gray-300 text-gray-600";

  const classes = [
    sizeClass,
    bgClass,
    "rounded font-bold flex items-center justify-center border border-white/20 select-none",
    highlighted ? "ring-2 ring-yellow-300 ring-offset-1" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="relative inline-block">
      <div className={classes}>{isJoker ? "★" : (number ?? "?")}</div>
      {onRemove && (
        <button
          onClick={onRemove}
          className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white rounded-full text-xs flex items-center justify-center leading-none hover:bg-red-600 z-10"
          aria-label={t("removeLabel")}
        >
          ×
        </button>
      )}
    </div>
  );
}
