"use client";

import { useTranslations } from "next-intl";
import type { TileColor, TileInput } from "../types/api";

const COLORS: TileColor[] = ["blue", "red", "black", "yellow"];
const NUMBERS = Array.from({ length: 13 }, (_, i) => i + 1);

// Static map — Tailwind JIT must see all class names at build time.
const TILE_BG: Record<TileColor, string> = {
  blue: "bg-tile-blue text-white",
  red: "bg-tile-red text-white",
  black: "bg-tile-black text-white",
  yellow: "bg-tile-yellow text-gray-900",
};

interface Props {
  onSelect: (tile: TileInput) => void;
  /** Returns how many copies of this tile are already selected. */
  tileCount?: (tile: TileInput) => number;
}

export default function TileGridPicker({ onSelect, tileCount }: Props) {
  const t = useTranslations("tilePicker");
  const count = (tile: TileInput) => tileCount?.(tile) ?? 0;

  return (
    <div className="w-full space-y-[2px]">
      {/* 4 rows × 13 columns — tiles scale to fill the available width */}
      {COLORS.map((color) => (
        <div
          key={color}
          className="grid gap-[2px]"
          style={{ gridTemplateColumns: "repeat(13, 1fr)" }}
        >
          {NUMBERS.map((n) => {
            const tile: TileInput = { color, number: n };
            const c = count(tile);
            const atMax = c >= 2;
            return (
              <button
                key={n}
                onClick={() => !atMax && onSelect(tile)}
                disabled={atMax}
                className={[
                  "relative w-full aspect-[5/6] rounded font-bold",
                  "flex items-center justify-center",
                  "border border-white/20 select-none",
                  TILE_BG[color],
                  atMax
                    ? "opacity-40 cursor-not-allowed"
                    : "cursor-pointer hover:brightness-110 active:scale-95 transition-transform",
                ].join(" ")}
                style={{ fontSize: "clamp(8px, 2vw, 13px)" }}
                aria-label={
                  atMax
                    ? t("ariaMax", { color, number: n })
                    : c > 0
                      ? t("ariaSelected", { color, number: n, count: c })
                      : t("ariaLabel", { color, number: n })
                }
              >
                {n}
                {c > 0 && (
                  <span className="absolute bottom-0 right-0 w-3 h-3 rounded-tl bg-black/70 text-white text-[7px] flex items-center justify-center leading-none pointer-events-none">
                    {c}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      ))}

      {/* Joker button */}
      <div className="pt-1">
        {(() => {
          const jokerTile: TileInput = { joker: true };
          const c = count(jokerTile);
          const atMax = c >= 2;
          return (
            <button
              onClick={() => !atMax && onSelect(jokerTile)}
              disabled={atMax}
              className={[
                "relative px-3 py-1.5 rounded font-bold text-sm",
                "bg-gray-800 text-yellow-400",
                "border border-white/20 select-none",
                atMax
                  ? "opacity-40 cursor-not-allowed"
                  : "cursor-pointer hover:brightness-110 active:scale-95 transition-transform",
              ].join(" ")}
              aria-label={
                atMax
                  ? t("jokerAriaMax")
                  : c > 0
                    ? t("jokerAriaSelected", { count: c })
                    : t("jokerAria")
              }
            >
              ★ {t("joker")}
              {c > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-black/70 text-white text-[8px] flex items-center justify-center leading-none pointer-events-none">
                  {c}
                </span>
              )}
            </button>
          );
        })()}
      </div>
    </div>
  );
}
