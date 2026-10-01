import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CoverageBar } from "./CoverageBar";

describe("CoverageBar Component", () => {
  it("renders empty state when total count is 0", () => {
    render(<CoverageBar breakdown={{}} />);
    expect(screen.getByText(/No assessment data available/i)).toBeInTheDocument();
  });

  it("renders segment counts and legend correctly", () => {
    render(
      <CoverageBar
        breakdown={{
          pass: 80,
          fail: 15,
          unknown: 5,
        }}
      />
    );

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument(); // total
  });
});
