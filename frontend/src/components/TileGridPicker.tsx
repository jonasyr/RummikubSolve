"use client";

import type { TileColor, TileInput } from "../types/api";
import Tile from "./Tile";

const COLORS: TileColor[] = ["blue", "red", "black", "yellow"];
const NUMBERS = Array.from({ length: 13 }, (_, i) => i + 1);

interface Props {
  onSelect: (tile: TileInput) => void;
  /** Returns how many copies of this tile are already in the rack. */
  tileCount?: (tile: TileInput) => number;
}

export default function TileGridPicker({ onSelect, tileCount }: Props) {
  const count = (tile: TileInput) => tileCount?.(tile) ?? 0;

  return (
    <div className="overflow-x-auto">
      <div className="inline-block">
        {COLORS.map((color) => (
          <div key={color} className="flex gap-[2px] mb-[2px]">
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
                    "relative p-0 border-0 bg-transparent transition-transform",
                    atMax
                      ? "opacity-40 cursor-not-allowed"
                      : "cursor-pointer hover:scale-110 active:scale-95",
                  ].join(" ")}
                  aria-label={`${color} ${n}${atMax ? " (max 2)" : c > 0 ? ` (${c} in rack)` : ""}`}
                >
                  <Tile color={color} number={n} size="xs" />
                  {c > 0 && (
                    <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-black/70 text-white text-[8px] flex items-center justify-center leading-none pointer-events-none">
                      {c}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
        <div className="mt-1">
          {(() => {
            const jokerTile: TileInput = { joker: true };
            const c = count(jokerTile);
            const atMax = c >= 2;
            return (
              <button
                onClick={() => !atMax && onSelect(jokerTile)}
                disabled={atMax}
                className={[
                  "relative p-0 border-0 bg-transparent transition-transform",
                  atMax
                    ? "opacity-40 cursor-not-allowed"
                    : "cursor-pointer hover:scale-110 active:scale-95",
                ].join(" ")}
                aria-label={`Joker${atMax ? " (max 2)" : c > 0 ? ` (${c} in rack)` : ""}`}
              >
                <Tile isJoker size="xs" />
                {c > 0 && (
                  <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-black/70 text-white text-[8px] flex items-center justify-center leading-none pointer-events-none">
                    {c}
                  </span>
                )}
              </button>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
