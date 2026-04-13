import { postTelemetry } from "./api";
import type {
  PuzzleResponse,
  TelemetryEventRequest,
  TelemetryEventType,
  TileInput,
} from "../types/api";

type TelemetryContext = Pick<
  PuzzleResponse,
  | "puzzle_id"
  | "difficulty"
  | "generator_version"
  | "composite_score"
  | "branching_factor"
  | "deductive_depth"
  | "red_herring_density"
  | "working_memory_load"
  | "tile_ambiguity"
  | "solution_fragility"
  | "disruption_score"
  | "chain_depth"
>;

type TelemetryDetails = Omit<
  TelemetryEventRequest,
  | "event_type"
  | "event_at"
  | "puzzle_id"
  | "difficulty"
  | "generator_version"
  | "composite_score"
  | "branching_factor"
  | "deductive_depth"
  | "red_herring_density"
  | "working_memory_load"
  | "tile_ambiguity"
  | "solution_fragility"
  | "disruption_score"
  | "chain_depth"
>;

function toTelemetryTile(tile: TileInput): TileInput {
  return {
    color: tile.color,
    number: tile.number,
    joker: tile.joker,
  };
}

export function buildTelemetryEvent(
  eventType: TelemetryEventType,
  puzzle: TelemetryContext,
  details: TelemetryDetails = {},
): TelemetryEventRequest {
  return {
    event_type: eventType,
    event_at: new Date().toISOString(),
    puzzle_id: puzzle.puzzle_id,
    difficulty: puzzle.difficulty,
    generator_version: puzzle.generator_version,
    composite_score: puzzle.composite_score,
    branching_factor: puzzle.branching_factor,
    deductive_depth: puzzle.deductive_depth,
    red_herring_density: puzzle.red_herring_density,
    working_memory_load: puzzle.working_memory_load,
    tile_ambiguity: puzzle.tile_ambiguity,
    solution_fragility: puzzle.solution_fragility,
    disruption_score: puzzle.disruption_score,
    chain_depth: puzzle.chain_depth,
    ...details,
  };
}

export async function recordTelemetryEvent(
  eventType: TelemetryEventType,
  puzzle: TelemetryContext,
  details: TelemetryDetails = {},
): Promise<void> {
  await postTelemetry(buildTelemetryEvent(eventType, puzzle, details));
}

export { toTelemetryTile };
