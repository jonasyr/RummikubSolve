"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import type { TranslationValues } from "next-intl";
import { useGameStore } from "../store/game";
import Tile from "./Tile";
import TileGridPicker from "./TileGridPicker";
import type { TileColor, TileInput } from "../types/api";

// ---------------------------------------------------------------------------
// Client-side set validation (mirrors backend rule_checker.py logic)
// Returns a translation key + optional params, or null if valid.
// ---------------------------------------------------------------------------

type ValidationResult = { key: string; params?: TranslationValues } | null;

function validateSet(
  type: "run" | "group",
  tiles: TileInput[],
): ValidationResult {
  if (tiles.length < 3) return { key: "errors.minTiles", params: { count: tiles.length } };
  if (tiles.length > 13) return { key: "errors.maxTiles" };

  const jokers = tiles.filter((t) => t.joker);
  const nonJokers = tiles.filter((t) => !t.joker);
  const jLen = jokers.length;

  if (type === "run") {
    if (nonJokers.length === 0) return null;

    const colors = [...new Set(nonJokers.map((t) => t.color as TileColor))];
    if (colors.length > 1) return { key: "errors.runColor" };

    const nums = nonJokers.map((t) => t.number!).sort((a, b) => a - b);
    if (new Set(nums).size < nums.length) return { key: "errors.runDuplicates" };

    const nMin = nums[0];
    const nMax = nums[nums.length - 1];
    const internalGaps = nMax - nMin + 1 - nums.length;
    if (internalGaps > jLen) return { key: "errors.runJokers" };

    const total = tiles.length;
    const lo = Math.max(1, nMax - total + 1);
    const hi = Math.min(nMin, 14 - total);
    if (lo > hi) return { key: "errors.runRange" };

    return null;
  }

  // group
  if (tiles.length > 4) return { key: "errors.groupMax" };
  if (nonJokers.length === 0) return null;

  const nums = [...new Set(nonJokers.map((t) => t.number))];
  if (nums.length > 1) return { key: "errors.groupNumber" };

  const colors = nonJokers.map((t) => t.color!);
  if (new Set(colors).size < colors.length) return { key: "errors.groupColors" };

  const distinctColors = new Set(colors).size;
  if (jLen > 4 - distinctColors) return { key: "errors.groupJokers" };

  return null;
}

/** Try "run" first, then "group". Returns the first valid type or null. */
function getValidType(tiles: TileInput[]): "run" | "group" | null {
  if (validateSet("run", tiles) === null) return "run";
  if (validateSet("group", tiles) === null) return "group";
  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BoardSection() {
  const t = useTranslations("board");
  const boardSets = useGameStore((s) => s.boardSets);
  const rack = useGameStore((s) => s.rack);
  const addBoardSet = useGameStore((s) => s.addBoardSet);
  const removeBoardSet = useGameStore((s) => s.removeBoardSet);
  const updateBoardSet = useGameStore((s) => s.updateBoardSet);
  const isBuildingSet = useGameStore((s) => s.isBuildingSet);
  const setIsBuildingSet = useGameStore((s) => s.setIsBuildingSet);
  const isLoading = useGameStore((s) => s.isLoading);
  const [pendingTiles, setPendingTiles] = useState<TileInput[]>([]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  // Auto-detect type from current pending tiles.
  const validType = pendingTiles.length >= 3 ? getValidType(pendingTiles) : null;
  const canConfirm = validType !== null;

  // For live error feedback when tiles >= 3 and neither type is valid, show the run error.
  const validationError = (() => {
    if (pendingTiles.length < 3) return null;
    if (validType !== null) return null;
    const runResult = validateSet("run", pendingTiles);
    const result = runResult ?? validateSet("group", pendingTiles);
    return result ? t(result.key as Parameters<typeof t>[0], result.params) : null;
  })();

  function confirmSet() {
    if (!canConfirm || validType === null) return;
    if (editingIndex !== null) {
      updateBoardSet(editingIndex, { type: validType, tiles: pendingTiles });
    } else {
      addBoardSet({ type: validType, tiles: pendingTiles });
    }
    cancelSet();
  }

  function cancelSet() {
    setIsBuildingSet(false);
    setPendingTiles([]);
    setEditingIndex(null);
  }

  function startEditing(si: number) {
    const set = boardSets[si];
    setEditingIndex(si);
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
      const inRack = rack.filter((t) => {
        const k = t.joker ? "joker" : `${t.color}-${t.number}`;
        return k === key;
      }).length;
      return inPending + inBoard + inRack;
    },
    [pendingTiles, boardSets, editingIndex, rack],
  );

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          {t("heading")}
        </h2>
        {!isBuildingSet && (
          <button
            onClick={() => setIsBuildingSet(true)}
            disabled={isLoading}
            className="text-sm px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {t("addSet")}
          </button>
        )}
      </div>

      {/* Inline set builder — shown at top so it's immediately visible */}
      {isBuildingSet && (
        <div className="p-3 border border-blue-200 rounded-lg bg-blue-50 space-y-3">
          <TileGridPicker
            onSelect={(tile) =>
              setPendingTiles((prev) => {
                const next = [...prev, tile];
                // Auto-sort runs by number as tiles are picked.
                return getValidType(next) === "run"
                  ? [...next].sort((a, b) => (a.number ?? 0) - (b.number ?? 0))
                  : next;
              })
            }
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
          {pendingTiles.length >= 3 && !validationError && validType && (
            <p className="text-xs text-green-600 font-medium">
              {t("validSet")} ({t(validType as "run" | "group")})
            </p>
          )}

          <div className="flex gap-2">
            <button
              onClick={confirmSet}
              disabled={!canConfirm}
              className="px-3 py-1 rounded text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {editingIndex !== null ? t("saveChanges") : t("addToBoard")}
            </button>
            <button
              onClick={cancelSet}
              className="px-3 py-1 rounded text-sm font-medium bg-white text-gray-600 border border-gray-300 hover:bg-gray-50"
            >
              {t("cancel")}
            </button>
          </div>
        </div>
      )}

      {/* Existing sets */}
      {boardSets.length === 0 && !isBuildingSet && (
        <p className="text-sm text-gray-400 italic">{t("noSets")}</p>
      )}
      <div className="space-y-2">
        {boardSets.map((set, si) => (
          <div
            key={si}
            className="flex items-start gap-2 p-2 bg-gray-50 rounded border border-gray-200"
          >
            <span className="text-xs text-gray-400 uppercase w-8 shrink-0 pt-1">
              {t(set.type as "run" | "group")}
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
              aria-label={t("editSet", { n: si + 1 })}
            >
              ✎
            </button>
            <button
              onClick={() => removeBoardSet(si)}
              disabled={isLoading}
              className="shrink-0 text-gray-400 hover:text-red-500 text-lg leading-none disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label={t("removeSet", { n: si + 1 })}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
