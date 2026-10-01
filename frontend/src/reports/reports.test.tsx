import type { ReactElement } from "react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UnassessedSectionBox } from "./components/UnassessedSectionBox";
import { ReportVerifyModal } from "./components/ReportVerifyModal";
import { ExportFormatDropdown } from "./components/ExportFormatDropdown";
import { ReportLibraryPage } from "./pages/ReportLibraryPage";
import { ReportViewerPage } from "./pages/ReportViewerPage";

function withQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("Reports Subsystem", () => {
  it("renders UnassessedSectionBox with verbatim closing disclaimer", () => {
    render(
      <UnassessedSectionBox
        determinedPercentage={81}
        undeterminedPercentage={19}
        items={[
          {
            control_id: "CIS-1.1.1",
            title: "Physical chassis tamper locks",
            reason: "Outside config telemetry",
          },
        ]}
      />
    );

    expect(screen.getByText(/Section 6 · Unassessed Controls/i)).toBeInTheDocument();
    expect(screen.getByText("Physical chassis tamper locks")).toBeInTheDocument();
    expect(
      screen.getByText(/This assessment determined 81% of applicable controls/i)
    ).toBeInTheDocument();
  });

  describe("ReportVerifyModal (real POST /reports/{id}/verify)", () => {
    const originalFetch = global.fetch;

    afterEach(() => {
      global.fetch = originalFetch;
    });

    function mockVerifyResponse(body: unknown) {
      const fetchSpy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body });
      global.fetch = fetchSpy as unknown as typeof fetch;
      return fetchSpy;
    }

    it("renders the MATCH outcome from a real verify response", async () => {
      mockVerifyResponse({
        report_id: "REP-01",
        result: "MATCH",
        original_hash: "abc123",
        recomputed_hash: "abc123",
        knowledge_base_identical: true,
      });
      withQueryClient(<ReportVerifyModal isOpen={true} reportId="REP-01" onClose={() => {}} />);

      expect(screen.getByText(/Cryptographic Report Verification/i)).toBeInTheDocument();
      fireEvent.click(screen.getByText("Verify Now"));

      expect(await screen.findByText("VERIFICATION SUCCESSFUL (MATCH)")).toBeInTheDocument();
    });

    it("renders the MISMATCH-with-differing-knowledge-base outcome distinctly from a defect", async () => {
      mockVerifyResponse({
        report_id: "REP-01",
        result: "MISMATCH",
        original_hash: "abc123",
        recomputed_hash: "def456",
        knowledge_base_identical: false,
      });
      withQueryClient(<ReportVerifyModal isOpen={true} reportId="REP-01" onClose={() => {}} />);
      fireEvent.click(screen.getByText("Verify Now"));

      expect(await screen.findByText(/DIFFERING KNOWLEDGE BASE/i)).toBeInTheDocument();
      expect(screen.queryByText(/DEFECT DETECTED/i)).not.toBeInTheDocument();
    });

    it("renders MISMATCH-with-identical-knowledge-base as a loud, distinct defect alert", async () => {
      mockVerifyResponse({
        report_id: "REP-01",
        result: "MISMATCH",
        original_hash: "abc123",
        recomputed_hash: "def456",
        knowledge_base_identical: true,
      });
      withQueryClient(<ReportVerifyModal isOpen={true} reportId="REP-01" onClose={() => {}} />);
      fireEvent.click(screen.getByText("Verify Now"));

      expect(await screen.findByText(/CRITICAL AUDIT INTEGRITY DEFECT DETECTED/i)).toBeInTheDocument();
    });
  });

  it("renders ExportFormatDropdown with OSCAL and PDF options", () => {
    render(<ExportFormatDropdown reportId="REP-01" />);

    const exportBtn = screen.getByRole("button", { name: /Export Report/i });
    fireEvent.click(exportBtn);

    expect(screen.getByText(/Executive & Technical PDF/i)).toBeInTheDocument();
    expect(screen.getByText(/NIST OSCAL Assessment Results/i)).toBeInTheDocument();
  });

  describe("ReportLibraryPage and ReportViewerPage (real GET /reports/{id}, /download?format=json)", () => {
    const originalFetch = global.fetch;

    beforeEach(() => {
      // The library seeds one known report id from localStorage (see
      // reports/lib/knownReportIds.ts) — cleared here so this test is
      // deterministic and doesn't depend on network reachability.
      localStorage.clear();
    });

    afterEach(() => {
      global.fetch = originalFetch;
      localStorage.clear();
    });

    it("renders ReportLibraryPage's empty state cleanly against a real empty GET /reports", async () => {
      const fetchSpy = vi.fn(async (url: string) => {
        const u = String(url);
        if (u.includes("/reports")) {
          return { ok: true, status: 200, json: async () => ({ items: [], next_cursor: null }) };
        }
        return { ok: false, status: 404, statusText: "Not Found", json: async () => ({ detail: "not found" }) };
      });
      global.fetch = fetchSpy as unknown as typeof fetch;

      withQueryClient(
        <MemoryRouter>
          <ReportLibraryPage />
        </MemoryRouter>
      );
      expect(screen.getByText("Compliance Reports Library")).toBeInTheDocument();
      expect(await screen.findByText(/No reports yet/i)).toBeInTheDocument();
    });

    it("renders ReportViewerPage from a real report document response", async () => {
      const doc = {
        report_id: "REP-01",
        mode: "issued",
        generated_at: "2026-08-31T00:00:00Z",
        device: { hostname: "CORE-SW-01", model: null, os_version: "15.2", serials: [], role: null, exposure: null, location: null },
        campaign: { name: "Q3-2026 Core Infrastructure Audit", assessed_at: "2026-08-31T00:00:00Z", assessor: "p.sharma", frameworks: [] },
        inputs: [],
        scores: {
          compliance: { numerator: 6, denominator: 10 },
          coverage: { numerator: 10, denominator: 22 },
          meaningful: { numerator: 6, denominator: 6 },
          security_posture: { numerator: 6, denominator: 22 },
          pass_count: 6, fail_count: 4, unknown_count: 12, not_applicable_count: 14,
          severity_counts: { critical: 1, high: 2, medium: 0, low: 1 },
        },
        findings: [],
        emergent_findings: [],
        unassessed: [{ control_ids: ["NSCA-CRYPTO-001"], cause: "see finding-level unknown_reason", resolution: null }],
        knowledge_base: {
          engine: "unknown",
          rulepack: { id: "unknown", version: "0", trust_tier: "local" },
          control_pack: { id: "unknown", version: "0" },
          frameworks: [],
          schema_registry: "unknown",
        },
        report_hash: "7a6e63b7c535a356",
      };
      const meta = { id: "REP-01", campaign_id: "CMP-2026Q3-002", device: "CORE-SW-01", generated_at: doc.generated_at, formats_available: ["json", "csv", "oscal"], hash: doc.report_hash };
      const manifest = { report_id: "REP-01", generated: doc.generated_at, inputs: [], knowledge_base: { engine: "unknown", rulepacks: [], control_packs: [] }, report_hash: doc.report_hash, statement: "Re-executing with identical inputs and knowledge base versions will produce a byte-identical report." };

      const fetchSpy = vi.fn(async (url: string) => {
        const u = String(url);
        if (u.includes("/download?format=json")) {
          return { ok: true, status: 200, blob: async () => ({ text: async () => JSON.stringify(doc) }) };
        }
        if (u.includes("/manifest")) {
          return { ok: true, status: 200, json: async () => manifest };
        }
        if (u.endsWith("/reports/REP-01")) {
          return { ok: true, status: 200, json: async () => meta };
        }
        return { ok: false, status: 404, statusText: "Not Found", json: async () => ({ detail: "not found" }) };
      });
      global.fetch = fetchSpy as unknown as typeof fetch;

      withQueryClient(
        <MemoryRouter initialEntries={["/reports/REP-01"]}>
          <Routes>
            <Route path="/reports/:id" element={<ReportViewerPage />} />
          </Routes>
        </MemoryRouter>
      );

      expect(await screen.findByText(/SECTION 1 · FORMAL AUDIT IDENTIFICATION/i)).toBeInTheDocument();
      // The real device/campaign identity from the fetched document, not a
      // fixture.
      expect(screen.getByText(/Q3-2026 Core Infrastructure Audit — CORE-SW-01/)).toBeInTheDocument();
      // Section 6 renders with real ratios derived from `scores`.
      expect(screen.getByText(/This assessment determined 45% of applicable controls/i)).toBeInTheDocument();
    });
  });
});
