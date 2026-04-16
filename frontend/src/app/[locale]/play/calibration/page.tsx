"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { fetchCalibrationBatch } from "../../../../lib/api";
import { recordTelemetryEvent } from "../../../../lib/telemetry";
import PlayLayout from "../../../../components/play/PlayLayout";
import ControlBar from "../../../../components/play/ControlBar";
import PlayGrid from "../../../../components/play/PlayGrid";
import PlayRack from "../../../../components/play/PlayRack";
import SolvedBanner from "../../../../components/play/SolvedBanner";
import { usePlayStore } from "../../../../store/play";
import { GRID_COLS } from "../../../../types/play";
import type {
  CalibrationBatchEntry,
  TelemetrySelfLabel,
} from "../../../../types/api";

const BATCH_NAME = "phase7_batch_v1";
const STORAGE_KEY = `calibration:${BATCH_NAME}:progress`;
const ACCESS_KEY = "calibration:access-granted";
const ACCESS_PASSWORD = "123";

type ProgressEntry = {
  rated: boolean;
  abandoned: boolean;
  selfRating?: number;
  selfLabel?: TelemetrySelfLabel;
};

type ProgressState = {
  currentIndex: number;
  entries: Record<number, ProgressEntry>;
};

const initialProgress: ProgressState = { currentIndex: 0, entries: {} };

export default function CalibrationPage() {
  const t = useTranslations("calibration");
  const playT = useTranslations("play");
  const locale = useLocale();

  const [batchRunId] = useState<string>(() =>
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `run-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
  );
  const [batch, setBatch] = useState<CalibrationBatchEntry[]>([]);
  const [progress, setProgress] = useState<ProgressState>(initialProgress);
  const [loadingBatch, setLoadingBatch] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [accessGranted, setAccessGranted] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [selfRating, setSelfRating] = useState(5);
  const [selfLabel, setSelfLabel] = useState<TelemetrySelfLabel>("challenging");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const puzzle = usePlayStore((s) => s.puzzle);
  const grid = usePlayStore((s) => s.grid);
  const gridRows = usePlayStore((s) => s.gridRows);
  const detectedSets = usePlayStore((s) => s.detectedSets);
  const selectedTile = usePlayStore((s) => s.selectedTile);
  const showValidation = usePlayStore((s) => s.showValidation);
  const tapCell = usePlayStore((s) => s.tapCell);
  const loadPuzzle = usePlayStore((s) => s.loadPuzzle);
  const setCalibrationContext = usePlayStore((s) => s.setCalibrationContext);
  const isSolved = usePlayStore((s) => s.isSolved);
  const attemptId = usePlayStore((s) => s.attemptId);
  const rack = usePlayStore((s) => s.rack);
  const moveCount = usePlayStore((s) => s.moveCount);
  const undoCount = usePlayStore((s) => s.undoCount);
  const redoCount = usePlayStore((s) => s.redoCount);
  const commitCount = usePlayStore((s) => s.commitCount);
  const revertCount = usePlayStore((s) => s.revertCount);
  const solveStartTime = usePlayStore((s) => s.solveStartTime);
  const stuckMoments = usePlayStore((s) => s.stuckMoments);

  const currentIndex = progress.currentIndex;
  const currentEntry = batch[currentIndex] ?? null;
  const currentProgress = progress.entries[currentIndex];

  useEffect(() => {
    try {
      setAccessGranted(sessionStorage.getItem(ACCESS_KEY) === "true");
    } catch {
      setAccessGranted(false);
    }
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setProgress(JSON.parse(raw) as ProgressState);
    } catch {
      // ignore malformed developer progress
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
    } catch {
      // ignore storage failures
    }
  }, [progress]);

  useEffect(() => {
    if (!accessGranted) return;
    let cancelled = false;
    setLoadingBatch(true);
    void fetchCalibrationBatch(BATCH_NAME)
      .then((response) => {
        if (cancelled) return;
        setBatch(response.entries);
        setLoadingBatch(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : t("errors.batchLoad"));
        setLoadingBatch(false);
      });
    return () => {
      cancelled = true;
    };
  }, [accessGranted, t]);

  useEffect(() => {
    if (!currentEntry) return;
    setCalibrationContext({ batchName: BATCH_NAME, batchRunId: batchRunId, batchIndex: currentIndex });
    // Pregenerated batches (Phase 7+) supply puzzle_id → instant pool load.
    // Legacy batches supply only seed → live generation.
    const alreadyLoaded = currentEntry.puzzle_id
      ? puzzle?.puzzle_id === currentEntry.puzzle_id
      : puzzle?.seed === currentEntry.seed && puzzle?.difficulty === currentEntry.difficulty;
    if (alreadyLoaded) return;
    void loadPuzzle(
      currentEntry.puzzle_id
        ? { puzzle_id: currentEntry.puzzle_id, difficulty: currentEntry.difficulty }
        : { difficulty: currentEntry.difficulty, seed: currentEntry.seed },
    );
  }, [currentEntry, currentIndex, loadPuzzle, puzzle?.difficulty, puzzle?.seed, setCalibrationContext]);

  useEffect(() => {
    const saved = progress.entries[currentIndex];
    setSelfRating(saved?.selfRating ?? 5);
    setSelfLabel(saved?.selfLabel ?? "challenging");
    setNotes("");
  }, [currentIndex, progress.entries]);

  const completedCount = useMemo(
    () => Object.values(progress.entries).filter((entry) => entry.rated || entry.abandoned).length,
    [progress.entries],
  );

  const isRunComplete = batch.length > 0 && completedCount >= batch.length;

  const startNewRun = () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore storage failures
    }
    setProgress(initialProgress);
  };

  const unlock = () => {
    if (password !== ACCESS_PASSWORD) {
      setPasswordError(t("password.error"));
      return;
    }
    try {
      sessionStorage.setItem(ACCESS_KEY, "true");
    } catch {
      // ignore storage failures
    }
    setPasswordError(null);
    setAccessGranted(true);
  };

  const submitRating = async () => {
    if (!puzzle) return;
    setSubmitting(true);
    try {
      await recordTelemetryEvent("puzzle_rated", puzzle, {
        attempt_id: attemptId ?? "",
        batch_name: BATCH_NAME,
        batch_run_id: batchRunId,
        batch_index: currentIndex,
        self_rating: selfRating,
        self_label: selfLabel,
        stuck_moments: stuckMoments,
        notes,
      });
      setProgress((prev) => ({
        ...prev,
        entries: {
          ...prev.entries,
          [currentIndex]: {
            ...prev.entries[currentIndex],
            rated: true,
            selfRating,
            selfLabel,
          },
        },
      }));
    } finally {
      setSubmitting(false);
    }
  };

  const abandonPuzzle = async () => {
    if (!puzzle) return;
    setSubmitting(true);
    try {
      const elapsedMs = solveStartTime === null ? 0 : Math.max(0, Date.now() - solveStartTime);
      const initialRack = puzzle.rack.length;
      await recordTelemetryEvent("puzzle_abandoned", puzzle, {
        attempt_id: attemptId ?? "",
        batch_name: BATCH_NAME,
        batch_run_id: batchRunId,
        batch_index: currentIndex,
        elapsed_ms: elapsedMs,
        move_count: moveCount,
        undo_count: undoCount,
        redo_count: redoCount,
        commit_count: commitCount,
        revert_count: revertCount,
        tiles_placed: initialRack - rack.length,
        tiles_remaining: rack.length,
      });
      setProgress((prev) => ({
        ...prev,
        entries: {
          ...prev.entries,
          [currentIndex]: {
            ...prev.entries[currentIndex],
            abandoned: true,
          },
        },
      }));
    } finally {
      setSubmitting(false);
    }
  };

  const jumpTo = (nextIndex: number) => {
    setProgress((prev) => ({
      ...prev,
      currentIndex: Math.max(0, Math.min(nextIndex, batch.length - 1)),
    }));
  };

  if (!accessGranted) {
    return (
      <div className="min-h-dvh overflow-y-auto px-2 py-2">
        <PlayLayout className="h-auto min-h-[100dvh]">
          <div style={{ gridArea: "controls" }} className="flex min-h-[60vh] items-center justify-center px-4 py-8">
            <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-900">
              <h1 className="text-lg font-semibold">{t("password.title")}</h1>
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{t("password.description")}</p>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t("password.placeholder")}
                className="mt-4 w-full rounded border border-gray-300 bg-white px-3 py-2 dark:border-gray-700 dark:bg-gray-950"
              />
              {passwordError && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{passwordError}</p>}
              <div className="mt-4 flex gap-2">
                <button
                  className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                  onClick={unlock}
                >
                  {t("password.submit")}
                </button>
                <Link
                  href={`/${locale}/play`}
                  className="rounded border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
                >
                  {t("backToPlay")}
                </Link>
              </div>
            </div>
          </div>
        </PlayLayout>
      </div>
    );
  }

  return (
    <div className="min-h-dvh overflow-y-auto px-2 py-2">
      <div className="mb-3 rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
        <div className="flex flex-wrap items-center gap-3">
          <Link
            href={`/${locale}/play`}
            className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            {t("backToPlay")}
          </Link>
          <div className="text-sm font-medium">{t("title")}</div>
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-gray-500">
              {t("progress", { done: completedCount, total: batch.length || 25 })}
            </span>
            <button
              className="rounded border border-gray-300 px-2 py-1 text-xs font-medium hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
              onClick={startNewRun}
              title={`Run ID: ${batchRunId}`}
            >
              {t("newRun")}
            </button>
          </div>
        </div>

        {isRunComplete && (
          <div className="mt-3 rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-green-800 dark:text-green-200">
                {t("runComplete.title")}
              </h2>
              <code className="text-xs text-green-600 dark:text-green-400">{batchRunId.slice(0, 8)}…</code>
            </div>
            <p className="mt-1 text-xs text-green-700 dark:text-green-300">
              {t("runComplete.hint", { runId: batchRunId.slice(0, 8) })}
            </p>
            <button
              className="mt-3 rounded bg-green-700 px-3 py-2 text-xs font-medium text-white hover:bg-green-800"
              onClick={startNewRun}
            >
              {t("newRun")}
            </button>
          </div>
        )}

        {loadingBatch ? (
          <p className="mt-3 text-sm text-gray-500">{playT("loading")}</p>
        ) : error ? (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
        ) : currentEntry ? (
          <div className="mt-3 grid gap-3 md:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-blue-100 px-2 py-1 text-xs font-semibold text-blue-800 dark:bg-blue-950 dark:text-blue-200">
                  {t("batchBadge", { name: BATCH_NAME })}
                </span>
                <span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-semibold text-gray-700 dark:bg-gray-800 dark:text-gray-200">
                  {t("puzzleIndex", { current: currentIndex + 1, total: batch.length })}
                </span>
                <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                  {currentEntry.difficulty}
                </span>
                {currentEntry.seed != null && (
                  <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
                    {t("seed", { seed: currentEntry.seed })}
                  </span>
                )}
                {currentProgress?.rated && (
                  <span className="rounded-full bg-green-100 px-2 py-1 text-xs font-semibold text-green-800 dark:bg-green-950 dark:text-green-200">
                    {t("rated")}
                  </span>
                )}
                {currentProgress?.abandoned && (
                  <span className="rounded-full bg-red-100 px-2 py-1 text-xs font-semibold text-red-800 dark:bg-red-950 dark:text-red-200">
                    {t("abandoned")}
                  </span>
                )}
              </div>

              {puzzle && (
                <div className="mt-3 grid gap-2 text-sm text-gray-600 dark:text-gray-300 sm:grid-cols-3">
                  <div>{t("metric.score", { value: puzzle.composite_score.toFixed(2) })}</div>
                  <div>{t("metric.branching", { value: puzzle.branching_factor.toFixed(2) })}</div>
                  <div>{t("metric.chain", { value: puzzle.chain_depth })}</div>
                </div>
              )}

              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  className="rounded bg-gray-100 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-100 dark:hover:bg-gray-700"
                  onClick={() => jumpTo(currentIndex - 1)}
                  disabled={currentIndex === 0}
                >
                  {t("previous")}
                </button>
                <button
                  className="rounded bg-gray-100 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-100 dark:hover:bg-gray-700"
                  onClick={() => jumpTo(currentIndex + 1)}
                  disabled={currentIndex >= batch.length - 1}
                >
                  {t("next")}
                </button>
                <button
                  className="rounded bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                  onClick={() => void abandonPuzzle()}
                  disabled={submitting || !puzzle}
                >
                  {t("abandonButton")}
                </button>
              </div>
            </div>

            <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
              <h2 className="text-sm font-semibold">{t("ratingTitle")}</h2>
              <div className="mt-3 grid gap-3">
                <label className="grid gap-1 text-sm">
                  <span>{t("selfRating")}</span>
                  <input
                    type="range"
                    min={1}
                    max={10}
                    value={selfRating}
                    onChange={(e) => setSelfRating(Number(e.target.value))}
                  />
                  <span className="text-xs text-gray-500">{selfRating}/10</span>
                </label>

                <label className="grid gap-1 text-sm">
                  <span>{t("selfLabel")}</span>
                  <select
                    value={selfLabel}
                    onChange={(e) => setSelfLabel(e.target.value as TelemetrySelfLabel)}
                    className="rounded border border-gray-300 bg-white px-2 py-2 dark:border-gray-700 dark:bg-gray-950"
                  >
                    <option value="trivial">{t("labels.trivial")}</option>
                    <option value="straightforward">{t("labels.straightforward")}</option>
                    <option value="challenging">{t("labels.challenging")}</option>
                    <option value="brutal">{t("labels.brutal")}</option>
                  </select>
                </label>

                <label className="grid gap-1 text-sm">
                  <span>{t("stuckMomentsAuto")}</span>
                  <div className="rounded border border-gray-300 bg-gray-50 px-2 py-2 text-sm dark:border-gray-700 dark:bg-gray-950">
                    {stuckMoments}
                  </div>
                </label>

                <label className="grid gap-1 text-sm">
                  <span>{t("notes")}</span>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    rows={4}
                    className="rounded border border-gray-300 bg-white px-2 py-2 dark:border-gray-700 dark:bg-gray-950"
                  />
                </label>

                <button
                  className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  onClick={() => void submitRating()}
                  disabled={submitting || !puzzle || !isSolved}
                >
                  {isSolved ? t("submitRating") : t("solveFirst")}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <PlayLayout>
        <div
          style={{ gridArea: "controls" }}
          className="flex flex-col gap-2 border-b px-2 py-2"
        >
        <ControlBar />
        </div>

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
            {playT("loadPuzzlePrompt")}
          </div>
        )}

        <PlayRack />
        <SolvedBanner />
      </PlayLayout>
    </div>
  );
}
