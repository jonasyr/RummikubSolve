import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { usePlayStore } from "../../../store/play";
import SolvedBanner from "../../../components/play/SolvedBanner";

// SolvedBanner uses useTranslations — mock next-intl (same pattern as PlayGrid.test.tsx)
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) return `${key}:${JSON.stringify(params)}`;
    return key;
  },
}));

beforeEach(() => {
  usePlayStore.getState().reset();
});

describe("SolvedBanner", () => {
  it("renders nothing when isSolved is false", () => {
    const { container } = render(<SolvedBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the solved message when isSolved is true", () => {
    usePlayStore.setState({ isSolved: true });
    render(<SolvedBanner />);
    expect(screen.getByText("solved")).toBeInTheDocument();
  });

  it("shows elapsed time when both start and end times are set", () => {
    usePlayStore.setState({
      isSolved: true,
      solveStartTime: 0,
      solveEndTime: 30_000, // 30 seconds
    });
    render(<SolvedBanner />);
    // The mock renders "solveTime:{"time":"30s"}"
    expect(screen.getByText(/30s/)).toBeInTheDocument();
  });
});
