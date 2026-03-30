import { describe, it, expect, vi, beforeEach } from "vitest";
import { useGameStore } from "../../store/game";
import type { BoardSetInput, TileInput } from "../../types/api";

// ---------------------------------------------------------------------------
// Mock the API module so loadPuzzle doesn't make real HTTP calls.
// ---------------------------------------------------------------------------
vi.mock("../../lib/api", () => ({
  fetchPuzzle: vi.fn(),
  solvePuzzle: vi.fn(),
}));

// Import after vi.mock so we get the mocked version.
const { fetchPuzzle } = await import("../../lib/api");
const mockFetchPuzzle = fetchPuzzle as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Access Zustand store state directly — no React rendering needed.
const store = () => useGameStore.getState();

const redTile = (n: number): TileInput => ({ color: "red", number: n, joker: false });
const boardSet = (tiles: TileInput[]): BoardSetInput => ({ type: "run", tiles });

beforeEach(() => {
  store().reset();
  mockFetchPuzzle.mockReset();
});

describe("rack actions", () => {
  it("addRackTile appends a tile", () => {
    store().addRackTile(redTile(5));
    expect(store().rack).toHaveLength(1);
    expect(store().rack[0].number).toBe(5);
  });

  it("addRackTile appends multiple tiles", () => {
    store().addRackTile(redTile(5));
    store().addRackTile(redTile(6));
    expect(store().rack).toHaveLength(2);
  });

  it("removeRackTile removes by index", () => {
    store().addRackTile(redTile(5));
    store().addRackTile(redTile(6));
    store().removeRackTile(0);
    expect(store().rack).toHaveLength(1);
    expect(store().rack[0].number).toBe(6);
  });

  it("removeRackTile is no-op on empty rack", () => {
    store().removeRackTile(0);
    expect(store().rack).toHaveLength(0);
  });
});

describe("board set actions", () => {
  it("addBoardSet appends a set", () => {
    store().addBoardSet(boardSet([redTile(4), redTile(5), redTile(6)]));
    expect(store().boardSets).toHaveLength(1);
  });

  it("removeBoardSet removes by index", () => {
    store().addBoardSet(boardSet([redTile(4), redTile(5), redTile(6)]));
    store().addBoardSet(boardSet([redTile(7), redTile(8), redTile(9)]));
    store().removeBoardSet(0);
    expect(store().boardSets).toHaveLength(1);
    expect(store().boardSets[0].tiles[0].number).toBe(7);
  });

  it("updateBoardSet replaces set at index", () => {
    store().addBoardSet(boardSet([redTile(4), redTile(5), redTile(6)]));
    const updated = boardSet([redTile(10), redTile(11), redTile(12)]);
    store().updateBoardSet(0, updated);
    expect(store().boardSets[0].tiles[0].number).toBe(10);
  });

  it("updateBoardSet does not affect other sets", () => {
    store().addBoardSet(boardSet([redTile(4), redTile(5), redTile(6)]));
    store().addBoardSet(boardSet([redTile(7), redTile(8), redTile(9)]));
    store().updateBoardSet(0, boardSet([redTile(1), redTile(2), redTile(3)]));
    expect(store().boardSets[1].tiles[0].number).toBe(7);
  });
});

describe("settings actions", () => {
  it("setIsFirstTurn updates flag", () => {
    expect(store().isFirstTurn).toBe(false);
    store().setIsFirstTurn(true);
    expect(store().isFirstTurn).toBe(true);
  });

  it("setIsBuildingSet updates flag", () => {
    store().setIsBuildingSet(true);
    expect(store().isBuildingSet).toBe(true);
  });
});

describe("async state actions", () => {
  it("setLoading updates isLoading", () => {
    store().setLoading(true);
    expect(store().isLoading).toBe(true);
    store().setLoading(false);
    expect(store().isLoading).toBe(false);
  });

  it("setError stores error string", () => {
    store().setError("something went wrong");
    expect(store().error).toBe("something went wrong");
  });

  it("setError accepts null", () => {
    store().setError("err");
    store().setError(null);
    expect(store().error).toBeNull();
  });

  it("setSolution stores solution", () => {
    // Minimal shape — just verify it is stored
    const fakeSolution = { status: "solved", tiles_placed: 3 } as never;
    store().setSolution(fakeSolution);
    expect(store().solution).not.toBeNull();
  });
});

describe("reset", () => {
  it("clears all state to initial values", () => {
    store().addRackTile(redTile(5));
    store().addBoardSet(boardSet([redTile(4), redTile(5), redTile(6)]));
    store().setIsFirstTurn(true);
    store().setError("oops");
    store().setLoading(true);
    store().reset();
    const s = store();
    expect(s.rack).toHaveLength(0);
    expect(s.boardSets).toHaveLength(0);
    expect(s.isFirstTurn).toBe(false);
    expect(s.error).toBeNull();
    expect(s.isLoading).toBe(false);
    expect(s.solution).toBeNull();
    expect(s.isBuildingSet).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Phase 6: lastPuzzleMeta
// ---------------------------------------------------------------------------

describe("lastPuzzleMeta", () => {
  it("is null in initial state", () => {
    expect(store().lastPuzzleMeta).toBeNull();
  });

  it("is set after loadPuzzle resolves", async () => {
    mockFetchPuzzle.mockResolvedValueOnce({
      board_sets: [],
      rack: [],
      difficulty: "expert",
      tile_count: 0,
      disruption_score: 30,
      chain_depth: 2,
      is_unique: true,
      puzzle_id: "test-uuid",
    });
    await store().loadPuzzle({ difficulty: "expert" });
    expect(store().lastPuzzleMeta).toEqual({
      chainDepth: 2,
      isUnique: true,
      difficulty: "expert",
    });
  });

  it("defaults chainDepth to 0 and isUnique to false when fields are absent", async () => {
    mockFetchPuzzle.mockResolvedValueOnce({
      board_sets: [],
      rack: [],
      difficulty: "easy",
      tile_count: 0,
      disruption_score: 5,
      // chain_depth and is_unique intentionally absent
      puzzle_id: "",
    });
    await store().loadPuzzle({ difficulty: "easy" });
    expect(store().lastPuzzleMeta?.chainDepth).toBe(0);
    expect(store().lastPuzzleMeta?.isUnique).toBe(false);
  });

  it("stores difficulty from the response", async () => {
    mockFetchPuzzle.mockResolvedValueOnce({
      board_sets: [],
      rack: [],
      difficulty: "nightmare",
      tile_count: 0,
      disruption_score: 42,
      chain_depth: 4,
      is_unique: false,
      puzzle_id: "some-id",
    });
    await store().loadPuzzle({ difficulty: "nightmare" });
    expect(store().lastPuzzleMeta?.difficulty).toBe("nightmare");
  });

  it("is cleared by reset()", async () => {
    mockFetchPuzzle.mockResolvedValueOnce({
      board_sets: [],
      rack: [],
      difficulty: "medium",
      tile_count: 0,
      disruption_score: 10,
      chain_depth: 1,
      is_unique: false,
      puzzle_id: "",
    });
    await store().loadPuzzle({ difficulty: "medium" });
    expect(store().lastPuzzleMeta).not.toBeNull();
    store().reset();
    expect(store().lastPuzzleMeta).toBeNull();
  });
});
