import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrustTierBadge } from "./TrustTierBadge";

describe("TrustTierBadge Component", () => {
  it("renders CERTIFIED tier with correct text", () => {
    render(<TrustTierBadge tier="CERTIFIED" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveTextContent("CERTIFIED");
    expect(badge).toHaveAttribute("aria-label", "Rulepack Trust Tier: Certified Rulepack");
  });

  it("renders SYNTHESIZED tier with correct text", () => {
    render(<TrustTierBadge tier="SYNTHESIZED" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveTextContent("SYNTHESIZED");
  });
});
