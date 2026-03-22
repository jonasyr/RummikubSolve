"use client";

import { useCallback } from "react";
import { useTranslations } from "next-intl";
import type { TileInput } from "../types/api";
import { useGameStore } from "../store/game";
import Tile from "./Tile";
import TileGridPicker from "./TileGridPicker";

export default function RackSection() {
  const t = useTranslations("rack");
  const rack = useGameStore((s) => s.rack);
  const boardSets = useGameStore((s) => s.boardSets);
  const addRackTile = useGameStore((s) => s.addRackTile);
  const removeRackTile = useGameStore((s) => s.removeRackTile);

  const tileCount = useCallback(
    (tile: TileInput): number => {
      const key = tile.joker ? "joker" : `${tile.color}-${tile.number}`;
      const inRack = rack.filter((t) => {
        const k = t.joker ? "joker" : `${t.color}-${t.number}`;
        return k === key;
      }).length;
      const inBoard = boardSets
        .flatMap((s) => s.tiles)
        .filter((t) => {
          const k = t.joker ? "joker" : `${t.color}-${t.number}`;
          return k === key;
        }).length;
      return inRack + inBoard;
    },
    [rack, boardSets],
  );

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {t("heading")}
      </h2>
      <TileGridPicker onSelect={addRackTile} tileCount={tileCount} />
      {rack.length > 0 ? (
        <div className="flex flex-wrap gap-2 pt-1">
          {rack.map((tile, i) => (
            <Tile
              key={i}
              color={tile.color ?? null}
              number={tile.number ?? null}
              isJoker={tile.joker ?? false}
              onRemove={() => removeRackTile(i)}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400 dark:text-gray-500 italic">{t("empty")}</p>
      )}
    </section>
  );
}
