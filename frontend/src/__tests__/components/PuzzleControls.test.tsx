import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PuzzleControls from "../../components/PuzzleControls";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

// Allow tests to control these values before each render.
const mockLoadPuzzle = vi.fn();
let mockIsPuzzleLoading = false;
let mockLastPuzzleMeta: {
  chainDepth: number;
  isUnique: boolean;
  difficulty: string;
} | null = null;

vi.mock("../../store/game", () => ({
  useGameStore: (selector: (s: object) => unknown) =>
    selector({
      isPuzzleLoading: mockIsPuzzleLoading,
      loadPuzzle: mockLoadPuzzle,
      lastPuzzleMeta: mockLastPuzzleMeta,
      error: null,
    }),
}));

describe("PuzzleControls", () => {
  beforeEach(() => {
    mockLoadPuzzle.mockReset();
    mockIsPuzzleLoading = false;
    mockLastPuzzleMeta = null;
  });

  it("renders Easy, Medium, Hard, Expert, Nightmare, and Custom difficulty buttons", () => {
    render(<PuzzleControls />);
    expect(screen.getByRole("button", { name: "easy" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "medium" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "hard" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "expert" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "nightmare" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "custom" })).toBeInTheDocument();
  });

  it("medium is selected by default (has bg-blue-600 class)", () => {
    render(<PuzzleControls />);
    expect(screen.getByRole("button", { name: "medium" }).className).toContain(
      "bg-blue-600",
    );
  });

  it("unselected difficulty buttons do not have bg-blue-600", () => {
    render(<PuzzleControls />);
    expect(screen.getByRole("button", { name: "easy" }).className).not.toContain(
      "bg-blue-600",
    );
    expect(screen.getByRole("button", { name: "hard" }).className).not.toContain(
      "bg-blue-600",
    );
  });

  it("clicking a difficulty button selects it", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "hard" }));
    expect(screen.getByRole("button", { name: "hard" }).className).toContain(
      "bg-blue-600",
    );
    expect(screen.getByRole("button", { name: "medium" }).className).not.toContain(
      "bg-blue-600",
    );
  });

  it("Get Puzzle button is disabled while isPuzzleLoading is true", () => {
    mockIsPuzzleLoading = true;
    render(<PuzzleControls />);
    expect(screen.getByRole("button", { name: /loading/i })).toBeDisabled();
  });

  it("Get Puzzle button calls loadPuzzle with selected difficulty as request object", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "getButton" }));
    expect(mockLoadPuzzle).toHaveBeenCalledOnce();
    expect(mockLoadPuzzle).toHaveBeenCalledWith(
      { difficulty: "medium" },
      expect.any(AbortSignal),
    );
  });

  it("clicking Easy then Get Puzzle calls loadPuzzle with { difficulty: 'easy' }", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "easy" }));
    await userEvent.click(screen.getByRole("button", { name: "getButton" }));
    expect(mockLoadPuzzle).toHaveBeenCalledWith(
      { difficulty: "easy" },
      expect.any(AbortSignal),
    );
  });

  // Phase 6: Nightmare difficulty
  it("clicking Nightmare selects it", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "nightmare" }));
    expect(screen.getByRole("button", { name: "nightmare" }).className).toContain("bg-blue-600");
    expect(screen.getByRole("button", { name: "medium" }).className).not.toContain("bg-blue-600");
  });

  it("clicking Nightmare then Get Puzzle calls loadPuzzle with nightmare difficulty", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "nightmare" }));
    await userEvent.click(screen.getByRole("button", { name: "getButton" }));
    expect(mockLoadPuzzle).toHaveBeenCalledWith(
      { difficulty: "nightmare" },
      expect.any(AbortSignal),
    );
  });

  // Phase 6: Stats badge
  it("stats badge is not shown when lastPuzzleMeta is null", () => {
    render(<PuzzleControls />);
    expect(screen.queryByText(/chainDepth/)).not.toBeInTheDocument();
  });

  it("stats badge shows chain depth when lastPuzzleMeta is set", () => {
    mockLastPuzzleMeta = { chainDepth: 3, isUnique: false, difficulty: "expert" };
    render(<PuzzleControls />);
    expect(screen.getByText(/chainDepth/)).toBeInTheDocument();
  });

  it("stats badge shows uniqueSolution indicator when isUnique is true", () => {
    mockLastPuzzleMeta = { chainDepth: 2, isUnique: true, difficulty: "nightmare" };
    render(<PuzzleControls />);
    expect(screen.getByText(/uniqueSolution/)).toBeInTheDocument();
  });

  it("stats badge does not show uniqueSolution when isUnique is false", () => {
    mockLastPuzzleMeta = { chainDepth: 1, isUnique: false, difficulty: "hard" };
    render(<PuzzleControls />);
    expect(screen.queryByText(/uniqueSolution/)).not.toBeInTheDocument();
  });

  // Phase 7a: Custom mode parameter panel
  it("selecting Custom shows the custom parameter panel", async () => {
    render(<PuzzleControls />);
    // Panel should not be visible for default (medium) selection
    expect(screen.queryByLabelText("Decrease sets to sacrifice")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "custom" }));
    expect(screen.getByLabelText("Decrease sets to sacrifice")).toBeInTheDocument();
    expect(screen.getByLabelText("Decrease min board sets")).toBeInTheDocument();
    expect(screen.getByLabelText("Decrease min chain depth")).toBeInTheDocument();
    expect(screen.getByLabelText("Decrease min disruption")).toBeInTheDocument();
  });

  it("sets-to-sacrifice stepper − is disabled at min (1) and + at max (8)", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "custom" }));

    const dec = screen.getByLabelText("Decrease sets to sacrifice");
    const inc = screen.getByLabelText("Increase sets to sacrifice");

    // Decrement to 1
    await userEvent.click(dec); // 2
    await userEvent.click(dec); // 1
    expect(dec).toBeDisabled();
    expect(inc).not.toBeDisabled();

    // Increment to 8
    for (let i = 0; i < 7; i++) {
      await userEvent.click(inc);
    }
    expect(inc).toBeDisabled();
    expect(dec).not.toBeDisabled();
  });

  it("slow warning is not shown with default custom params", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "custom" }));
    expect(screen.queryByText(/customSlowWarning/)).not.toBeInTheDocument();
  });

  it("uniqueness info note is always shown for custom", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "custom" }));
    expect(screen.getByText(/customUniquenessNote/)).toBeInTheDocument();
  });

  it("custom Get Puzzle sends all custom params", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "custom" }));
    await userEvent.click(screen.getByRole("button", { name: "getButton" }));
    expect(mockLoadPuzzle).toHaveBeenCalledWith(
      expect.objectContaining({
        difficulty: "custom",
        sets_to_remove: expect.any(Number),
        min_board_sets: expect.any(Number),
        max_board_sets: expect.any(Number),
        min_chain_depth: expect.any(Number),
        min_disruption: expect.any(Number),
      }),
      expect.any(AbortSignal),
    );
  });
});
