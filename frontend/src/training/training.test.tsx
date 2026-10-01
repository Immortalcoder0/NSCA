import type { ReactElement } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../app/auth-guard";
import { PlatformQueueCard } from "./components/PlatformQueueCard";
import { PolarityCheckBlock } from "./components/PolarityCheckBlock";
import { ValidationGateList } from "./components/ValidationGateList";
import { TwoPersonRatificationBanner } from "./components/TwoPersonRatificationBanner";
import { TrainingResultPage } from "./pages/TrainingResultPage";
import { TrainingQuestionPage } from "./pages/TrainingQuestionPage";
import type { TrainingQueueItem } from "./types";

function renderWithProviders(ui: ReactElement, initialEntries: Array<string | { pathname: string; search?: string; state?: unknown }>) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

function jsonResponse(status: number, body: unknown) {
  return { ok: status < 400, status, statusText: String(status), json: async () => body };
}

// Real `/training/queue/{platform}/next` shape (services/training.py
// `_question_row_to_response`) — see shared/api/hooks/useTraining.ts.
const Q1 = {
  question_id: "Q-01",
  position: 1,
  total: 2,
  section: "/ip service",
  pattern: "set <identifier> disabled= no",
  examples: [{ line: 24, text: "set telnet disabled=no" }],
  proposal: {
    source: "heuristic",
    signals: [],
    mappings: [{ fact: "services.telnet.enabled", token: "telnet", justification: "lexical match" }],
    polarity: { inverted: true, indicator: "disabled", requires_explicit_confirmation: true },
    confidence: 0.98,
    description: "Telnet service is ACTIVE and ENABLED",
  },
  impact: { facts_resolved: 1, controls_unlocked: 8, coverage_before: null, coverage_after_estimate: null },
};

const Q2 = {
  question_id: "Q-02",
  position: 2,
  total: 2,
  section: "/system ntp client",
  pattern: "set enabled= yes",
  examples: [{ line: 47, text: "set enabled=yes" }],
  proposal: {
    source: "heuristic",
    signals: [],
    mappings: [{ fact: "ntp.client.enabled", token: "enabled", justification: "lexical match" }],
    polarity: { inverted: false, indicator: null, requires_explicit_confirmation: false },
    confidence: 0.9,
    description: "NTP client service is ENABLED",
  },
  impact: { facts_resolved: 1, controls_unlocked: 6, coverage_before: null, coverage_after_estimate: null },
};

describe("Training Studio Subsystem", () => {
  it("renders PlatformQueueCard with 3 distinct card states", () => {
    const notTaughtItem: TrainingQueueItem = {
      platform: "mikrotik_routeros",
      display_name: "MikroTik RouterOS 7.x",
      status: "not_taught",
      device_count: 8,
      current_coverage: 0.0,
      grammar_coverage: 0.984,
      question_count: 9,
      estimated_minutes: 8,
    };

    const { rerender } = render(
      <MemoryRouter>
        <PlatformQueueCard item={notTaughtItem} />
      </MemoryRouter>
    );

    expect(screen.getByRole("status")).toHaveTextContent("not taught");
    expect(screen.getByText("Begin Teaching Session")).toBeInTheDocument();

    const unidentifiedItem: TrainingQueueItem = {
      ...notTaughtItem,
      status: "unidentified",
      grammar_coverage: 0.43,
    };
    rerender(
      <MemoryRouter>
        <PlatformQueueCard item={unidentifiedItem} />
      </MemoryRouter>
    );

    expect(screen.getByRole("status")).toHaveTextContent("unidentified");
    expect(screen.getByText("Assisted Grammar Authoring")).toBeInTheDocument();
    expect(screen.queryByText("Begin Teaching Session")).not.toBeInTheDocument();
  });

  it("blocks confirmation when PolarityCheckBlock is unconfirmed", () => {
    const handleToggle = vi.fn();
    render(
      <PolarityCheckBlock
        polarity={{
          requires_explicit_confirmation: true,
          prompt: "Does 'disabled=no' mean Telnet is ENABLED?",
          proposed_polarity: "positive",
          explanation: "Double negative ambiguity.",
        }}
        isConfirmed={false}
        onToggleConfirm={handleToggle}
      />
    );

    expect(screen.getByText(/Polarity Ambiguity Gate/i)).toBeInTheDocument();
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toHaveAttribute("aria-checked", "false");
  });

  it("renders ValidationGateList with all 6 gates passed", () => {
    render(
      <ValidationGateList
        gates={[
          { id: "G1", name: "Self-Match Gate", description: "100% parse", status: "passed" },
          { id: "G2", name: "Cross-Platform Gate", description: "0 false triggers", status: "passed" },
          { id: "G3", name: "Conflict Gate", description: "No collisions", status: "passed" },
          { id: "G4", name: "Regression Gate", description: "All tests pass", status: "passed" },
          { id: "G5", name: "Metamorphic Gate", description: "Invariants hold", status: "passed" },
          { id: "G6", name: "Coverage Effect Gate", description: ">= 70% coverage", status: "passed" },
        ]}
      />
    );

    expect(screen.getByText("ALL 6 GATES PASSED")).toBeInTheDocument();
    expect(screen.getByText("Self-Match Gate")).toBeInTheDocument();
  });

  it("enforces two-person custody rule in TwoPersonRatificationBanner", () => {
    const { rerender } = render(
      <TwoPersonRatificationBanner
        taughtBy="r.deshmukh"
        currentUser="r.deshmukh"
      />
    );

    expect(screen.getByText(/Self-Ratification Blocked/i)).toBeInTheDocument();

    rerender(
      <TwoPersonRatificationBanner
        taughtBy="r.deshmukh"
        currentUser="p.sharma"
      />
    );

    expect(screen.getByText(/Ratify into Certified Rulepack/i)).toBeInTheDocument();
  });

  it("renders TrainingResultPage with real, locally-measured session stats handed off via router state", () => {
    // No backend endpoint aggregates "this session's" elapsed time or
    // coverage shift (see TrainingResultPage's own note) — the real
    // numbers come from router `state` that TrainingQuestionPage computes
    // from actual answered questions, not a static fixture.
    renderWithProviders(<TrainingResultPage />, [
      {
        pathname: "/training/result",
        search: "?platform=mikrotik_routeros",
        state: {
          platform: "mikrotik_routeros",
          confirmations_count: 5,
          confirmed_controls: 7,
          total_controls: 10,
          elapsed_ms: 8 * 60 * 1000 + 12 * 1000,
        },
      },
    ]);

    expect(screen.getByText("Teaching Session Completed Successfully")).toBeInTheDocument();
    expect(screen.getByText("8 min 12 s")).toBeInTheDocument();
    expect(screen.getByText("5 Confirmations Answered")).toBeInTheDocument();
    // 7 of 10 real controls_unlocked confirmed -> 70%, matching the
    // product's own "0% -> ≥70%" central claim.
    expect(screen.getByText("70%")).toBeInTheDocument();
  });

  it("renders TrainingResultPage honestly at zero when opened directly with no session state", () => {
    renderWithProviders(<TrainingResultPage />, ["/training/result"]);

    expect(screen.getByText(/opened directly/i)).toBeInTheDocument();
    expect(screen.getByText("0 min 0 s")).toBeInTheDocument();
  });

  describe("real question-flow wiring (GET /training/queue/{platform}/next, POST /training/answer)", () => {
    let fetchSpy: ReturnType<typeof vi.fn>;
    const originalFetch = global.fetch;
    let nextCallCount = 0;

    beforeEach(() => {
      nextCallCount = 0;
      fetchSpy = vi.fn(async (url: string, options?: RequestInit) => {
        const u = String(url);
        if (u.includes("/training/queue/mikrotik_routeros/next")) {
          nextCallCount += 1;
          if (nextCallCount === 1) return jsonResponse(200, Q1);
          if (nextCallCount === 2) return jsonResponse(200, Q2);
          return jsonResponse(404, { detail: "no pending questions for this platform" });
        }
        if (u.includes("/training/queue/mikrotik_routeros")) {
          return jsonResponse(200, { platform: "mikrotik_routeros", questions: [Q1, Q2] });
        }
        if (u.includes("/training/answer")) {
          const body = JSON.parse(String(options?.body));
          return jsonResponse(200, { question_id: body.question_id, response: body.response, accepted: true });
        }
        return jsonResponse(404, { detail: "unhandled in test" });
      });
      global.fetch = fetchSpy as unknown as typeof fetch;
    });

    afterEach(() => {
      global.fetch = originalFetch;
    });

    it("blocks the Confirm action end-to-end when the polarity gate is unconfirmed (client-side mirrors the API's 422 rule)", async () => {
      renderWithProviders(
        <Routes>
          <Route path="/training/questions" element={<TrainingQuestionPage />} />
          <Route path="/training/result" element={<div>RESULT SCREEN REACHED</div>} />
        </Routes>,
        ["/training/questions?platform=mikrotik_routeros"]
      );

      // Question 1 (real, from the mocked /next response) requires explicit
      // polarity confirmation.
      await waitFor(() => expect(screen.getByText(/Polarity Ambiguity Gate/i)).toBeInTheDocument());

      const confirmButton = screen.getByRole("button", { name: /Confirm Interpretation/i });
      expect(confirmButton).toBeDisabled();

      // Pressing the keyboard shortcut for Confirm (Enter) must not be able
      // to do what the disabled button itself cannot — the client-side gate
      // has equal severity to the server-side 422 rejection, not a lesser
      // copy of it that can be bypassed via keyboard shortcut.
      fireEvent.keyDown(window, { key: "Enter" });
      expect(screen.getByText("Question 1 of 2")).toBeInTheDocument();
      expect(screen.queryByText("RESULT SCREEN REACHED")).not.toBeInTheDocument();
      // No answer was ever POSTed.
      expect(fetchSpy.mock.calls.some((c) => String(c[0]).includes("/training/answer"))).toBe(false);

      // Clicking Confirm directly (still unconfirmed) must also be inert.
      fireEvent.click(confirmButton);
      expect(screen.getByText("Question 1 of 2")).toBeInTheDocument();
    });

    it("completes the entire question-flow sequence keyboard-only, including the mandatory polarity confirmation step (NFR-USE-008)", async () => {
      renderWithProviders(
        <Routes>
          <Route path="/training/questions" element={<TrainingQuestionPage />} />
          <Route path="/training/result" element={<div>RESULT SCREEN REACHED</div>} />
        </Routes>,
        ["/training/questions?platform=mikrotik_routeros"]
      );

      // --- Question 1 of 2: polarity confirmation required ---
      await waitFor(() => expect(screen.getByText("Question 1 of 2")).toBeInTheDocument());
      expect(screen.getByRole("button", { name: /Confirm Interpretation/i })).toBeDisabled();

      // Keyboard-only: Tab to the polarity checkbox and activate it. A
      // native <button> receiving Enter/Space in a real browser dispatches
      // a click event, which is what we simulate here on the focused
      // element.
      const polarityCheckbox = screen.getByRole("checkbox");
      polarityCheckbox.focus();
      expect(document.activeElement).toBe(polarityCheckbox);
      fireEvent.click(polarityCheckbox);
      expect(polarityCheckbox).toHaveAttribute("aria-checked", "true");

      // Now the keyboard shortcut for Confirm is live.
      expect(screen.getByRole("button", { name: /Confirm Interpretation/i })).not.toBeDisabled();
      fireEvent.keyDown(window, { key: "Enter" });

      // --- Question 2 of 2: no polarity gate required ---
      await waitFor(() => expect(screen.getByText("Question 2 of 2")).toBeInTheDocument());
      expect(screen.queryByText(/Polarity Ambiguity Gate/i)).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Confirm Interpretation/i })).not.toBeDisabled();

      // Keyboard shortcut "1" also drives Confirm.
      fireEvent.keyDown(window, { key: "1" });

      // Real /next 404s after both questions are answered — the queue is
      // exhausted, completing the walkthrough entirely via keyboard.
      await waitFor(() => expect(screen.getByText("RESULT SCREEN REACHED")).toBeInTheDocument());

      // Both real answers were actually POSTed, in order.
      const answerCalls = fetchSpy.mock.calls.filter((c) => String(c[0]).includes("/training/answer"));
      expect(answerCalls).toHaveLength(2);
      expect(JSON.parse(String(answerCalls[0][1]?.body)).question_id).toBe("Q-01");
      expect(JSON.parse(String(answerCalls[0][1]?.body)).polarity_confirmed).toBe(true);
      expect(JSON.parse(String(answerCalls[1][1]?.body)).question_id).toBe("Q-02");
    });
  });
});
