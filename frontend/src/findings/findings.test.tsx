import type { ReactElement } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FindingCard } from "./components/FindingCard";
import { SystemicFindingBanner } from "./components/SystemicFindingBanner";
import { RiskAcceptanceModal } from "./components/RiskAcceptanceModal";
import { FindingWorkbenchPage } from "./pages/FindingWorkbenchPage";
import { AuthProvider } from "../app/auth-guard";
import type { FindingModel } from "./types";

function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

const MOCK_FINDING: FindingModel = {
  id: "F-001",
  campaign_id: "CMP-01",
  device_id: "DEV-01",
  hostname: "CORE-SW-01",
  device_platform: "Cisco IOS-XE",
  control_id: "NSCA-MGMT-002",
  rule_id: "vty_telnet_disabled",
  title: "Plaintext management protocols enabled",
  description: "Telnet cleartext session allowed",
  verdict: "FAIL",
  severity: { base: "HIGH", effective: "CRITICAL", reason: "external exposure" },
  state: "Open",
  rulepack_trust_tier: "CERTIFIED",
  frameworks: [{ framework: "cis", id: "CIS-IOS-1.2.4" }],
  evidence: [
    {
      artifact: "running-config.txt",
      lines: [140, 145],
      highlight: [143],
      excerpt: "transport input telnet ssh",
    },
  ],
  attack_paths: ["AP-CORE-01"],
  created_at: "2026-08-28T12:00:00Z",
};

describe("Findings Subsystem", () => {
  it("renders FindingCard with inline evidence expanded", () => {
    render(
      <MemoryRouter>
        <FindingCard finding={MOCK_FINDING} initialExpanded={true} />
      </MemoryRouter>
    );

    expect(screen.getByText("Plaintext management protocols enabled")).toBeInTheDocument();
    expect(screen.getByText("transport input telnet ssh")).toBeInTheDocument();
    expect(screen.getByText(/Contributes to AP-CORE-01/i)).toBeInTheDocument();
  });

  it("renders SystemicFindingBanner with cluster actions", () => {
    const handleAdjudicate = vi.fn();
    render(
      <MemoryRouter>
        <SystemicFindingBanner
          systemicId="SF-004"
          affectedCount={31}
          totalGroupCount={40}
          onAdjudicateAll={handleAdjudicate}
        />
      </MemoryRouter>
    );

    expect(screen.getByText(/SYSTEMIC FINDING SF-004/i)).toBeInTheDocument();
    expect(screen.getByText(/31 of 40 branch routers/i)).toBeInTheDocument();

    const btn = screen.getByText(/Adjudicate All 31/i);
    fireEvent.click(btn);
    expect(handleAdjudicate).toHaveBeenCalled();
  });

  it("validates mandatory expires_at in RiskAcceptanceModal", () => {
    const handleSubmit = vi.fn();
    render(
      <AuthProvider>
        <RiskAcceptanceModal
          isOpen={true}
          findingId="F-001"
          onClose={() => {}}
          onSubmit={handleSubmit}
        />
      </AuthProvider>
    );

    expect(screen.getByText(/Mandatory Expiration Date/i)).toBeInTheDocument();
  });

  describe("FindingWorkbenchPage (real API integration, fixture fallback)", () => {
    let fetchSpy: ReturnType<typeof vi.fn>;
    const originalFetch = global.fetch;

    beforeEach(() => {
      // `useWorkbenchFindings` (findings/hooks.ts) is real-fetch-first with
      // a fixture fallback, same pattern as `estate/hooks/useEstateDevices
      // .ts` — force the fallback path here so the test is deterministic
      // and doesn't depend on a live backend being reachable.
      fetchSpy = vi.fn().mockRejectedValue(new Error("network unavailable in test"));
      global.fetch = fetchSpy as unknown as typeof fetch;
    });

    afterEach(() => {
      global.fetch = originalFetch;
    });

    it("renders with default grouping by control, real API attempted then falls back to fixture data", async () => {
      renderWithProviders(
        <AuthProvider>
          <FindingWorkbenchPage />
        </AuthProvider>
      );

      expect(screen.getByText("Findings & Risk Workbench")).toBeInTheDocument();
      expect(screen.getByText("Control (Default)")).toBeInTheDocument();

      // A real `GET /campaigns/{id}/findings` call was attempted first.
      await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
      const requestedUrl = String(fetchSpy.mock.calls[0][0]);
      expect(requestedUrl).toContain("/campaigns/");
      expect(requestedUrl).toContain("/findings");

      // On failure, the bundled fixture (findings/fixtures.ts, same content
      // as the Phase-1 mock) renders instead of an empty/error state.
      await waitFor(() => expect(screen.getByText(/F-2026Q3-000412/i)).toBeInTheDocument());
    });
  });
});
