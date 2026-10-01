import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EvidenceExcerpt } from "./EvidenceExcerpt";

describe("EvidenceExcerpt Component", () => {
  const sampleConfig = `hostname CORE-SW-01
!
interface GigabitEthernet0/1
 ip address 10.1.1.1 255.255.255.0
 enable secret 5 $1$mERr$hx5rVt7rPNoS4wqbXKX7m0
!`;

  it("renders lines with line numbers starting at default or specified offset", () => {
    render(<EvidenceExcerpt content={sampleConfig} startLineNumber={10} />);
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("hostname CORE-SW-01")).toBeInTheDocument();
  });

  it("masks secrets in configuration lines", () => {
    render(<EvidenceExcerpt content={sampleConfig} />);
    expect(screen.getByText("***SECRET_MASKED***")).toBeInTheDocument();
  });

  it("highlights specified line ranges", () => {
    const { container } = render(
      <EvidenceExcerpt
        content={sampleConfig}
        startLineNumber={1}
        highlightLines={{ start: 3, end: 4 }}
      />
    );

    const highlighted = container.querySelectorAll(".border-amber-400");
    expect(highlighted.length).toBe(2);
  });

  it("renders counterexample verification path if provided", () => {
    render(
      <EvidenceExcerpt
        content={sampleConfig}
        counterexample={{
          packet: "10.40.7.19 -> 10.250.0.11:23 TCP",
          ruleChain: [
            {
              device: "EDGE-FW-01",
              rule: "acl outside-in:14",
              action: "permit",
            },
          ],
        }}
      />
    );

    expect(screen.getByText("Counterexample Verification Path")).toBeInTheDocument();
    expect(screen.getByText("10.40.7.19 -> 10.250.0.11:23 TCP")).toBeInTheDocument();
    expect(screen.getByText("EDGE-FW-01")).toBeInTheDocument();
  });
});
