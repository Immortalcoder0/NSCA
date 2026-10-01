import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DisputeAdjudicationPage } from "./pages/DisputeAdjudicationPage";

// A real `<Route path=":id/dispute">` wrapper (matching
// `findings/routes.tsx`) so `useParams()` inside the page resolves `id`
// the same way it does in the real app, rather than always falling back to
// the fixture's own `finding_id`.
function renderWithProviders(initialEntries: string[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/findings/:id/dispute" element={<DisputeAdjudicationPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Dispute & Verification Subsystem", () => {
  // DisputeAdjudicationPage now wires a real "Run Real Verification" action
  // (`POST /findings/{id}/dispute`) and a real adjudicate submit
  // (`POST /findings/{id}/adjudicate`), backed by `useDisputeFinding`/
  // `useAdjudicateFinding` mutation hooks — both need a QueryClientProvider
  // in the tree. The switcher's initial/default REFUTED state still comes
  // from the same fixture content as before
  // (`findings/fixtures.ts::DISPUTE_FIXTURE`, moved out of the component
  // but byte-identical), so these assertions are unchanged.
  it("renders REFUTED outcome with counterexample packet and trajectory path", () => {
    renderWithProviders(["/findings/F-001/dispute"]);

    expect(screen.getByText("Dispute & Compensating Control Adjudication")).toBeInTheDocument();
    expect(screen.getByText(/CLAIM REFUTED/i)).toBeInTheDocument();
    // Counterexample renders via the shared EvidenceExcerpt component (same
    // sub-component used by finding detail's graph-derived evidence and the
    // attack path explorer's per-link inspector).
    expect(screen.getByText(/Counterexample Verification Path/i)).toBeInTheDocument();
    expect(screen.getByText("EDGE-FW-01")).toBeInTheDocument();
    expect(screen.getByText(/Based on 389 of 412 devices/i)).toBeInTheDocument();
  });

  it("switches to CONFIRMED and UNVERIFIABLE outcomes cleanly", () => {
    renderWithProviders(["/findings/F-001/dispute"]);

    const confirmedBtn = screen.getByText("CONFIRMED");
    fireEvent.click(confirmedBtn);
    expect(screen.getByText(/CLAIM CONFIRMED/i)).toBeInTheDocument();

    const unverifiableBtn = screen.getByText("UNVERIFIABLE");
    fireEvent.click(unverifiableBtn);
    expect(screen.getByText(/Manual Review Required/i)).toBeInTheDocument();
  });

  describe("submits formal adjudication decision (real POST /findings/{id}/adjudicate)", () => {
    let fetchSpy: ReturnType<typeof vi.fn>;
    const originalFetch = global.fetch;

    beforeEach(() => {
      fetchSpy = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ id: "F-001", control: "NSCA-MGMT-002", verdict: "FAIL", state: "Confirmed" }),
      });
      global.fetch = fetchSpy as unknown as typeof fetch;
    });

    afterEach(() => {
      global.fetch = originalFetch;
    });

    it("posts the real adjudicate decision and confirms in the audit trail", async () => {
      renderWithProviders(["/findings/F-001/dispute"]);

      // Default radio is "Uphold Finding (Reject Defense)" -> the dispute's
      // *claim* is rejected -> real API `decision: "overturned"` (see the
      // naming-inversion comment in DisputeAdjudicationPage.tsx).
      const submitBtn = screen.getByText("Submit Formal Adjudication");
      fireEvent.click(submitBtn);

      expect(await screen.findByText(/Adjudication recorded in audit trail/i)).toBeInTheDocument();
      const requestedUrl = String(fetchSpy.mock.calls[0][0]);
      expect(requestedUrl).toContain("/findings/F-001/adjudicate");
      const requestedBody = JSON.parse(String(fetchSpy.mock.calls[0][1]?.body));
      expect(requestedBody.decision).toBe("overturned");
    });
  });

  describe("real verification action (POST /findings/{id}/dispute)", () => {
    let fetchSpy: ReturnType<typeof vi.fn>;
    const originalFetch = global.fetch;

    beforeEach(() => {
      // Reproduces the real M5 server response this track verified live
      // (curl against CMP-2026Q3-001's seeded EDGE-FW-01/CORE-SW-01
      // estate) — real reachability verification firing via
      // `nsca_engine.api.query_reachability`, not the MGMT-SW-04 local
      // fixture fallback.
      fetchSpy = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          dispute_id: "D-000001",
          finding_id: "F-2026Q3-001-000019",
          type: "compensating_control",
          claim: "test claim",
          verification: {
            result: "REFUTED",
            counterexample: {
              packet: { src: "203.0.113.5", dst: "10.0.20.1", dport: 22, protocol: "tcp" },
              path: [{ node: "ART-25C030", rule: "acl[outside-in] line 14", action: "permit", note: "Trusted-Admins -> Partners -> 0.0.0.0/0" }],
            },
            assumptions: ["ART-4A0054: no inbound ACL on ART-4A0054:interface:GigabitEthernet0/0 — default permit"],
            confidence: "high",
          },
        }),
      });
      global.fetch = fetchSpy as unknown as typeof fetch;
    });

    afterEach(() => {
      global.fetch = originalFetch;
    });

    it("calls the real dispute endpoint for the routed finding id and renders the live result", async () => {
      renderWithProviders(["/findings/F-2026Q3-001-000019/dispute"]);

      const verifyBtn = screen.getByText(/Verify Compensating Control Against Real Estate Graph/i);
      fireEvent.click(verifyBtn);

      expect(await screen.findByText("LIVE RESULT")).toBeInTheDocument();
      const requestedUrl = String(fetchSpy.mock.calls[0][0]);
      expect(requestedUrl).toContain("/findings/F-2026Q3-001-000019/dispute");
    });
  });
});
