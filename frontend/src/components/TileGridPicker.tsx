"use client";

import type { TileColor, TileInput } from "../types/api";
import Tile from "./Tile";

const COLORS: TileColor[] = ["blue", "red", "black", "yellow"];
const NUMBERS = Array.from({ length: 13 }, (_, i) => i + 1);

interface Props {
  onSelect: (tile: TileInput) => void;
}

export default function TileGridPicker({ onSelect }: Props) {
  return (
    <div className="overflow-x-auto">
      <div className="inline-block">
        {COLORS.map((color) => (
          <div key={color} className="flex gap-1 mb-1">
            {NUMBERS.map((n) => (
              <button
                key={n}
                onClick={() => onSelect({ color, number: n })}
                className="p-0 border-0 bg-transparent cursor-pointer hover:scale-110 active:scale-95 transition-transform"
                aria-label={`${color} ${n}`}
              >
                <Tile color={color} number={n} size="sm" />
              </button>
            ))}
          </div>
        ))}
        <div className="mt-1">
          <button
            onClick={() => onSelect({ joker: true })}
            className="p-0 border-0 bg-transparent cursor-pointer hover:scale-110 active:scale-95 transition-transform"
            aria-label="Joker"
          >
            <Tile isJoker size="sm" />
          </button>
        </div>
      </div>
    </div>
  );
}
