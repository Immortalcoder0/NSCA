import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VerdictBadge } from "./VerdictBadge";

describe("VerdictBadge Component", () => {
  it("renders PASS correctly", () => {
    render(<VerdictBadge verdict="PASS" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveTextContent("Pass");
    expect(badge).toHaveAttribute("aria-label", "Verdict: Pass");
  });

  it("renders UNKNOWN distinctly per U3", () => {
    render(<VerdictBadge verdict="UNKNOWN" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveTextContent("Unknown (⊥)");
    expect(badge).toHaveTextContent("?");
  });

  it("renders monochrome print mode with distinct text symbols", () => {
    const { rerender } = render(<VerdictBadge verdict="UNKNOWN" monochromePrint={true} />);
    expect(screen.getByRole("status")).toHaveTextContent("{?}");

    rerender(<VerdictBadge verdict="PASS" monochromePrint={true} />);
    expect(screen.getByRole("status")).toHaveTextContent("[✓]");

    rerender(<VerdictBadge verdict="FAIL" monochromePrint={true} />);
    expect(screen.getByRole("status")).toHaveTextContent("[✗]");
  });

  it("handles normalized strings like 'pass_partial'", () => {
    render(<VerdictBadge verdict="pass_partial" />);
    expect(screen.getByRole("status")).toHaveTextContent("Pass (Partial)");
  });
});
