import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SolutionView from "../../components/SolutionView";
import type { SolveResponse, SetChange, TileWithOrigin } from "../../types/api";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

// ---------------------------------------------------------------------------
// Factories (mirrors SolutionView.test.tsx)
// ---------------------------------------------------------------------------

function makeTile(
  origin: "hand" | number,
  color: TileWithOrigin["color"] = "red",
  number: number | null = 5,
): TileWithOrigin {
  return { color, number, joker: false, copy_id: 0, origin };
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

describe("SolutionView – provenance toggle", () => {
  // ── Default state ─────────────────────────────────────────────────────────

  it("provenance_labels_hidden_by_default", () => {
    const set_changes = [makeSetChange("new", [makeTile("hand"), makeTile(0)])];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    expect(screen.queryByText("originHand")).not.toBeInTheDocument();
    expect(screen.queryByText(/originSet/)).not.toBeInTheDocument();
  });

  // ── Button visibility ─────────────────────────────────────────────────────

  it("provenance_toggle_button_shown_when_set_changes_exist", () => {
    const set_changes = [makeSetChange("new", [makeTile("hand")])];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    expect(
      screen.getByRole("button", { name: /showProvenance/ }),
    ).toBeInTheDocument();
  });

  it("provenance_toggle_button_hidden_when_no_set_changes", () => {
    render(<SolutionView solution={makeSolution({ set_changes: [] })} />);
    expect(
      screen.queryByRole("button", { name: /showProvenance|hideProvenance/ }),
    ).not.toBeInTheDocument();
  });

  // ── Toggle interaction ────────────────────────────────────────────────────

  it("clicking_provenance_toggle_shows_labels", async () => {
    const set_changes = [makeSetChange("extended", [makeTile("hand"), makeTile(0)])];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    await userEvent.click(screen.getByRole("button", { name: /showProvenance/ }));
    expect(screen.getByText("originHand")).toBeInTheDocument();
    expect(screen.getByText('originSet:{"n":1}')).toBeInTheDocument();
  });

  it("clicking_provenance_toggle_twice_hides_labels", async () => {
    const set_changes = [makeSetChange("extended", [makeTile("hand"), makeTile(0)])];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    const btn = screen.getByRole("button", { name: /showProvenance|hideProvenance/ });
    await userEvent.click(btn); // show
    await userEvent.click(btn); // hide
    expect(screen.queryByText("originHand")).not.toBeInTheDocument();
    expect(screen.queryByText(/originSet/)).not.toBeInTheDocument();
  });

  // ── State reset ───────────────────────────────────────────────────────────

  it("provenance_state_resets_on_new_solution", async () => {
    const set_changes = [makeSetChange("new", [makeTile("hand")])];
    const sol1 = makeSolution({ set_changes });
    const sol2 = makeSolution({ set_changes });
    const { rerender } = render(<SolutionView solution={sol1} />);
    await userEvent.click(screen.getByRole("button", { name: /showProvenance/ }));
    expect(screen.getByText("originHand")).toBeInTheDocument();
    rerender(<SolutionView solution={sol2} />);
    expect(screen.queryByText("originHand")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /showProvenance/ }),
    ).toBeInTheDocument();
  });

  // ── Label content ─────────────────────────────────────────────────────────

  it("hand_label_shown_for_hand_origin_tile_when_toggled_on", async () => {
    const set_changes = [makeSetChange("new", [makeTile("hand")])];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    await userEvent.click(screen.getByRole("button", { name: /showProvenance/ }));
    expect(screen.getByText("originHand")).toBeInTheDocument();
  });

  it("set_label_shown_as_one_based_for_origin_zero", async () => {
    const set_changes = [makeSetChange("extended", [makeTile(0)])];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    await userEvent.click(screen.getByRole("button", { name: /showProvenance/ }));
    expect(screen.getByText('originSet:{"n":1}')).toBeInTheDocument();
  });

  it("set_label_shown_as_one_based_for_origin_two", async () => {
    const set_changes = [makeSetChange("rearranged", [makeTile(2)])];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    await userEvent.click(screen.getByRole("button", { name: /showProvenance/ }));
    expect(screen.getByText('originSet:{"n":3}')).toBeInTheDocument();
  });

  it("no_labels_shown_when_toggle_is_off", () => {
    const set_changes = [
      makeSetChange("extended", [makeTile("hand"), makeTile(0), makeTile(2)]),
    ];
    render(<SolutionView solution={makeSolution({ set_changes })} />);
    // Do not click — toggle stays off
    expect(screen.queryByText("originHand")).not.toBeInTheDocument();
    expect(screen.queryByText(/originSet/)).not.toBeInTheDocument();
  });
});
