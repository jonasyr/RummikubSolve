"use client";

import { useTranslations } from "next-intl";
import type { TileColor } from "../types/api";
import { TILE_BG_CLASSES, JOKER_BG_CLASSES, PLACEHOLDER_BG_CLASSES } from "./tile-colors";

interface TileProps {
  color?: TileColor | null;
  number?: number | null;
  isJoker?: boolean;
  highlighted?: boolean;
  onRemove?: () => void;
  size?: "xs" | "sm" | "md";
  label?: string;
  selected?: boolean;
  onClick?: () => void;
}

export default function Tile({
  color,
  number,
  isJoker = false,
  highlighted = false,
  onRemove,
  size = "md",
  label,
  selected = false,
  onClick,
}: TileProps) {
  const t = useTranslations("tile");

  const sizeClass =
    size === "xs"
      ? "w-5 h-6 text-[10px]"
      : size === "sm"
        ? "w-7 h-8 text-xs"
        : "w-9 h-10 text-sm";

  const bgClass = isJoker
    ? JOKER_BG_CLASSES
    : color
      ? TILE_BG_CLASSES[color]
      : PLACEHOLDER_BG_CLASSES;

  // selected (blue) takes visual precedence over highlighted (yellow)
  const ringCls = selected
    ? "ring-2 ring-blue-400 ring-offset-1"
    : highlighted
      ? "ring-2 ring-yellow-300 ring-offset-1"
      : "";

  const classes = [
    sizeClass,
    bgClass,
    "rounded font-bold flex items-center justify-center border border-white/20 select-none",
    ringCls,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={`relative inline-block${onClick ? " cursor-pointer" : ""}`}
      onClick={onClick}
    >
      <div
        className={classes}
        data-skin-kind="css"
        data-tile-color={isJoker ? undefined : (color ?? undefined)}
        data-tile-joker={isJoker ? "true" : undefined}
      >
        {isJoker ? "★" : (number ?? "?")}
      </div>
      {label && (
        <div className="text-center mt-0.5">
          <span className="text-[8px] font-medium leading-none px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 whitespace-nowrap">
            {label}
          </span>
        </div>
      )}
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
