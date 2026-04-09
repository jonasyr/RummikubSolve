"use client";

import { usePlayStore } from "../../store/play";
import Tile from "../Tile";

export default function PlayRack() {
  const rack = usePlayStore((s) => s.rack);
  const selectedTile = usePlayStore((s) => s.selectedTile);
  const tapRackTile = usePlayStore((s) => s.tapRackTile);

  return (
    <div
      className="play-rack-scroll border-t lg:border-t-0 lg:border-l overflow-auto p-2"
      style={{ gridArea: "rack" }}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">
        {rack.length} {rack.length === 1 ? "tile" : "tiles"}
      </p>

      {rack.length === 0 ? null : (
        <div className="flex flex-wrap gap-1 lg:flex-col">
          {rack.map((tile, idx) => {
            const isSelected =
              selectedTile?.source === "rack" && selectedTile.index === idx;
            return (
              <button
                key={idx}
                onClick={() => tapRackTile(idx)}
                className={`flex items-center justify-center p-1 rounded border ${
                  isSelected
                    ? "ring-2 ring-blue-500 ring-offset-1 border-blue-300"
                    : "border-gray-200 dark:border-gray-700"
                }`}
                aria-label={
                  tile.joker
                    ? "joker"
                    : `${tile.color ?? ""} ${tile.number ?? ""}`
                }
              >
                <Tile
                  color={tile.color ?? null}
                  number={tile.number ?? null}
                  isJoker={tile.joker ?? false}
                  size="sm"
                />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
