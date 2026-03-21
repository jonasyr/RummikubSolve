"use client";

import { useGameStore } from "../store/game";
import Tile from "./Tile";
import TileGridPicker from "./TileGridPicker";

export default function RackSection() {
  const rack = useGameStore((s) => s.rack);
  const addRackTile = useGameStore((s) => s.addRackTile);
  const removeRackTile = useGameStore((s) => s.removeRackTile);

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
        Your Rack
      </h2>
      <TileGridPicker onSelect={addRackTile} />
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
        <p className="text-sm text-gray-400 italic">
          Click tiles above to add them to your rack.
        </p>
      )}
    </section>
  );
}
