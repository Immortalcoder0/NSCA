import type { ReactElement } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RulepackCoverageReport } from "./components/RulepackCoverageReport";
import { AutomationCoverageManifest } from "./components/AutomationCoverageManifest";
import { FrameworkImpactPreview } from "./components/FrameworkImpactPreview";
import { RulepackListPage } from "./pages/RulepackListPage";
import { FrameworkCatalogPage } from "./pages/FrameworkCatalogPage";
import type { AutomationCoverageManifestData, FrameworkUpdateDiff } from "./types";

describe("Knowledge Base Subsystem", () => {
  it("renders RulepackCoverageReport with AST fact counts and line coverage", () => {
    render(
      <RulepackCoverageReport
        metrics={{
          line_coverage: 0.984,
          facts_producible_count: 142,
          test_fixtures_count: 450,
          unparsed_constructs_count: 3,
        }}
      />
    );

    expect(screen.getByText("98.4%")).toBeInTheDocument();
    expect(screen.getByText("142")).toBeInTheDocument();
    expect(screen.getByText("450")).toBeInTheDocument();
  });

  it("renders AutomationCoverageManifest with full manual-only reason disclosure", () => {
    const mockManifest: AutomationCoverageManifestData = {
      framework_name: "CIS Cisco IOS 15",
      version: "v4.1.0",
      total_controls: 112,
      automated_count: 84,
      manual_only_count: 14,
      data_unavailable_count: 10,
      not_implemented_count: 4,
      manual_only_items: [
        {
          control_id: "CIS-1.1.1",
          framework_id: "CIS-IOS-1.1.1",
          title: "Physical security of device chassis",
          reason: "Physical locks are outside config file telemetry",
          recommended_manual_procedure: "Perform physical facility check",
        },
      ],
    };

    render(<AutomationCoverageManifest manifest={mockManifest} />);

    expect(screen.getByText("84")).toBeInTheDocument();
    expect(screen.getByText("14")).toBeInTheDocument();
    expect(screen.getByText("Physical security of device chassis")).toBeInTheDocument();
    expect(screen.getByText(/Physical locks are outside config file telemetry/i)).toBeInTheDocument();
  });

  it("renders FrameworkImpactPreview with simulated estate impact", () => {
    const mockDiff: FrameworkUpdateDiff = {
      framework: "CIS Cisco IOS 15",
      current_version: "v4.1.0",
      available_version: "v4.2.0",
      release_date: "2026-08-10",
      added_controls_count: 12,
      modified_controls_count: 5,
      withdrawn_controls_count: 2,
      estate_impact: {
        new_findings_predicted: 34,
        severity_tightened_count: 8,
        findings_auto_resolvable: 2,
        net_compliance_delta: -0.03,
      },
    };

    render(<FrameworkImpactPreview diff={mockDiff} />);

    expect(screen.getByText(/Benchmark Update Review/i)).toBeInTheDocument();
    expect(screen.getByText("+34 Findings")).toBeInTheDocument();
    expect(screen.getByText("-3% Net Posture Shift")).toBeInTheDocument();
  });

  describe("RulepackListPage and FrameworkCatalogPage (real GET /knowledge/rulepacks, /frameworks)", () => {
    const originalFetch = global.fetch;

    afterEach(() => {
      global.fetch = originalFetch;
    });

    function mockKnowledgeFetch() {
      const fetchSpy = vi.fn(async (url: string) => {
        const u = String(url);
        if (u.includes("/knowledge/rulepacks") && u.includes("/coverage")) {
          return { ok: true, status: 200, json: async () => ({ rulepack_id: "cisco_iosxe", version: "7.2.1", controls_covered: 154, controls_total: 187, coverage_rate: 0.82 }) };
        }
        if (u.includes("/knowledge/rulepacks")) {
          return { ok: true, status: 200, json: async () => ({ items: [{ id: "cisco_iosxe", version: "7.2.1", trust_tier: "certified", platform: "cisco_iosxe" }] }) };
        }
        if (u.includes("/knowledge/frameworks") && u.includes("/coverage")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              framework: "cis", benchmark: "cisco_ios_15", version: "4.1.0",
              total_recommendations: 187, automated: 154, manual_only: 21, data_unavailable: 7, not_implemented: 5,
              automation_rate: 0.82, manual_only_items: [{ id: "CIS-IOS-1.9.1", reason: "Physical security cannot be determined from configuration" }],
            }),
          };
        }
        if (u.includes("/knowledge/frameworks")) {
          return { ok: true, status: 200, json: async () => ({ items: [{ framework: "cis", benchmark: "cisco_ios_15", version: "4.1.0" }] }) };
        }
        return { ok: false, status: 404, statusText: "Not Found", json: async () => ({ detail: "not found" }) };
      });
      global.fetch = fetchSpy as unknown as typeof fetch;
    }

    function renderWithProviders(ui: ReactElement) {
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      return render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>{ui}</MemoryRouter>
        </QueryClientProvider>
      );
    }

    it("renders RulepackListPage and FrameworkCatalogPage cleanly against real (mocked) API responses", async () => {
      mockKnowledgeFetch();
      const { unmount } = renderWithProviders(<RulepackListPage />);
      expect(screen.getByText("Knowledge Base · Rulepacks")).toBeInTheDocument();
      expect(await screen.findByText("cisco_iosxe")).toBeInTheDocument();
      unmount();

      renderWithProviders(<FrameworkCatalogPage />);
      expect(screen.getByText("Compliance Framework Catalogs")).toBeInTheDocument();
      expect(await screen.findByText(/CIS CISCO_IOS_15/i)).toBeInTheDocument();
    });
  });
});
