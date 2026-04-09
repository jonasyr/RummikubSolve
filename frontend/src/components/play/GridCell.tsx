"use client";

import { memo } from "react";
import type { PlacedTile } from "../../types/play";
import Tile from "../Tile";

interface Props {
  row: number;
  col: number;
  placed: PlacedTile | null;
  isSelected: boolean;
  isDropTarget: boolean;
  onClick: () => void;
}

const BASE = "w-12 h-12 rounded border flex items-center justify-center";

export default memo(function GridCell({
  row,
  col,
  placed,
  isSelected,
  isDropTarget,
  onClick,
}: Props) {
  if (placed) {
    return (
      <div
        className={`${BASE} cursor-pointer${isSelected ? " ring-2 ring-blue-500 ring-offset-1" : ""}`}
        onClick={onClick}
        data-row={row}
        data-col={col}
        data-slot-cell
      >
        <Tile
          color={placed.tile.color ?? null}
          number={placed.tile.number ?? null}
          isJoker={placed.tile.joker ?? false}
          size="sm"
        />
      </div>
    );
  }

  return (
    <div
      className={`${BASE} ${
        isDropTarget
          ? "border-dashed border-green-300 dark:border-green-700 cursor-pointer"
          : "border-gray-200 dark:border-gray-800"
      }`}
      onClick={onClick}
      data-row={row}
      data-col={col}
      data-slot-cell
    />
  );
});
