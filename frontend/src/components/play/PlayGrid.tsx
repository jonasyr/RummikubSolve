"use client";

import type { CellKey, DetectedSet, PlacedTile, TileSelection } from "../../types/play";
import { cellKey, CELL_SIZE_PX, CELL_GAP_PX } from "../../types/play";
import GridCell from "./GridCell";
import SetOverlay from "./SetOverlay";

interface Props {
  grid: Map<CellKey, PlacedTile>;
  rows: number;
  cols: number;
  detectedSets: DetectedSet[];
  selectedTile: TileSelection;
  showValidation: boolean;
  onCellClick: (row: number, col: number) => void;
}

export default function PlayGrid({
  grid,
  rows,
  cols,
  detectedSets,
  selectedTile,
  showValidation,
  onCellClick,
}: Props) {
  const cellPx = CELL_SIZE_PX + CELL_GAP_PX;

  return (
    <div
      className="play-surface overflow-auto"
      style={{ gridArea: "board" }}
      role="region"
      aria-label="Puzzle board grid"
    >
      <div
        className="relative"
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${cols}, ${CELL_SIZE_PX}px)`,
          gridTemplateRows: `repeat(${rows}, ${CELL_SIZE_PX}px)`,
          gap: `${CELL_GAP_PX}px`,
          width: cols * cellPx,
          height: rows * cellPx,
        }}
      >
        {Array.from({ length: rows * cols }, (_, i) => {
          const row = Math.floor(i / cols);
          const col = i % cols;
          const key = cellKey(row, col);
          const placed = grid.get(key) ?? null;
          const isSelected =
            selectedTile?.source === "grid" &&
            selectedTile.row === row &&
            selectedTile.col === col;

          return (
            <GridCell
              key={key}
              row={row}
              col={col}
              placed={placed}
              isSelected={isSelected}
              isDropTarget={selectedTile !== null && !placed}
              onClick={() => onCellClick(row, col)}
            />
          );
        })}

        {showValidation &&
          detectedSets.map((ds) => (
            <SetOverlay
              key={`overlay-${ds.row}-${ds.startCol}`}
              set={ds}
              cellPx={cellPx}
            />
          ))}
      </div>
    </div>
  );
}
