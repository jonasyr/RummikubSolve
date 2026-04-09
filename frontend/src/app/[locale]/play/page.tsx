"use client";

import { useTranslations } from "next-intl";
import { usePlayStore } from "../../../store/play";
import { GRID_COLS } from "../../../types/play";
import PlayLayout from "../../../components/play/PlayLayout";
import ControlBar from "../../../components/play/ControlBar";
import PlayPuzzleControls from "../../../components/play/PlayPuzzleControls";
import PlayGrid from "../../../components/play/PlayGrid";
import PlayRack from "../../../components/play/PlayRack";

export default function PlayPage() {
  const t = useTranslations("play");

  const puzzle = usePlayStore((s) => s.puzzle);
  const grid = usePlayStore((s) => s.grid);
  const gridRows = usePlayStore((s) => s.gridRows);
  const detectedSets = usePlayStore((s) => s.detectedSets);
  const selectedTile = usePlayStore((s) => s.selectedTile);
  const showValidation = usePlayStore((s) => s.showValidation);
  const tapCell = usePlayStore((s) => s.tapCell);

  return (
    <PlayLayout>
      {/* controls grid area */}
      <div
        style={{ gridArea: "controls" }}
        className="flex flex-col gap-2 border-b px-2 py-2"
      >
        <ControlBar />
        <PlayPuzzleControls />
      </div>

      {/* board grid area */}
      {puzzle ? (
        <PlayGrid
          grid={grid}
          rows={gridRows}
          cols={GRID_COLS}
          detectedSets={detectedSets}
          selectedTile={selectedTile}
          showValidation={showValidation}
          onCellClick={tapCell}
        />
      ) : (
        <div
          style={{ gridArea: "board" }}
          className="flex items-center justify-center text-sm text-gray-400"
        >
          {t("loadPuzzlePrompt")}
        </div>
      )}

      {/* rack grid area */}
      <PlayRack />
    </PlayLayout>
  );
}
