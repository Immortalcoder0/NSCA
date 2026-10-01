import React, { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Pin, Loader2, AlertTriangle, Info } from "lucide-react";
import { ValidationGateList } from "../components/ValidationGateList";
import { TwoPersonRatificationBanner } from "../components/TwoPersonRatificationBanner";
import { RequireRole, useAuth } from "../../app/auth-guard";
import { prettyPlatformName } from "../lib/prettyPlatformName";
import { useTrainingRules, useRatifyRule, useRejectRule, type TrainingRuleSummary } from "../../shared/api/hooks";
import type { ValidationGateItem } from "../types";

// GET /training/rules (learning/ratification.py:list_rules ->
// `_row_to_response`) does NOT expose the per-gate breakdown that
// `learning/validation_gates.py` actually computed — only the fact that a
// provisional rule exists (which, per `save_provisional`'s structural
// invariant, is only possible when `gates_passed=True`). This renders the
// canonical six gates as "passed" because that single boolean fact is
// real and provably true for every persisted provisional rule, not because
// per-gate telemetry was fetched — flagged here and in the M6 report
// rather than papered over.
const CANONICAL_GATE_NAMES: Array<{ id: string; name: string; description: string }> = [
  { id: "GATE-01", name: "Self-Match Gate", description: "Parse/match coverage against the confirmed training examples." },
  { id: "GATE-02", name: "Cross-Platform Generalization Gate", description: "No false-positive triggers on other platforms' corpora." },
  { id: "GATE-03", name: "Grammar Conflict Gate", description: "No AST node overlap with certified standard rulepacks." },
  { id: "GATE-04", name: "Regression Gate", description: "Existing baseline extractor tests still pass." },
  { id: "GATE-05", name: "Metamorphic Testing Gate", description: "Whitespace/comment/token permutations parse invariantly." },
  { id: "GATE-06", name: "Coverage Effect Gate", description: "Estate-wide coverage effect of adding this rule." },
];

function ruleToGateItems(rule: TrainingRuleSummary): ValidationGateItem[] {
  return CANONICAL_GATE_NAMES.map((g) => ({
    id: g.id,
    name: g.name,
    description: g.description,
    status: "passed",
    details: `Enforced before save — a provisional rule cannot be persisted unless all gates passed (learning/ratification.py:save_provisional). Per-gate detail for ${rule.id} is not exposed by GET /training/rules.`,
  }));
}

export const TrainingRatifyPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const platform = searchParams.get("platform") || "";
  const { user } = useAuth();

  const rulesQuery = useTrainingRules("provisional");
  const ratifyRule = useRatifyRule();
  const rejectRule = useRejectRule();

  const provisionalRules = useMemo(() => {
    const items = rulesQuery.data?.items ?? [];
    return platform ? items.filter((r) => r.platform === platform) : items;
  }, [rulesQuery.data, platform]);

  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedRuleId && provisionalRules.length > 0) {
      setSelectedRuleId(provisionalRules[0].id);
    }
  }, [provisionalRules, selectedRuleId]);

  const selectedRule = provisionalRules.find((r) => r.id === selectedRuleId) ?? null;
  const gates = selectedRule ? ruleToGateItems(selectedRule) : [];

  const handleRatify = () => {
    if (!selectedRule) return;
    ratifyRule.mutate(selectedRule.id);
  };

  const handleReject = () => {
    if (!selectedRule) return;
    rejectRule.mutate(selectedRule.id);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/training" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Training Studio Queue</span>
        </Link>
        <span>/</span>
        <span className="font-mono text-foreground font-bold">{platform || "all platforms"}</span>
        <span>/</span>
        <span className="font-semibold text-foreground">Rulepack Ratification</span>
      </div>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Rulepack Validation & Two-Person Ratification
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Cryptographic validation gate verification and separation-of-duties ratification for newly taught parsing rules.
        </p>
      </div>

      <div className="p-3 rounded-lg border border-sky-300 dark:border-sky-800 bg-sky-50/60 dark:bg-sky-950/30 text-[11px] text-sky-900 dark:text-sky-300 flex items-start gap-2">
        <Info size={14} className="shrink-0 mt-0.5" />
        <span>
          This environment's dev-auth stand-in (<code>nsca_platform/auth/dev_auth.py</code>) has exactly one
          hardcoded identity across every role — the same user always answers questions and would always attempt
          ratification, so the two-person rule below will always show the "blocked" state for rules taught in this
          session. That block is real and server-enforced (a 409 from <code>POST /training/rules/{"{id}"}/ratify</code>
          ), not a UI limitation.
        </span>
      </div>

      {rulesQuery.isLoading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-6 justify-center">
          <Loader2 size={16} className="animate-spin" />
          <span>Loading provisional rules…</span>
        </div>
      )}

      {rulesQuery.isError && (
        <div className="p-4 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300 flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>Failed to load provisional rules.</span>
        </div>
      )}

      {!rulesQuery.isLoading && !rulesQuery.isError && provisionalRules.length === 0 && (
        <div className="p-6 rounded-xl border border-border/80 bg-card text-xs text-muted-foreground text-center">
          No provisional rules are pending ratification
          {platform ? ` for ${prettyPlatformName(platform)}` : ""} yet. Confirm at least one training question first.
        </div>
      )}

      {provisionalRules.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {provisionalRules.map((r) => (
            <button
              key={r.id}
              onClick={() => setSelectedRuleId(r.id)}
              className={`px-3 py-1.5 rounded-md text-[11px] font-mono font-semibold border transition-colors ${
                selectedRuleId === r.id
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-secondary text-foreground border-border hover:bg-secondary/80"
              }`}
            >
              {r.id}
            </button>
          ))}
        </div>
      )}

      {selectedRule && (
        <>
          {/* Rulepack Metadata Block */}
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
              <div className="flex items-center gap-2">
                <Pin size={15} className="text-primary" />
                <span className="font-mono font-bold text-foreground">{selectedRule.extractor_id}</span>
                <span className="font-mono text-muted-foreground text-[11px]">v{selectedRule.version}</span>
              </div>
              <span className="px-2 py-0.5 rounded bg-purple-100 dark:bg-purple-950/80 font-mono font-bold text-[10px] text-purple-900 dark:text-purple-300">
                {selectedRule.status.toUpperCase()} → RATIFIED (PENDING)
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Taught By</span>
                <span className="font-mono font-bold text-foreground">{selectedRule.taught_by}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Target Platform</span>
                <span className="font-mono text-foreground">{selectedRule.platform}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Source Artifact</span>
                <span className="font-mono text-foreground">{selectedRule.source_artifact}</span>
              </div>
            </div>
          </div>

          {/* Gate Checklist */}
          <ValidationGateList gates={gates} />

          {(ratifyRule.isError || rejectRule.isError) && (
            <div className="p-3 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300">
              {(ratifyRule.error instanceof Error && ratifyRule.error.message) ||
                (rejectRule.error instanceof Error && rejectRule.error.message) ||
                "Action failed."}
            </div>
          )}

          {/* Two-Person Ratification Gate */}
          <RequireRole
            roles={["lead_assessor", "platform_administrator"]}
            fallback={
              <div className="p-4 rounded-lg bg-muted border text-xs text-muted-foreground">
                Lead Assessor or Platform Administrator role required to ratify rulepacks into the certified knowledge base.
              </div>
            }
          >
            {ratifyRule.isSuccess && ratifyRule.data?.id === selectedRule.id && ratifyRule.data.status === "ratified" ? (
              <div className="p-5 rounded-xl border border-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 text-xs text-emerald-950 dark:text-emerald-200 flex items-center justify-between shadow-sm">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <CheckCircle2 size={18} className="text-emerald-600" />
                  <span>Rule successfully ratified!</span>
                </div>
                <Link
                  to="/knowledge"
                  className="px-3 py-1.5 rounded-md bg-emerald-700 text-white font-bold hover:bg-emerald-800 transition-colors"
                >
                  View Knowledge Base
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                <TwoPersonRatificationBanner
                  taughtBy={selectedRule.taught_by}
                  currentUser={user.id}
                  onRatify={handleRatify}
                />
                <button
                  onClick={handleReject}
                  disabled={rejectRule.isPending}
                  className="text-[11px] font-semibold text-muted-foreground hover:text-red-600 underline disabled:opacity-50"
                >
                  Reject this candidate rule instead
                </button>
              </div>
            )}
          </RequireRole>
        </>
      )}
    </div>
  );
};
