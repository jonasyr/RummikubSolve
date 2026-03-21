"use client";

import { useCallback, useState } from "react";
import { useGameStore } from "../store/game";
import Tile from "./Tile";
import TileGridPicker from "./TileGridPicker";
import type { TileColor, TileInput } from "../types/api";

// ---------------------------------------------------------------------------
// Client-side set validation (mirrors backend rule_checker.py logic)
// ---------------------------------------------------------------------------

function validateSet(
  type: "run" | "group",
  tiles: TileInput[],
): string | null {
  if (tiles.length < 3) return `Need at least 3 tiles (have ${tiles.length})`;
  if (tiles.length > 13) return "Too many tiles (max 13)";

  const jokers = tiles.filter((t) => t.joker);
  const nonJokers = tiles.filter((t) => !t.joker);
  const jLen = jokers.length;

  if (type === "run") {
    // All jokers — structurally valid for any run.
    if (nonJokers.length === 0) return null;

    const colors = [...new Set(nonJokers.map((t) => t.color as TileColor))];
    if (colors.length > 1) return "Run: all tiles must be the same color";

    const nums = nonJokers.map((t) => t.number!).sort((a, b) => a - b);
    if (new Set(nums).size < nums.length)
      return "Run: cannot have duplicate numbers";

    const nMin = nums[0];
    const nMax = nums[nums.length - 1];
    const internalGaps = nMax - nMin + 1 - nums.length;
    if (internalGaps > jLen)
      return "Run: not enough jokers to fill gaps between tiles";

    // A valid start position `a` must satisfy:
    //   a ≤ nMin, a ≥ nMax - total + 1, a ≥ 1, a + total - 1 ≤ 13
    const total = tiles.length;
    const lo = Math.max(1, nMax - total + 1);
    const hi = Math.min(nMin, 14 - total);
    if (lo > hi) return "Run: tiles don't fit within the 1–13 range";

    return null;
  }

  // group
  if (tiles.length > 4) return "Group: can have at most 4 tiles";
  if (nonJokers.length === 0) return null; // all jokers

  const nums = [...new Set(nonJokers.map((t) => t.number))];
  if (nums.length > 1) return "Group: all tiles must have the same number";

  const colors = nonJokers.map((t) => t.color!);
  if (new Set(colors).size < colors.length)
    return "Group: cannot have duplicate colors";

  const distinctColors = new Set(colors).size;
  if (jLen > 4 - distinctColors) return "Group: too many jokers";

  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BoardSection() {
  const boardSets = useGameStore((s) => s.boardSets);
  const addBoardSet = useGameStore((s) => s.addBoardSet);
  const removeBoardSet = useGameStore((s) => s.removeBoardSet);
  const updateBoardSet = useGameStore((s) => s.updateBoardSet);
  const isBuildingSet = useGameStore((s) => s.isBuildingSet);
  const setIsBuildingSet = useGameStore((s) => s.setIsBuildingSet);
  const isLoading = useGameStore((s) => s.isLoading);
  const [pendingType, setPendingType] = useState<"run" | "group">("run");
  const [pendingTiles, setPendingTiles] = useState<TileInput[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const validationError = validateSet(pendingType, pendingTiles);
  const canConfirm = pendingTiles.length >= 3 && validationError === null;

  function confirmSet() {
    if (!canConfirm) return;
    if (editingIndex !== null) {
      updateBoardSet(editingIndex, { type: pendingType, tiles: pendingTiles });
    } else {
      addBoardSet({ type: pendingType, tiles: pendingTiles });
    }
    cancelSet();
  }

  function cancelSet() {
    setIsBuildingSet(false);
    setPendingTiles([]);
    setPendingType("run");
    setEditingIndex(null);
  }

  function startEditing(si: number) {
    const set = boardSets[si];
    setEditingIndex(si);
    setPendingType(set.type);
    setPendingTiles([...set.tiles]);
    setIsBuildingSet(true);
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
        {!isBuildingSet && (
          <button
            onClick={() => setIsBuildingSet(true)}
            disabled={isLoading}
            className="text-sm px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
          >
            + Add Set
          </button>
        )}
      </div>

      {/* Existing sets */}
      {boardSets.length === 0 && !isBuildingSet && (
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
              disabled={isLoading}
              className="shrink-0 text-gray-400 hover:text-blue-500 text-base leading-none disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label={`Edit set ${si + 1}`}
            >
              ✎
            </button>
            <button
              onClick={() => removeBoardSet(si)}
              disabled={isLoading}
              className="shrink-0 text-gray-400 hover:text-red-500 text-lg leading-none disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label={`Remove set ${si + 1}`}
            >
              ×
            </button>
          </div>
        ))}
      </div>

      {/* Inline set builder */}
      {isBuildingSet && (
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

          {/* Live validation feedback */}
          {pendingTiles.length >= 3 && validationError && (
            <p className="text-xs text-red-600 font-medium">{validationError}</p>
          )}
          {pendingTiles.length >= 3 && !validationError && (
            <p className="text-xs text-green-600 font-medium">Valid set ✓</p>
          )}

          <div className="flex gap-2">
            <button
              onClick={confirmSet}
              disabled={!canConfirm}
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
