"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { useGameStore } from "../store/game";
import type { Difficulty, PuzzleRequest } from "../types/api";

const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard", "expert", "nightmare", "custom"];

// ---------------------------------------------------------------------------
// Stepper: inline helper for the ± counter controls
// ---------------------------------------------------------------------------

interface StepperProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  decLabel: string;
  incLabel: string;
}

function Stepper({ value, min, max, step = 1, onChange, decLabel, incLabel }: StepperProps) {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => onChange(Math.max(min, value - step))}
        disabled={value <= min}
        className="w-6 h-6 flex items-center justify-center rounded bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed font-mono leading-none"
        aria-label={decLabel}
      >
        −
      </button>
      <span className="w-6 text-center text-sm font-medium tabular-nums">{value}</span>
      <button
        onClick={() => onChange(Math.min(max, value + step))}
        disabled={value >= max}
        className="w-6 h-6 flex items-center justify-center rounded bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed font-mono leading-none"
        aria-label={incLabel}
      >
        +
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function PuzzleControls() {
  const t = useTranslations("puzzle");
  const [selected, setSelected] = useState<Difficulty>("medium");

  // Custom mode parameters
  const [setsToRemove, setSetsToRemove] = useState(3);
  const [minBoardSets, setMinBoardSets] = useState(8);
  const [maxBoardSets, setMaxBoardSets] = useState(14);
  const [minChainDepth, setMinChainDepth] = useState(0);
  const [minDisruption, setMinDisruption] = useState(0);

  const isPuzzleLoading = useGameStore((s) => s.isPuzzleLoading);
  const puzzleError = useGameStore((s) => s.error);
  const loadPuzzle = useGameStore((s) => s.loadPuzzle);
  const lastPuzzleMeta = useGameStore((s) => s.lastPuzzleMeta);
  const abortRef = useRef<AbortController | null>(null);
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const wasLoadingRef = useRef(false);

  // Chain depth label array (index = depth value 0–4)
  const chainDepthLabels = [
    t("customChainDepthNone"),
    t("customChainDepthSimple"),
    t("customChainDepthModerate"),
    t("customChainDepthDeep"),
    t("customChainDepthExpert"),
  ] as const;

  // Show slow-generation warning for strict custom settings
  const isSlowWarning =
    selected === "custom" &&
    (minChainDepth >= 2 || minDisruption >= 20 || setsToRemove >= 6);

  useEffect(() => {
    // Only collapse on successful load (not on error — user needs to see the error and retry).
    if (wasLoadingRef.current && !isPuzzleLoading && !puzzleError) {
      if (detailsRef.current) detailsRef.current.open = false;
    }
    wasLoadingRef.current = isPuzzleLoading;
  }, [isPuzzleLoading, puzzleError]);

  function handleGetPuzzle() {
    // Cancel any still-in-flight request before starting a new one.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const request: PuzzleRequest = {
      difficulty: selected,
      ...(selected === "custom"
        ? {
            sets_to_remove: setsToRemove,
            min_board_sets: minBoardSets,
            max_board_sets: maxBoardSets,
            min_chain_depth: minChainDepth,
            min_disruption: minDisruption,
          }
        : {}),
    };
    void loadPuzzle(request, controller.signal);
  }

  return (
    <details ref={detailsRef} className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-sm">
      <summary className="px-4 py-2 cursor-pointer font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 select-none list-none flex items-center gap-2">
        <span className="text-base">🎯</span> {t("title")}
      </summary>
      <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
        {/* Difficulty buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {DIFFICULTIES.map((d) => (
            <button
              key={d}
              onClick={() => setSelected(d)}
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                selected === d
                  ? "bg-blue-600 text-white"
                  : "bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600"
              }`}
            >
              {t(d)}
            </button>
          ))}

          <button
            onClick={handleGetPuzzle}
            disabled={isPuzzleLoading}
            className="ml-auto px-4 py-1 rounded bg-green-600 text-white font-medium text-sm hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1"
          >
            {isPuzzleLoading ? (
              <>
                <span className="animate-spin text-base">⟳</span>
                {t("loading")}
              </>
            ) : (
              t("getButton")
            )}
          </button>
        </div>

        {/* Custom mode parameter panel */}
        {selected === "custom" && (
          <div className="w-full mt-2 space-y-2 text-xs text-gray-600 dark:text-gray-300 border-t border-gray-200 dark:border-gray-600 pt-2">
            {/* Sets to sacrifice */}
            <div className="flex items-center justify-between">
              <span>{t("customSetsToSacrifice")}</span>
              <Stepper
                value={setsToRemove}
                min={1}
                max={8}
                onChange={setSetsToRemove}
                decLabel="Decrease sets to sacrifice"
                incLabel="Increase sets to sacrifice"
              />
            </div>

            {/* Board sets range */}
            <div className="flex items-center justify-between">
              <span>{t("customBoardSets")}</span>
              <div className="flex items-center gap-1">
                <Stepper
                  value={minBoardSets}
                  min={5}
                  max={maxBoardSets}
                  onChange={setMinBoardSets}
                  decLabel="Decrease min board sets"
                  incLabel="Increase min board sets"
                />
                <span className="text-gray-400 px-1">–</span>
                <Stepper
                  value={maxBoardSets}
                  min={minBoardSets}
                  max={25}
                  onChange={setMaxBoardSets}
                  decLabel="Decrease max board sets"
                  incLabel="Increase max board sets"
                />
              </div>
            </div>

            {/* Min chain depth */}
            <div className="flex items-center justify-between">
              <span>{t("customMinChainDepth")}</span>
              <div className="flex items-center gap-2">
                <Stepper
                  value={minChainDepth}
                  min={0}
                  max={4}
                  onChange={setMinChainDepth}
                  decLabel="Decrease min chain depth"
                  incLabel="Increase min chain depth"
                />
                <span className="text-gray-400 italic text-[10px] w-14 text-right">
                  {chainDepthLabels[minChainDepth]}
                </span>
              </div>
            </div>

            {/* Min disruption */}
            <div className="flex items-center justify-between">
              <span>{t("customMinDisruption")}</span>
              <Stepper
                value={minDisruption}
                min={0}
                max={60}
                step={5}
                onChange={setMinDisruption}
                decLabel="Decrease min disruption"
                incLabel="Increase min disruption"
              />
            </div>

            {/* Slow generation warning */}
            {isSlowWarning && (
              <p className="text-amber-600 dark:text-amber-400 text-[11px]">
                ⚠ {t("customSlowWarning")}
              </p>
            )}

            {/* Uniqueness info note */}
            <p className="text-gray-400 dark:text-gray-500 text-[10px] leading-tight">
              ℹ {t("customUniquenessNote")}
            </p>
          </div>
        )}

        {/* Stats badge — shown after a puzzle loads */}
        {lastPuzzleMeta && (
          <div className="w-full mt-1 flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
            <span>{t("chainDepth", { depth: lastPuzzleMeta.chainDepth })}</span>
            {lastPuzzleMeta.isUnique && (
              <span className="text-green-600 dark:text-green-400 font-medium">
                ✓ {t("uniqueSolution")}
              </span>
            )}
          </div>
        )}
      </div>
    </details>
  );
}
