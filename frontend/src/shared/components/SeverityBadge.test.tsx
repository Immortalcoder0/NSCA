import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeverityBadge } from "./SeverityBadge";

describe("SeverityBadge Component", () => {
  it("renders CRITICAL severity with correct label and attributes", () => {
    render(<SeverityBadge severity="CRITICAL" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveTextContent("Critical");
    expect(badge).toHaveAttribute("aria-label", "Severity: Critical");
  });

  it("renders monochrome print symbols for all severities", () => {
    const { rerender } = render(<SeverityBadge severity="CRITICAL" monochromePrint={true} />);
    expect(screen.getByRole("status")).toHaveTextContent("CRITICAL");
    expect(screen.getByRole("status")).toHaveTextContent("⯃");

    rerender(<SeverityBadge severity="HIGH" monochromePrint={true} />);
    expect(screen.getByRole("status")).toHaveTextContent("HIGH");
    expect(screen.getByRole("status")).toHaveTextContent("◆");

    rerender(<SeverityBadge severity="MEDIUM" monochromePrint={true} />);
    expect(screen.getByRole("status")).toHaveTextContent("MEDIUM");
    expect(screen.getByRole("status")).toHaveTextContent("▲");
  });
});
