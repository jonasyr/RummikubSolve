import type { TileInput } from "../types/api";
import type { PlacedTile, SetValidation } from "../types/play";

// ── Public API ────────────────────────────────────────────────────────────────

export function validateTileGroup(placed: PlacedTile[]): SetValidation {
  if (placed.length < 3) {
    return { isValid: false, type: null };
    // NOTE: no reason string for <3 tiles — this is "incomplete", not "invalid"
  }

  const tiles = placed.map((p) => p.tile);
  const runResult = validateAsRun(tiles);
  if (runResult.valid) return { isValid: true, type: "run" };

  const groupResult = validateAsGroup(tiles);
  if (groupResult.valid) return { isValid: true, type: "group" };

  return {
    isValid: false,
    type: null,
    reason: runResult.reason ?? groupResult.reason ?? "play.validation.invalid",
  };
}

// ── Internal helpers ──────────────────────────────────────────────────────────

interface ValidationResult {
  valid: boolean;
  reason?: string;
}

function validateAsRun(tiles: TileInput[]): ValidationResult {
  if (tiles.length > 13) return { valid: false, reason: "play.validation.runTooLong" };

  const jokers = tiles.filter((t) => t.joker);
  const nonJokers = tiles.filter((t) => !t.joker);

  if (nonJokers.length === 0) return { valid: true }; // all jokers, structurally valid

  const colors = new Set(nonJokers.map((t) => t.color));
  if (colors.size > 1) return { valid: false, reason: "play.validation.runMixedColors" };

  const numbers = nonJokers.map((t) => t.number!).sort((a, b) => a - b);
  if (new Set(numbers).size < numbers.length) {
    return { valid: false, reason: "play.validation.runDuplicateNumbers" };
  }

  const nMin = numbers[0];
  const nMax = numbers[numbers.length - 1];
  const gaps = nMax - nMin + 1 - numbers.length;
  if (gaps > jokers.length) {
    return { valid: false, reason: "play.validation.runGapsTooLarge" };
  }

  const total = tiles.length;
  const lo = Math.max(1, nMax - total + 1);
  const hi = Math.min(nMin, 14 - total);
  if (lo > hi) return { valid: false, reason: "play.validation.runOutOfRange" };

  return { valid: true };
}

function validateAsGroup(tiles: TileInput[]): ValidationResult {
  if (tiles.length > 4) return { valid: false, reason: "play.validation.groupTooLarge" };

  const jokers = tiles.filter((t) => t.joker);
  const nonJokers = tiles.filter((t) => !t.joker);

  if (nonJokers.length === 0) return { valid: true };

  const numbers = new Set(nonJokers.map((t) => t.number));
  if (numbers.size > 1) return { valid: false, reason: "play.validation.groupMixedNumbers" };

  const colors = nonJokers.map((t) => t.color!);
  if (new Set(colors).size < colors.length) {
    return { valid: false, reason: "play.validation.groupDuplicateColors" };
  }

  if (jokers.length > 4 - new Set(colors).size) {
    return { valid: false, reason: "play.validation.groupTooManyJokers" };
  }

  return { valid: true };
}
