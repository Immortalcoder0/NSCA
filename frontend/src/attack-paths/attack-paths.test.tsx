import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AttackPathGraph } from "./components/AttackPathGraph";
import { AttackPathPayoffCard } from "./components/AttackPathPayoffCard";
import { AttackPathExplorerPage } from "./pages/AttackPathExplorerPage";
import type { AttackPathModel } from "./types";

const MOCK_PATH: AttackPathModel = {
  id: "AP-CORE-01",
  name: "Perimeter Ingress to Core Distribution Control Plane",
  entry_point: "EDGE-FW-01",
  target_asset: "CORE-SW-01",
  criticality: "CRITICAL",
  length: 2,
  nodes: [
    { id: "n1", hostname: "EDGE-FW-01", ip: "10.0.0.1", role: "Perimeter", zone: "Ext", is_entry: true },
    { id: "n2", hostname: "CORE-SW-01", ip: "10.0.0.2", role: "Core", zone: "Core", is_target: true },
  ],
  links: [
    {
      id: "l1-2",
      source: "n1",
      target: "n2",
      contributing_finding_id: "F-001",
      control_id: "NSCA-MGMT-002",
      finding_title: "Plaintext management enabled",
      severity: "CRITICAL",
      protocol: "Telnet",
      port: 23,
    },
  ],
  payoff: {
    critical_links_count: 1,
    recommended_break_finding_id: "F-001",
    recommended_break_device: "CORE-SW-01",
    unreachable_findings_count: 4,
    cost_estimate: "1 command",
  },
};

describe("Attack Path Subsystem", () => {
  it("renders deterministic Dagre SVG layout with entry and target markers", () => {
    render(<AttackPathGraph path={MOCK_PATH} />);

    expect(screen.getByText("EDGE-FW-01")).toBeInTheDocument();
    expect(screen.getByText("ENTRY POINT")).toBeInTheDocument();
    expect(screen.getByText("CORE-SW-01")).toBeInTheDocument();
    expect(screen.getByText("CORE TARGET")).toBeInTheDocument();
    expect(screen.getByText("NSCA-MGMT-002 (Telnet/23)")).toBeInTheDocument();
  });

  it("computes deterministic node positions for a fixed input (dagre, not force-directed)", () => {
    // TECH-STACK.md §12: dagre was chosen over a force-directed layout
    // specifically because attack paths must render deterministically —
    // the same graph must produce the same coordinates every time, with
    // no simulation, no settling iterations, no randomness. This test is
    // the guarantee: two independent renders of the same fixed chain must
    // place every node at exactly the same (x, y).
    const getNodeTransform = (container: HTMLElement, hostname: string): string => {
      const label = Array.from(container.querySelectorAll("text")).find(
        (el) => el.textContent === hostname
      );
      if (!label) throw new Error(`Node label not found: ${hostname}`);
      const nodeGroup = label.closest("g[transform]");
      if (!nodeGroup) throw new Error(`Node <g transform> not found for: ${hostname}`);
      return nodeGroup.getAttribute("transform") || "";
    };

    const first = render(<AttackPathGraph path={MOCK_PATH} />);
    const firstEntry = getNodeTransform(first.container, "EDGE-FW-01");
    const firstTarget = getNodeTransform(first.container, "CORE-SW-01");
    first.unmount();

    const second = render(<AttackPathGraph path={MOCK_PATH} />);
    const secondEntry = getNodeTransform(second.container, "EDGE-FW-01");
    const secondTarget = getNodeTransform(second.container, "CORE-SW-01");
    second.unmount();

    // Same input, independently rendered — identical coordinates.
    expect(firstEntry).toBe(secondEntry);
    expect(firstTarget).toBe(secondTarget);

    // Structural sanity: top-to-bottom rankdir means the entry node (rank
    // 0) sits strictly above the target node (rank 1) in the same column,
    // for this single-chain fixture.
    const parseTranslate = (transform: string): { x: number; y: number } => {
      const match = transform.match(/translate\(([-\d.]+),\s*([-\d.]+)\)/);
      if (!match) throw new Error(`Unparseable transform: ${transform}`);
      return { x: parseFloat(match[1]), y: parseFloat(match[2]) };
    };
    const entryPos = parseTranslate(firstEntry);
    const targetPos = parseTranslate(firstTarget);
    expect(entryPos.y).toBeLessThan(targetPos.y);
    expect(entryPos.x).toBe(targetPos.x);
  });

  it("renders AttackPathPayoffCard with optimal cut finding and blast radius", () => {
    render(
      <MemoryRouter>
        <AttackPathPayoffCard path={MOCK_PATH} />
      </MemoryRouter>
    );

    expect(screen.getByText(/Optimal Remediation Cut-Point/i)).toBeInTheDocument();
    expect(screen.getByText("F-001")).toBeInTheDocument();
    expect(screen.getByText(/4 Downstream Findings/i)).toBeInTheDocument();
  });

  describe("AttackPathExplorerPage (real API integration)", () => {
    // The page now makes a real `GET /campaigns/{id}/attack-paths` call
    // (`useCampaignAttackPaths`) alongside the local `SAMPLE_ATTACK_PATHS`
    // fixture that actually drives the dagre graph (the real endpoint is
    // verified live to still be the M0 stub — no node/link detail to render
    // a graph from). Needs a `QueryClientProvider` now; fetch is mocked to
    // reject so the test is deterministic without a live backend.
    let fetchSpy: ReturnType<typeof vi.fn>;
    const originalFetch = global.fetch;

    beforeEach(() => {
      fetchSpy = vi.fn().mockRejectedValue(new Error("network unavailable in test"));
      global.fetch = fetchSpy as unknown as typeof fetch;
    });

    afterEach(() => {
      global.fetch = originalFetch;
    });

    it("renders AttackPathExplorerPage with path selector and inspector", async () => {
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <AttackPathExplorerPage />
          </MemoryRouter>
        </QueryClientProvider>
      );

      expect(screen.getByRole("heading", { name: "Attack Path Explorer" })).toBeInTheDocument();
      expect(screen.getByText(/Active Attack Path:/i)).toBeInTheDocument();

      // A real attack-paths call was attempted.
      await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
      expect(String(fetchSpy.mock.calls[0][0])).toContain("/attack-paths");
    });
  });
});
