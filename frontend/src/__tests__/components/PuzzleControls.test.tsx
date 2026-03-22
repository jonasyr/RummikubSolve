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

vi.mock("../../store/game", () => ({
  useGameStore: (selector: (s: object) => unknown) =>
    selector({ isPuzzleLoading: mockIsPuzzleLoading, loadPuzzle: mockLoadPuzzle }),
}));

describe("PuzzleControls", () => {
  beforeEach(() => {
    mockLoadPuzzle.mockReset();
    mockIsPuzzleLoading = false;
  });

  it("renders Easy, Medium, Hard, and Custom difficulty buttons", () => {
    render(<PuzzleControls />);
    expect(screen.getByRole("button", { name: "easy" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "medium" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "hard" })).toBeInTheDocument();
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
    // When loading, the button renders "⟳ loading" (spinner + translated key).
    // Match via accessible-name substring so the test is independent of the
    // spinner character.
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

  it("selecting Custom shows the sets-to-remove stepper", async () => {
    render(<PuzzleControls />);
    // Stepper should not be visible for default (medium) selection.
    expect(screen.queryByLabelText("Decrease sets to remove")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "custom" }));
    expect(screen.getByLabelText("Decrease sets to remove")).toBeInTheDocument();
    expect(screen.getByLabelText("Increase sets to remove")).toBeInTheDocument();
    // Default value is 3.
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("Custom Get Puzzle passes sets_to_remove in the request", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "custom" }));
    // Increment from default 3 → 4.
    await userEvent.click(screen.getByLabelText("Increase sets to remove"));
    await userEvent.click(screen.getByRole("button", { name: "getButton" }));
    expect(mockLoadPuzzle).toHaveBeenCalledWith(
      { difficulty: "custom", sets_to_remove: 4 },
      expect.any(AbortSignal),
    );
  });

  it("stepper − button is disabled at minimum (1) and + at maximum (5)", async () => {
    render(<PuzzleControls />);
    await userEvent.click(screen.getByRole("button", { name: "custom" }));

    const dec = screen.getByLabelText("Decrease sets to remove");
    const inc = screen.getByLabelText("Increase sets to remove");

    // Decrement to 1.
    await userEvent.click(dec); // 2
    await userEvent.click(dec); // 1
    expect(dec).toBeDisabled();
    expect(inc).not.toBeDisabled();

    // Increment to 5.
    await userEvent.click(inc); // 2
    await userEvent.click(inc); // 3
    await userEvent.click(inc); // 4
    await userEvent.click(inc); // 5
    expect(inc).toBeDisabled();
    expect(dec).not.toBeDisabled();
  });
});
