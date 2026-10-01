import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CampaignStatusBadge } from "./components/CampaignStatusBadge";
import { CampaignDeltaView } from "./components/CampaignDeltaView";
import { ScopeResolverSummary } from "./components/ScopeResolverSummary";
import { CampaignCreateModal } from "./components/CampaignCreateModal";
import { CampaignListPage } from "./pages/CampaignListPage";
import { AuthProvider } from "../app/auth-guard";
import type { CampaignComparisonData } from "./types";

describe("Campaign Subsystem", () => {
  it("renders CampaignStatusBadge for all 6 lifecycle stages", () => {
    const { rerender } = render(<CampaignStatusBadge status="Draft" />);
    expect(screen.getByRole("status")).toHaveTextContent("Draft");

    rerender(<CampaignStatusBadge status="Collecting" />);
    expect(screen.getByRole("status")).toHaveTextContent("Collecting");

    rerender(<CampaignStatusBadge status="Assessing" />);
    expect(screen.getByRole("status")).toHaveTextContent("Assessing");

    rerender(<CampaignStatusBadge status="Review" />);
    expect(screen.getByRole("status")).toHaveTextContent("In Review");

    rerender(<CampaignStatusBadge status="Issued" />);
    expect(screen.getByRole("status")).toHaveTextContent("Issued (Immutable)");

    rerender(<CampaignStatusBadge status="Closed" />);
    expect(screen.getByRole("status")).toHaveTextContent("Closed");
  });

  it("renders CampaignDeltaView with causal decomposition categories", () => {
    const mockData: CampaignComparisonData = {
      from: "Q2-2026",
      to: "Q3-2026",
      compliance: { from: 0.78, to: 0.81 },
      decomposition: [
        { cause: "verified_remediation", delta: 0.05, findings: 34 },
        { cause: "framework_version_change", delta: -0.03, detail: "STIG tightened" },
        { cause: "scope_change", delta: 0.01, detail: "12 decommissioned" },
      ],
    };

    render(<CampaignDeltaView data={mockData} />);

    expect(screen.getByText("Audit Period Comparison: Q2-2026 → Q3-2026")).toBeInTheDocument();
    expect(screen.getByText("Verified Remediation")).toBeInTheDocument();
    expect(screen.getByText("+5%")).toBeInTheDocument();
    expect(screen.getByText("Framework Benchmark Update")).toBeInTheDocument();
    expect(screen.getByText("-3%")).toBeInTheDocument();
  });

  it("renders ScopeResolverSummary preview with asset count", () => {
    render(
      <ScopeResolverSummary
        expression="exposure == 'internet_facing'"
        resolvedCount={412}
        totalInventoryCount={500}
      />
    );

    expect(screen.getByText("Scope Resolution Preview")).toBeInTheDocument();
    expect(screen.getByText(/412 of 500 assets in scope/i)).toBeInTheDocument();
    expect(screen.getByText("exposure == 'internet_facing'")).toBeInTheDocument();
  });

  it("toggles a framework selection via keyboard (Space on the checkbox), not just mouse click on the row", () => {
    const handleSubmit = vi.fn();
    render(
      <CampaignCreateModal isOpen={true} onClose={() => {}} onSubmit={handleSubmit} />
    );

    // Previously this checkbox was `onChange={() => {}}` with the toggle
    // wired only to the parent div's onClick, so a keyboard user tabbing
    // to the checkbox and pressing Space could never actually select a
    // framework (the controlled `checked` prop snapped back immediately).
    const isoCheckbox = screen.getByRole("checkbox", {
      name: /ISO\/IEC 27001:2022 Annex A/i,
    }) as HTMLInputElement;

    expect(isoCheckbox.checked).toBe(false);
    isoCheckbox.focus();
    fireEvent.click(isoCheckbox); // jsdom's click on a checkbox toggles + fires onChange, as Space would natively
    expect(isoCheckbox.checked).toBe(true);
  });

  describe("CampaignListPage against the real `GET /campaigns` shape", () => {
    // CampaignListPage now fetches real data via `useCampaigns()`
    // (`shared/api/hooks/useCampaigns.ts`) instead of holding its own mock
    // fixture state, so these tests mock `fetch` directly to exercise that
    // real request/response path end to end, the same pattern
    // estate.test.tsx already uses for EstateGridPage.
    let fetchSpy: ReturnType<typeof vi.fn>;
    const originalFetch = global.fetch;

    afterEach(() => {
      global.fetch = originalFetch;
    });

    function renderListPage() {
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      return render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <AuthProvider>
              <CampaignListPage />
            </AuthProvider>
          </MemoryRouter>
        </QueryClientProvider>
      );
    }

    it("renders campaign cards from the real `{items: [...]}` list response", async () => {
      fetchSpy = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          items: [
            {
              id: "CMP-2026Q3-001",
              name: "Q3-2026 Core Infrastructure Audit",
              status: "Collecting",
              scope: { type: "filter", expression: "exposure == 'internet_facing'" },
              frameworks: [{ framework: "cis", version: "4.1.0" }],
              owner: "p.sharma",
              window: { start: "2026-09-01", end: "2026-09-30" },
              knowledge_pin: {},
            },
          ],
          next_cursor: null,
        }),
      });
      global.fetch = fetchSpy as unknown as typeof fetch;

      renderListPage();

      expect(screen.getByText("Audit Campaigns")).toBeInTheDocument();
      await waitFor(() =>
        expect(screen.getByText("Q3-2026 Core Infrastructure Audit")).toBeInTheDocument()
      );
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/campaigns"),
        expect.anything()
      );
    });

    it("shows an honest empty state when the live database has no campaigns yet", async () => {
      fetchSpy = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: [], next_cursor: null }),
      });
      global.fetch = fetchSpy as unknown as typeof fetch;

      renderListPage();

      await waitFor(() =>
        expect(screen.getByText(/No campaigns yet/i)).toBeInTheDocument()
      );
    });
  });
});
