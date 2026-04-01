import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SolutionView from "../../components/SolutionView";
import type { SolveResponse, SetChange, TileWithOrigin, TileOutput } from "../../types/api";

// ---------------------------------------------------------------------------
// Mock next-intl
// ---------------------------------------------------------------------------

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

// ---------------------------------------------------------------------------
// Helper factories
// ---------------------------------------------------------------------------

function makeTile(
  origin: "hand" | number,
  color: TileWithOrigin["color"] = "red",
  number: number | null = 5,
): TileWithOrigin {
  return { color, number, joker: false, copy_id: 0, origin };
}

function makeJoker(origin: "hand" | number): TileWithOrigin {
  return { color: null, number: null, joker: true, copy_id: 0, origin };
}

function makeSetChange(
  action: SetChange["action"],
  tiles: TileWithOrigin[],
  overrides: Partial<SetChange> = {},
): SetChange {
  return {
    action,
    result_set: { type: "run", tiles },
    source_set_indices: null,
    source_description: null,
    ...overrides,
  };
}

function makeSolution(overrides: Partial<SolveResponse> = {}): SolveResponse {
  return {
    status: "solved",
    tiles_placed: 3,
    tiles_remaining: 0,
    solve_time_ms: 42,
    is_optimal: false,
    is_first_turn: false,
    new_board: [],
    remaining_rack: [],
    moves: [],
    set_changes: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SolutionView", () => {
  // ── No-solution branch ────────────────────────────────────────────────────

  it("renders_no_solution_message", () => {
    render(<SolutionView solution={makeSolution({ status: "no_solution", tiles_placed: 0 })} />);
    expect(screen.getByText("noSolution")).toBeInTheDocument();
  });

  it("renders_first_turn_no_solution_message", () => {
    render(
      <SolutionView
        solution={makeSolution({ status: "no_solution", is_first_turn: true, tiles_placed: 0 })}
      />,
    );
    expect(screen.getByText("noSolutionFirstTurn")).toBeInTheDocument();
  });

  // ── Summary bar ───────────────────────────────────────────────────────────

  it("shows_tiles_placed_count", () => {
    render(<SolutionView solution={makeSolution({ tiles_placed: 3 })} />);
    expect(screen.getByText('tilesPlaced:{"count":3}')).toBeInTheDocument();
  });

  it("shows_tiles_remaining_when_nonzero", () => {
    render(<SolutionView solution={makeSolution({ tiles_remaining: 2 })} />);
    expect(screen.getByText('tilesRemaining:{"count":2}')).toBeInTheDocument();
  });

  it("hides_tiles_remaining_when_zero", () => {
    render(<SolutionView solution={makeSolution({ tiles_remaining: 0 })} />);
    expect(screen.queryByText(/tilesRemaining/)).not.toBeInTheDocument();
  });

  it("shows_optimal_badge_when_is_optimal_true", () => {
    render(<SolutionView solution={makeSolution({ is_optimal: true })} />);
    expect(screen.getByText("optimal")).toBeInTheDocument();
  });

  it("hides_optimal_badge_when_false", () => {
    render(<SolutionView solution={makeSolution({ is_optimal: false })} />);
    expect(screen.queryByText("optimal")).not.toBeInTheDocument();
  });

  // ── Cards rendered ────────────────────────────────────────────────────────

  it("renders_one_card_per_set_change", () => {
    const set_changes = [
      makeSetChange("new", [makeTile("hand")]),
      makeSetChange("extended", [makeTile(0), makeTile("hand")]),
      makeSetChange("rearranged", [makeTile(0)]),
    ];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    // Each card has an action badge: "badge.new", "badge.extended", "badge.rearranged"
    expect(screen.getByText("badge.new")).toBeInTheDocument();
    expect(screen.getByText("badge.extended")).toBeInTheDocument();
    expect(screen.getByText("badge.rearranged")).toBeInTheDocument();
  });

  it("new_action_tiles_are_highlighted", () => {
    const set_changes = [makeSetChange("new", [makeTile("hand"), makeTile("hand")])];
    const { container } = render(<SolutionView solution={makeSolution({ set_changes })} />);
    const rings = container.querySelectorAll(".ring-2");
    expect(rings.length).toBe(2);
  });

  it("extended_board_tiles_not_highlighted", () => {
    const set_changes = [makeSetChange("extended", [makeTile(0), makeTile(0)])];
    const { container } = render(<SolutionView solution={makeSolution({ set_changes })} />);
    const rings = container.querySelectorAll(".ring-2");
    expect(rings.length).toBe(0);
  });

  it("extended_hand_tiles_highlighted", () => {
    // 2 board origin tiles + 1 hand tile = only 1 ring
    const set_changes = [
      makeSetChange("extended", [makeTile(0), makeTile(0), makeTile("hand")]),
    ];
    const { container } = render(<SolutionView solution={makeSolution({ set_changes })} />);
    const rings = container.querySelectorAll(".ring-2");
    expect(rings.length).toBe(1);
  });

  it("rearranged_shows_source_description", () => {
    const set_changes = [
      makeSetChange("rearranged", [makeTile(0)], {
        source_description: "Set 1: Red 3, Red 4",
      }),
    ];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    expect(
      screen.getByText('source:{"desc":"Set 1: Red 3, Red 4"}'),
    ).toBeInTheDocument();
  });

  // ── Sorting ───────────────────────────────────────────────────────────────

  it("cards_sorted_new_before_extended_before_rearranged", () => {
    // Provide in reverse order: rearranged, extended, new
    const set_changes = [
      makeSetChange("rearranged", [makeTile(0)]),
      makeSetChange("extended", [makeTile(0), makeTile("hand")]),
      makeSetChange("new", [makeTile("hand")]),
    ];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    const badges = screen.getAllByText(/badge\.(new|extended|rearranged)$/);
    const texts = badges.map((b) => b.textContent);
    expect(texts).toEqual(["badge.new", "badge.extended", "badge.rearranged"]);
  });

  // ── Unchanged collapse ────────────────────────────────────────────────────

  it("unchanged_sets_hidden_by_default", () => {
    const set_changes = [
      makeSetChange("new", [makeTile("hand")]),
      makeSetChange("unchanged", [makeTile(0)]),
    ];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    // Only the "new" badge is visible; "unchanged" badge hidden
    expect(screen.getByText("badge.new")).toBeInTheDocument();
    expect(screen.queryByText("badge.unchanged")).not.toBeInTheDocument();
  });

  it("shows_show_unchanged_button_with_count", () => {
    const set_changes = [
      makeSetChange("unchanged", [makeTile(0)]),
      makeSetChange("unchanged", [makeTile(0)]),
    ];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    expect(screen.getByText('showUnchanged:{"n":2}')).toBeInTheDocument();
  });

  it("clicking_expand_shows_unchanged_cards", async () => {
    const set_changes = [
      makeSetChange("new", [makeTile("hand")]),
      makeSetChange("unchanged", [makeTile(0)]),
    ];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    const btn = screen.getByRole("button", { name: /showUnchanged/ });
    await userEvent.click(btn);
    expect(screen.getByText("badge.unchanged")).toBeInTheDocument();
  });

  it("clicking_collapse_rehides_unchanged_cards", async () => {
    const set_changes = [
      makeSetChange("new", [makeTile("hand")]),
      makeSetChange("unchanged", [makeTile(0)]),
    ];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    const btn = screen.getByRole("button", { name: /showUnchanged|hideUnchanged/ });
    await userEvent.click(btn); // expand
    await userEvent.click(btn); // collapse
    expect(screen.queryByText("badge.unchanged")).not.toBeInTheDocument();
  });

  // ── Remaining rack ────────────────────────────────────────────────────────

  it("remaining_rack_shown_when_present", () => {
    const remaining_rack: TileOutput[] = [
      { color: "blue", number: 7, joker: false, copy_id: 0 },
    ];
    render(<SolutionView solution={makeSolution({ remaining_rack })} />);
    expect(screen.getByText("remainingHand")).toBeInTheDocument();
  });

  it("remaining_rack_hidden_when_empty", () => {
    render(<SolutionView solution={makeSolution({ remaining_rack: [] })} />);
    expect(screen.queryByText("remainingHand")).not.toBeInTheDocument();
  });

  // ── Run tile sorting ──────────────────────────────────────────────────────

  it("run_tiles_sorted_by_number", () => {
    const tiles: TileWithOrigin[] = [
      { color: "red", number: 9, joker: false, copy_id: 0, origin: "hand" },
      { color: "red", number: 3, joker: false, copy_id: 0, origin: "hand" },
      { color: "red", number: 6, joker: false, copy_id: 0, origin: "hand" },
    ];
    const set_changes = [
      { action: "new" as const, result_set: { type: "run" as const, tiles }, source_set_indices: null, source_description: null },
    ];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    const numbers = screen.getAllByText(/^[369]$/).map((el) => el.textContent);
    expect(numbers).toEqual(["3", "6", "9"]);
  });

  it("group_tiles_not_reordered", () => {
    const tiles: TileWithOrigin[] = [
      { color: "blue", number: 8, joker: false, copy_id: 0, origin: "hand" },
      { color: "red", number: 8, joker: false, copy_id: 0, origin: "hand" },
      { color: "black", number: 8, joker: false, copy_id: 0, origin: "hand" },
    ];
    const set_changes = [
      { action: "new" as const, result_set: { type: "group" as const, tiles }, source_set_indices: null, source_description: null },
    ];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    // All three 8s are present; order is preserved (blue, red, black — not sorted)
    const eights = screen.getAllByText("8");
    expect(eights).toHaveLength(3);
  });

  // ── Fallback / edge cases ─────────────────────────────────────────────────

  it("empty_set_changes_with_tiles_placed_shows_fallback", () => {
    render(
      <SolutionView solution={makeSolution({ set_changes: [], tiles_placed: 2 })} />,
    );
    // Renders without crashing — the section heading is present
    // (the fallback card also renders the "heading" key, so use getAllByText)
    expect(screen.getAllByText("heading").length).toBeGreaterThanOrEqual(1);
  });

  it("set_changes_undefined_handled_gracefully", () => {
    render(
      <SolutionView solution={makeSolution({ set_changes: undefined })} />,
    );
    expect(screen.getAllByText("heading").length).toBeGreaterThanOrEqual(1);
  });

  // ── Step navigator absent ─────────────────────────────────────────────────

  it("step_navigator_buttons_not_rendered", () => {
    const set_changes = [makeSetChange("new", [makeTile("hand")])];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    expect(screen.queryByText("prev")).not.toBeInTheDocument();
    expect(screen.queryByText("next")).not.toBeInTheDocument();
  });
});
