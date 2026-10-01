import type { ReactElement } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EstateStatStrip } from "./components/EstateStatStrip";
import { AttackPathBanner } from "./components/AttackPathBanner";
// Track 2's real components (findings/components/), swapped in for this
// track's own placeholders per
// plans/frontend-01-ingestion-campaigns-estate.md §3 M4 — the placeholders
// (estate/components/FindingCard.tsx, SystemicFindingBanner.tsx) have been
// deleted now that EstateGridPage/DeviceDetailPage import these instead.
import { SystemicFindingBanner } from "../findings/components/SystemicFindingBanner";
import { FindingCard } from "../findings/components/FindingCard";
import type { FindingModel } from "../findings/types";
import { UnauditedCapabilityBox } from "./components/UnauditedCapabilityBox";
import { EstateGridPage } from "./pages/EstateGridPage";
import { criticalWeightedExposureScore, sortDevicesLocally } from "./hooks/useEstateDevices";
import { ESTATE_FIXTURE_DEVICES } from "./fixtures";

function renderWithProviders(ui: ReactElement, initialEntries: string[] = ["/estate"]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

const SAMPLE_FINDING: FindingModel = {
  id: "F-001",
  campaign_id: "CMP-TEST-001",
  device_id: "DEV-001",
  hostname: "CORE-SW-01",
  device_platform: "cisco_iosxe",
  control_id: "NSCA-MGMT-002",
  rule_id: "NSCA-MGMT-002",
  title: "Plaintext management protocols",
  description: "Telnet transport is enabled on VTY lines.",
  verdict: "FAIL",
  severity: { base: "HIGH", effective: "CRITICAL", reason: "external" },
  state: "Confirmed",
  rulepack_trust_tier: "CERTIFIED",
  frameworks: [{ framework: "cis", id: "CIS-IOS-1.2.4" }],
  evidence: [
    {
      artifact: "running-config.txt",
      lines: [140, 143],
      highlight: [143],
      excerpt: "transport input telnet ssh",
    },
  ],
  attack_paths: [],
  created_at: "2026-08-01T00:00:00Z",
};

describe("Estate Subsystem", () => {
  it("renders EstateStatStrip with all 4 high-level metrics", () => {
    render(
      <EstateStatStrip
        compliance={0.81}
        coverage={0.89}
        meaningfulRatio={0.67}
        security={0.64}
      />
    );

    expect(screen.getByText("89%")).toBeInTheDocument(); // Coverage
    expect(screen.getByText("81%")).toBeInTheDocument(); // Compliance
    expect(screen.getByText("67%")).toBeInTheDocument(); // Meaningful
    expect(screen.getByText("64%")).toBeInTheDocument(); // Security
  });

  it("renders AttackPathBanner and Track 2's real SystemicFindingBanner callouts", () => {
    const { container } = render(
      <MemoryRouter>
        <AttackPathBanner pathCount={3} criticalFindingCount={6} />
        <SystemicFindingBanner systemicId="SF-004" affectedCount={31} totalGroupCount={40} />
      </MemoryRouter>
    );

    expect(screen.getByText(/3 attack paths reach the core management plane/i)).toBeInTheDocument();
    // The real SystemicFindingBanner splits its heading and count badge
    // across sibling <span>s, so asserting via container.textContent
    // (rather than getByText, which would ambiguously match both the
    // badge span and its parent div) is the robust way to check this.
    expect(container.textContent).toMatch(/SYSTEMIC FINDING SF-004/i);
    expect(container.textContent).toMatch(/31 of 40/);
  });

  it("renders Track 2's real FindingCard with inline EvidenceExcerpt when expanded", () => {
    render(
      <MemoryRouter>
        <FindingCard finding={SAMPLE_FINDING} initialExpanded={true} />
      </MemoryRouter>
    );

    expect(screen.getByText("Plaintext management protocols")).toBeInTheDocument();
    expect(screen.getByText("transport input telnet ssh")).toBeInTheDocument();
  });

  it("renders UnauditedCapabilityBox with contaminated controls", () => {
    render(
      <UnauditedCapabilityBox
        capabilities={[
          {
            path: "services.web_mgmt_8443",
            port: 8443,
            properties: ["listens"],
            controls_contaminated: 6,
            description: "Embedded web management active",
          },
        ]}
      />
    );

    expect(screen.getByText(/Unaudited Surface/i)).toBeInTheDocument();
    expect(screen.getByText(/6 controls downgraded to PASS \(PARTIAL\)/i)).toBeInTheDocument();
  });

  describe("EstateGridPage (coverage-first, exposure-weighted default sort)", () => {
    let fetchSpy: ReturnType<typeof vi.fn>;
    const originalFetch = global.fetch;

    beforeEach(() => {
      // Force the useEstateDevices hook down its fixture-fallback path so
      // the test exercises real render output deterministically, while
      // still asserting on the *request* that was attempted first.
      fetchSpy = vi.fn().mockRejectedValue(new Error("network unavailable in test"));
      global.fetch = fetchSpy as unknown as typeof fetch;
    });

    afterEach(() => {
      global.fetch = originalFetch;
    });

    it("renders Coverage as a first-class column alongside devices", async () => {
      renderWithProviders(<EstateGridPage />);

      expect(screen.getByText("Estate Device Topology")).toBeInTheDocument();
      expect(screen.getByText("Coverage (1st-Class)")).toBeInTheDocument();
      await waitFor(() => expect(screen.getByText("EDGE-FW-01")).toBeInTheDocument());
      expect(screen.getByText("CORE-SW-01")).toBeInTheDocument();
    });

    it("sends the default sort as a real `sort` query param to the API", async () => {
      renderWithProviders(<EstateGridPage />);

      // EstateGridPage now also fires real (stub) attack-paths/systemic
      // requests alongside the device-grid request, so this searches
      // across every call this render made rather than assuming the
      // device-grid fetch is necessarily `calls[0]`.
      await waitFor(() =>
        expect(fetchSpy.mock.calls.some((c) => String(c[0]).includes("group_by=device"))).toBe(true)
      );
      const deviceGridCall = fetchSpy.mock.calls.find((c) => String(c[0]).includes("group_by=device"));
      expect(String(deviceGridCall?.[0])).toContain("sort=critical_weighted_exposure");
    });

    it("defaults to critical-findings-weighted-by-exposure order, not compliance", async () => {
      renderWithProviders(<EstateGridPage />);

      // Wait for the fixture fallback data to render.
      await waitFor(() => expect(screen.getByText("EDGE-FW-01")).toBeInTheDocument());

      const table = screen.getByRole("table");
      const rows = within(table).getAllByRole("row").slice(1); // drop header row
      const knownHostnames = ESTATE_FIXTURE_DEVICES.map((d) => d.hostname);
      const hostnamesInOrder = rows.map(
        (row) => knownHostnames.find((h) => within(row).queryByText(h)) ?? null
      );

      // EDGE-FW-01: internet_facing, 4 critical -> highest weighted score,
      // even though its compliance (68%) is far from the best in the set.
      // DIST-SW-08: 100% compliance / 97% coverage but 0 critical findings
      // must NOT outrank it -- that's the whole point of FR-CMP/estate
      // coverage-first + exposure-weighted default sort.
      const edgeIndex = hostnamesInOrder.indexOf("EDGE-FW-01");
      const distIndex = hostnamesInOrder.indexOf("DIST-SW-08");
      expect(edgeIndex).toBeGreaterThanOrEqual(0);
      expect(distIndex).toBeGreaterThanOrEqual(0);
      expect(edgeIndex).toBeLessThan(distIndex);
    });

    it("persists the chosen sort in the URL so it survives a refresh (not just component state)", async () => {
      renderWithProviders(<EstateGridPage />, ["/estate?sort=compliance_asc"]);

      await waitFor(() =>
        expect(fetchSpy.mock.calls.some((c) => String(c[0]).includes("sort=compliance_asc"))).toBe(true)
      );

      const sortSelect = screen.getByLabelText(/sort by/i) as HTMLSelectElement;
      expect(sortSelect.value).toBe("compliance_asc");
    });
  });

  describe("estate sort weighting function", () => {
    it("weights exposure above raw finding count (unit-level check)", () => {
      const internetFacingLowCount = criticalWeightedExposureScore({
        ...ESTATE_FIXTURE_DEVICES[0],
        exposure: "internet_facing",
        critical_findings_count: 1,
        high_findings_count: 0,
      });
      const isolatedSameCount = criticalWeightedExposureScore({
        ...ESTATE_FIXTURE_DEVICES[0],
        exposure: "isolated",
        critical_findings_count: 1,
        high_findings_count: 0,
      });
      expect(internetFacingLowCount).toBeGreaterThan(isolatedSameCount);
    });

    it("sortDevicesLocally never reorders by compliance when using the default key", () => {
      const sorted = sortDevicesLocally(ESTATE_FIXTURE_DEVICES, "critical_weighted_exposure");
      // The highest-compliance device (DIST-SW-08, 100%) must not be first;
      // the highest-critical/exposure device (EDGE-FW-01) must be.
      expect(sorted[0].hostname).toBe("EDGE-FW-01");
      expect(sorted.find((d) => d.hostname === "DIST-SW-08")).not.toBe(sorted[0]);
    });
  });
});
