import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PlaybookStepCard } from "./components/PlaybookStepCard";
import { DryRunSummaryBox } from "./components/DryRunSummaryBox";
import { RemediationPlaybookPage } from "./pages/RemediationPlaybookPage";
import { RemediationDryRunPage } from "./pages/RemediationDryRunPage";
import type { PlaybookStepModel, RemediationDryRunModel } from "./types";

const MOCK_STEP: PlaybookStepModel = {
  step_number: 1,
  title: "Enforce SSH-Only Transport",
  device_hostname: "CORE-SW-01",
  device_platform: "Cisco IOS-XE 16.12",
  impact: "lockout_risk",
  impact_warning: "Verify SSH key generation. Active Telnet session disconnect risk.",
  commands: ["configure terminal", "line vty 0 4", " transport input ssh"],
  rollback_commands: ["configure terminal", "line vty 0 4", " transport input telnet ssh"],
  precedes_steps: [2],
  findings_resolved: ["F-001"],
};

const MOCK_DRY_RUN: RemediationDryRunModel = {
  playbook_id: "PB-01",
  target_campaign_id: "CMP-01",
  metrics: {
    before_compliance: 0.78,
    after_compliance: 0.83,
    delta: 0.05,
    before_coverage: 0.92,
    after_coverage: 0.92,
    resolved_findings_count: 4,
  },
  newly_failing_controls: [
    {
      control_id: "NSCA-MGMT-009",
      rule_id: "ssh_session_limit",
      title: "VTY concurrent session limit unconfigured",
      severity: "LOW",
      cause_description: "Modifying line vty 0 4 cleared session-limit parameter.",
    },
  ],
  steps: [MOCK_STEP],
};

describe("Remediation & Dry Run Subsystem", () => {
  it("renders PlaybookStepCard with lockout risk warning and rollback commands", () => {
    render(<PlaybookStepCard step={MOCK_STEP} />);

    expect(screen.getByText("Enforce SSH-Only Transport")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("LOCKOUT RISK");
    expect(screen.getByText(/Safety Rollback Script/i)).toBeInTheDocument();
    expect(screen.getByText(/Must precede step 2/i)).toBeInTheDocument();
  });

  it("renders DryRunSummaryBox with newly failing controls warning banner", () => {
    render(<DryRunSummaryBox dryRun={MOCK_DRY_RUN} />);

    expect(screen.getByText("+5% Compliance")).toBeInTheDocument();
    expect(screen.getByText(/Newly Failing Baseline Controls Detected/i)).toBeInTheDocument();
    expect(screen.getByText("NSCA-MGMT-009")).toBeInTheDocument();
  });

  describe("RemediationPlaybookPage / RemediationDryRunPage (real API integration)", () => {
    // Both pages now make a real `GET /findings/{id}/remediation` call
    // (`useFindingRemediation`) alongside the local rich fixtures
    // (`SAMPLE_STEPS`/`DRY_RUN_FIXTURE`) that actually drive rendering —
    // the real endpoint is verified live to still be the M0 stub (two fixed
    // steps, no before/after metrics or newly-failing-control detection).
    // Needs a `QueryClientProvider` now; fetch is mocked to reject so the
    // test is deterministic without a live backend.
    let fetchSpy: ReturnType<typeof vi.fn>;
    const originalFetch = global.fetch;

    beforeEach(() => {
      fetchSpy = vi.fn().mockRejectedValue(new Error("network unavailable in test"));
      global.fetch = fetchSpy as unknown as typeof fetch;
    });

    afterEach(() => {
      global.fetch = originalFetch;
    });

    it("renders RemediationPlaybookPage and RemediationDryRunPage cleanly", () => {
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      const { rerender } = render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <RemediationPlaybookPage />
          </MemoryRouter>
        </QueryClientProvider>
      );
      expect(screen.getByText("Safety-Sequenced Remediation Playbook")).toBeInTheDocument();

      rerender(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <RemediationDryRunPage />
          </MemoryRouter>
        </QueryClientProvider>
      );
      expect(screen.getByText("Pre-Execution Dry-Run Simulation")).toBeInTheDocument();
    });
  });
});
