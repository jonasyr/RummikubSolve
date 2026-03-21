"use client";

import { useCallback, useState } from "react";
import { useGameStore } from "../store/game";
import Tile from "./Tile";
import TileGridPicker from "./TileGridPicker";
import type { TileInput } from "../types/api";

export default function BoardSection() {
  const boardSets = useGameStore((s) => s.boardSets);
  const addBoardSet = useGameStore((s) => s.addBoardSet);
  const removeBoardSet = useGameStore((s) => s.removeBoardSet);
  const updateBoardSet = useGameStore((s) => s.updateBoardSet);

  const [building, setBuilding] = useState(false);
  const [pendingType, setPendingType] = useState<"run" | "group">("run");
  const [pendingTiles, setPendingTiles] = useState<TileInput[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  function confirmSet() {
    if (pendingTiles.length === 0) return;
    if (editingIndex !== null) {
      updateBoardSet(editingIndex, { type: pendingType, tiles: pendingTiles });
    } else {
      addBoardSet({ type: pendingType, tiles: pendingTiles });
    }
    cancelSet();
  }

  function cancelSet() {
    setBuilding(false);
    setPendingTiles([]);
    setPendingType("run");
    setEditingIndex(null);
  }

  function startEditing(si: number) {
    const set = boardSets[si];
    setEditingIndex(si);
    setPendingType(set.type);
    setPendingTiles([...set.tiles]);
    setBuilding(true);
  }

  const tileCountForPending = useCallback(
    (tile: TileInput): number => {
      const key = tile.joker ? "joker" : `${tile.color}-${tile.number}`;
      const inPending = pendingTiles.filter((t) => {
        const k = t.joker ? "joker" : `${t.color}-${t.number}`;
        return k === key;
      }).length;
      const inBoard = boardSets.reduce((sum, set, idx) => {
        if (idx === editingIndex) return sum;
        return (
          sum +
          set.tiles.filter((t) => {
            const k = t.joker ? "joker" : `${t.color}-${t.number}`;
            return k === key;
          }).length
        );
      }, 0);
      return inPending + inBoard;
    },
    [pendingTiles, boardSets, editingIndex],
  );

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          Board Sets
        </h2>
        {!building && (
          <button
            onClick={() => setBuilding(true)}
            className="text-sm px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium"
          >
            + Add Set
          </button>
        )}
      </div>

      {/* Existing sets */}
      {boardSets.length === 0 && !building && (
        <p className="text-sm text-gray-400 italic">No board sets yet.</p>
      )}
      <div className="space-y-2">
        {boardSets.map((set, si) => (
          <div
            key={si}
            className="flex items-start gap-2 p-2 bg-gray-50 rounded border border-gray-200"
          >
            <span className="text-xs text-gray-400 uppercase w-8 shrink-0 pt-1">
              {set.type}
            </span>
            <div className="flex flex-wrap gap-1 flex-1">
              {set.tiles.map((tile, ti) => (
                <Tile
                  key={ti}
                  color={tile.color ?? null}
                  number={tile.number ?? null}
                  isJoker={tile.joker ?? false}
                  size="sm"
                />
              ))}
            </div>
            <button
              onClick={() => startEditing(si)}
              className="shrink-0 text-gray-400 hover:text-blue-500 text-base leading-none"
              aria-label={`Edit set ${si + 1}`}
            >
              ✎
            </button>
            <button
              onClick={() => removeBoardSet(si)}
              className="shrink-0 text-gray-400 hover:text-red-500 text-lg leading-none"
              aria-label={`Remove set ${si + 1}`}
            >
              ×
            </button>
          </div>
        ))}
      </div>

      {/* Inline set builder */}
      {building && (
        <div className="p-3 border border-blue-200 rounded-lg bg-blue-50 space-y-3">
          {/* Type selector */}
          <div className="flex gap-2">
            {(["run", "group"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setPendingType(t)}
                className={`px-3 py-1 rounded text-sm font-medium capitalize ${
                  pendingType === t
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-600 border border-gray-300 hover:bg-gray-50"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <TileGridPicker
            onSelect={(tile) => setPendingTiles((prev) => [...prev, tile])}
            tileCount={tileCountForPending}
          />

          {/* Pending tiles preview */}
          {pendingTiles.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {pendingTiles.map((tile, i) => (
                <Tile
                  key={i}
                  color={tile.color ?? null}
                  number={tile.number ?? null}
                  isJoker={tile.joker ?? false}
                  size="sm"
                  onRemove={() =>
                    setPendingTiles((prev) => prev.filter((_, idx) => idx !== i))
                  }
                />
              ))}
            </div>
          )}

          <div className="flex gap-2">
            <button
              onClick={confirmSet}
              disabled={pendingTiles.length === 0}
              className="px-3 py-1 rounded text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {editingIndex !== null ? "Save Changes" : "Add to Board"}
            </button>
            <button
              onClick={cancelSet}
              className="px-3 py-1 rounded text-sm font-medium bg-white text-gray-600 border border-gray-300 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
