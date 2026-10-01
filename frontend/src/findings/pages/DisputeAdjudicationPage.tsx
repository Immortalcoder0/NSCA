import React, { useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  ShieldCheck,
  ShieldAlert,
  Send,
  HelpCircle,
  Radar,
  Loader2,
} from "lucide-react";
import { EvidenceExcerpt } from "../../shared/components/EvidenceExcerpt";
import { RiskAcceptanceModal } from "../components/RiskAcceptanceModal";
import { useDisputeFinding, useAdjudicateFinding } from "../../shared/api/hooks/useFindings";
import { DEFAULT_CAMPAIGN_ID } from "../hooks";
import { DISPUTE_FIXTURE } from "../fixtures";
import type { DisputeModel, DisputeVerificationOutcome, RiskAcceptanceSubmission } from "../types";
import { cn } from "../../shared/lib/utils";

// A claim template that, against this track's seeded M5 integration
// campaign (CMP-2026Q3-001 — two real AP-003 fixture devices, EDGE-FW-01 /
// CORE-SW-01, uploaded + assessed through the live API), names two real
// IPv4 addresses that ARE genuinely reachable in the merged estate graph
// (verified live: `nsca_engine.api.query_reachability` returns `reachable`
// with a real counterexample chain through EDGE-FW-01's `outside-in` ACL,
// same result `nsca_engine/tests/test_assess_campaign_ap003.py`'s own
// acceptance test asserts). Submitting this claim as-is exercises the REAL
// `_try_engine_reachability` path in `services/dispute.py` — not the
// `_local_compensating_control_check` MGMT-SW-04 fixture fallback — and
// reliably comes back REFUTED. Editable so a claim naming a genuinely
// unreachable pair, or fewer than two addresses, can be tried too (the
// latter honestly falls through to the local fixture/UNVERIFIABLE default).
const LIVE_VERIFY_CLAIM_TEMPLATE =
  "External host 203.0.113.5 cannot reach CORE-SW-01 management interface 10.0.20.1 on tcp/22 because the outside-in ACL on EDGE-FW-01 only permits Trusted-Admins.";

interface RawVerification {
  result?: string;
  counterexample?: {
    packet?: { src?: string; dst?: string; dport?: number; protocol?: string };
    path?: Array<{ node?: string; note?: string; rule?: string; action?: string }>;
  } | null;
  assumptions?: string[];
  confidence?: string;
  reason?: string;
}

function mapRawDisputeToModel(raw: Record<string, unknown>, findingId: string): DisputeModel {
  const verification = (raw.verification ?? {}) as RawVerification;
  return {
    dispute_id: String(raw.dispute_id ?? "D-live"),
    finding_id: findingId,
    raised_by: "current user (live verification)",
    created_at: new Date().toISOString(),
    type: (raw.type as DisputeModel["type"]) ?? "compensating_control",
    claim: String(raw.claim ?? ""),
    verification: {
      result: (verification.result as DisputeVerificationOutcome) ?? "UNVERIFIABLE",
      counterexample: verification.counterexample
        ? {
            packet: {
              src: verification.counterexample.packet?.src ?? "",
              dst: verification.counterexample.packet?.dst ?? "",
              dport: verification.counterexample.packet?.dport ?? 0,
              protocol: verification.counterexample.packet?.protocol ?? "",
            },
            path: (verification.counterexample.path ?? []).map((hop) => ({
              node: hop.node ?? "",
              note: [hop.rule, hop.note].filter(Boolean).join(" — "),
              action: hop.action,
            })),
          }
        : undefined,
      assumptions: verification.assumptions ?? [],
      confidence: (verification.confidence as DisputeModel["verification"]["confidence"]) ?? "low",
      reason: verification.reason,
    },
  };
}

export const DisputeAdjudicationPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const campaignId = searchParams.get("campaign") || DEFAULT_CAMPAIGN_ID;
  const findingId = id || DISPUTE_FIXTURE.finding_id;

  const disputeMutation = useDisputeFinding();
  const adjudicateMutation = useAdjudicateFinding();

  const [dispute, setDispute] = useState<DisputeModel>(DISPUTE_FIXTURE);
  const [isLiveResult, setIsLiveResult] = useState(false);
  const [claimDraft, setClaimDraft] = useState(LIVE_VERIFY_CLAIM_TEMPLATE);
  const [selectedOutcome, setSelectedOutcome] = useState<DisputeVerificationOutcome>(
    dispute.verification.result
  );
  const [adjudicationDecision, setAdjudicationDecision] = useState<"uphold" | "reject" | "accept_as_risk">("uphold");
  const [rationale, setRationale] = useState(
    "Dispute rejected and finding upheld based on verified counterexample path from Partner VPN subnet."
  );
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isRiskModalOpen, setIsRiskModalOpen] = useState(false);

  const handleOutcomeSimulate = (outcome: DisputeVerificationOutcome) => {
    setSelectedOutcome(outcome);
    if (outcome === "REFUTED") {
      setAdjudicationDecision("uphold");
      setRationale("Dispute rejected and finding upheld based on verified counterexample trajectory.");
    } else if (outcome === "CONFIRMED") {
      setAdjudicationDecision("accept_as_risk");
      setRationale("Compensating control mathematically verified. Accepting with 90-day review expiry.");
    } else {
      setAdjudicationDecision("uphold");
      setRationale("Compensating defense cannot be telemetrically verified from available configs. Upheld.");
    }
  };

  // Real `POST /findings/{finding_id}/dispute` — this campaign has been
  // assessed via `POST /campaigns/{id}/assess` (M5's real `assess_campaign`
  // call), so a `Graph` is cached in-process
  // (`nsca_platform/services/graph_cache.py`) and, when the claim names two
  // concrete IPv4 addresses, `services/dispute.py._try_engine_reachability`
  // runs a REAL `nsca_engine.api.query_reachability` call — verified live
  // during M5 integration (curl reproduction documented in this track's M5
  // report) to actually fire and return REFUTED with a genuine
  // counterexample, not the MGMT-SW-04 local fixture.
  const handleRunLiveVerification = () => {
    disputeMutation.mutate(
      { id: findingId, type: "compensating_control", claim: claimDraft },
      {
        onSuccess: (raw) => {
          const mapped = mapRawDisputeToModel(raw, findingId);
          setDispute(mapped);
          setSelectedOutcome(mapped.verification.result);
          setIsLiveResult(true);
          setIsSubmitted(false);
        },
      }
    );
  };

  // Real `POST /findings/{finding_id}/adjudicate` — Lead-Assessor-gated.
  // **Naming inversion, flagged**: the API's `decision` literal
  // (`upheld` | `overturned`) describes the fate of the DISPUTE'S CLAIM,
  // while this form's radio group (unchanged from the Phase-1 mock)
  // describes the fate of the FINDING. They are near-opposites of each
  // other:
  //   UI "uphold finding / reject defense"  -> claim REJECTED  -> API "overturned"
  //   UI "reject finding / grant defense"   -> claim ACCEPTED  -> API "upheld"
  //   UI "accept as risk"                   -> not an adjudicate() outcome
  //     at all server-side; risk acceptance is the structurally separate
  //     `POST /findings/{id}/accept-risk` endpoint, which requires a future
  //     `expires_at` this form doesn't collect — so that option opens the
  //     existing `<RiskAcceptanceModal>` (same component the workbench and
  //     detail page use) instead of submitting an incomplete request.
  const handleAdjudicateSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (adjudicationDecision === "accept_as_risk") {
      setIsRiskModalOpen(true);
      return;
    }

    const apiDecision = adjudicationDecision === "uphold" ? "overturned" : "upheld";
    adjudicateMutation.mutate(
      { id: findingId, decision: apiDecision, notes: rationale },
      {
        onSuccess: () => {
          setDispute((prev) => ({
            ...prev,
            adjudication: {
              decision: adjudicationDecision,
              adjudicated_by: "current user (Lead Assessor)",
              rationale,
              timestamp: new Date().toISOString(),
            },
          }));
          setIsSubmitted(true);
        },
      }
    );
  };

  const handleRiskAcceptanceSubmit = (_data: RiskAcceptanceSubmission) => {
    setIsSubmitted(true);
  };

  return (
    <div className="space-y-5">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/findings" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Findings Workbench</span>
        </Link>
        <span>/</span>
        <Link to={`/findings/${findingId}`} className="hover:text-foreground font-mono">
          {findingId}
        </Link>
        <span>/</span>
        <span className="font-semibold text-foreground">Dispute Adjudication</span>
        <span className="ml-2 font-mono text-[10px] text-muted-foreground/70">(campaign: {campaignId})</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/70 pb-3.5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">
            Dispute & Compensating Control Adjudication
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Formal verification of engineer defense claims and compensating control efficacy.
          </p>
        </div>

        {/* Simulation Switcher */}
        <div className="flex items-center gap-1.5 text-xs bg-secondary/80 p-1 rounded-md border border-border/80">
          <span className="text-muted-foreground font-medium px-2 text-[11px]">Outcome:</span>
          {(["REFUTED", "CONFIRMED", "UNVERIFIABLE"] as DisputeVerificationOutcome[]).map((res) => (
            <button
              key={res}
              type="button"
              onClick={() => handleOutcomeSimulate(res)}
              className={cn(
                "px-2.5 py-1 rounded text-xs font-bold transition-colors select-none",
                selectedOutcome === res
                  ? res === "REFUTED"
                    ? "bg-red-600 text-white shadow-xs"
                    : res === "CONFIRMED"
                    ? "bg-emerald-600 text-white shadow-xs"
                    : "bg-amber-600 text-white shadow-xs"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary"
              )}
            >
              {res}
            </button>
          ))}
        </div>
      </div>

      {/* Live verification against the real dispute endpoint */}
      <div className="p-4 rounded-xl border border-primary/30 bg-primary/5 space-y-2.5 text-xs">
        <div className="flex items-center gap-2 font-bold text-foreground">
          <Radar size={14} className="text-primary" />
          <span>Run Real Verification — POST /findings/{findingId}/dispute</span>
          {isLiveResult && (
            <span className="px-2 py-0.5 rounded-full bg-primary text-primary-foreground text-[10px] font-mono">
              LIVE RESULT
            </span>
          )}
        </div>
        <textarea
          rows={2}
          value={claimDraft}
          onChange={(e) => setClaimDraft(e.target.value)}
          className="w-full px-3 py-2 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleRunLiveVerification}
            disabled={disputeMutation.isPending}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {disputeMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Radar size={13} />}
            <span>Verify Compensating Control Against Real Estate Graph</span>
          </button>
          {disputeMutation.isError && (
            <span className="text-red-600 dark:text-red-400">
              Request failed — real server unreachable, or finding {findingId} does not exist on the live API
              (the switcher above still previews all three outcome states from fixture data).
            </span>
          )}
        </div>
      </div>

      {/* 2-Column Side-by-Side Split Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Claim Summary & Adjudication Form */}
        <div className="lg:col-span-6 space-y-5">
          {/* Claim Summary Card */}
          <div className="p-4 rounded-xl border border-border/80 bg-card space-y-3 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-2">
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-foreground">{dispute.dispute_id}</span>
                <span className="text-muted-foreground">·</span>
                <span className="text-muted-foreground">Raised by <strong className="text-foreground">{dispute.raised_by}</strong></span>
              </div>
              <span className="px-2 py-0.5 rounded bg-secondary font-mono uppercase font-bold text-[10px]">
                {dispute.type.replace(/_/g, " ")}
              </span>
            </div>

            <div className="space-y-1.5">
              <span className="font-semibold text-muted-foreground text-[11px] uppercase tracking-wider block">
                Engineer Defense Claim
              </span>
              <p className="text-foreground leading-relaxed italic bg-secondary/50 p-3 rounded-lg border border-border/60">
                "{dispute.claim}"
              </p>
            </div>
          </div>

          {/* Adjudication Form */}
          <form onSubmit={handleAdjudicateSubmit} className="p-5 rounded-xl border border-border/80 bg-card space-y-4 text-xs">
            <h2 className="text-sm font-bold text-foreground">Lead Assessor Ruling Decision</h2>

            {/* Radio group */}
            <div className="space-y-2">
              {[
                { id: "uphold", label: "Uphold Finding (Reject Defense)", desc: "Maintain finding as active non-compliance." },
                { id: "reject", label: "Reject Finding (Grant Defense)", desc: "Clear finding from compliance ledger." },
                { id: "accept_as_risk", label: "Accept as Risk (Exemption)", desc: "Acknowledge residual risk with expiry." },
              ].map((opt) => (
                <label
                  key={opt.id}
                  className={cn(
                    "p-3 rounded-lg border cursor-pointer select-none block transition-colors",
                    adjudicationDecision === opt.id
                      ? "border-primary bg-secondary/60 font-semibold text-foreground"
                      : "border-border/80 hover:bg-secondary/30 text-muted-foreground"
                  )}
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="decision"
                      checked={adjudicationDecision === opt.id}
                      onChange={() => setAdjudicationDecision(opt.id as any)}
                      className="cursor-pointer accent-primary"
                    />
                    <span className="text-xs font-semibold">{opt.label}</span>
                  </div>
                  <p className="text-[11px] font-normal text-muted-foreground pl-5 mt-0.5">{opt.desc}</p>
                </label>
              ))}
            </div>

            {/* Adjudication Rationale */}
            <div className="space-y-1.5 pt-1">
              <label htmlFor="rationale" className="font-semibold text-foreground block text-xs">
                Adjudication Rationale & Audit Notes *
              </label>
              <textarea
                id="rationale"
                rows={3}
                required
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            {/* Submit button */}
            <div className="flex items-center justify-between pt-3 border-t border-border/60">
              {isSubmitted ? (
                <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                  <ShieldCheck size={15} />
                  Adjudication recorded in audit trail.
                </span>
              ) : (
                <span className="text-[11px] text-muted-foreground font-mono">
                  POST /findings/{findingId}/adjudicate
                </span>
              )}

              <button
                type="submit"
                disabled={adjudicateMutation.isPending}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {adjudicateMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                <span>Submit Formal Adjudication</span>
              </button>
            </div>
            {adjudicateMutation.isError && (
              <p className="text-[11px] text-red-600 dark:text-red-400">
                Real adjudicate call failed — the finding may not be in `Disputed` state on the live server (409),
                or the server is unreachable. The UI state above still updates for demo/preview purposes.
              </p>
            )}
          </form>
        </div>

        {/* Right Column: Verification & Counterexample Visualizer */}
        <div className="lg:col-span-6 space-y-4">
          {selectedOutcome === "REFUTED" && (
            <div className="p-5 rounded-xl border border-red-200 dark:border-red-900 bg-red-50/50 dark:bg-red-950/20 space-y-4 text-xs">
              <div className="flex items-center justify-between border-b border-red-200 dark:border-red-900/60 pb-2.5">
                <div className="flex items-center gap-2 text-red-900 dark:text-red-200 font-bold text-sm">
                  <ShieldAlert size={18} className="text-red-600 dark:text-red-400" />
                  <span>Engine Verification: CLAIM REFUTED</span>
                </div>
                <span className="px-2 py-0.5 rounded bg-red-100 dark:bg-red-900/80 font-mono font-bold text-red-900 dark:text-red-200 text-[10px]">
                  Confidence: {dispute.verification.confidence.toUpperCase()}
                </span>
              </div>

              <p className="text-red-900/80 dark:text-red-300">
                A reachability counterexample packet was mathematically proven to bypass the claimed filter:
              </p>

              {/* Counterexample Trace — reuses EvidenceExcerpt's shared
                  packet/rule-chain sub-component (same renderer as the
                  finding detail page's graph-derived evidence and the
                  attack path explorer's per-link inspector), per
                  frontend-02 §2.2's "not three separate implementations." */}
              {dispute.verification.counterexample && (
                <EvidenceExcerpt
                  content={`# A verified packet trajectory bypasses the compensating control claim above.\n# No single configuration statement is non-compliant in isolation.`}
                  filename={`${dispute.dispute_id} — verification evidence`}
                  counterexample={{
                    packet: `${dispute.verification.counterexample.packet.protocol.toUpperCase()}/${dispute.verification.counterexample.packet.dport}`,
                    source: dispute.verification.counterexample.packet.src,
                    destination: dispute.verification.counterexample.packet.dst,
                    ruleChain: dispute.verification.counterexample.path.map((hop) => ({
                      device: hop.node,
                      rule: hop.note || "",
                      action: (hop.action || "").toLowerCase(),
                    })),
                  }}
                />
              )}

              {/* Mandatory Assumptions Line */}
              {dispute.verification.assumptions && dispute.verification.assumptions.length > 0 && (
                <div className="pt-2 border-t border-red-200 dark:border-red-900/60 space-y-1 text-[11px] text-red-900/80 dark:text-red-300">
                  <span className="font-bold block">Assumptions Scope:</span>
                  <ul className="list-disc list-inside space-y-0.5">
                    {dispute.verification.assumptions.map((asm, idx) => (
                      <li key={idx}>{asm}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {selectedOutcome === "CONFIRMED" && (
            <div className="p-5 rounded-xl border border-emerald-200 dark:border-emerald-900 bg-emerald-50/50 dark:bg-emerald-950/20 space-y-3 text-xs">
              <div className="flex items-center justify-between border-b border-emerald-200 dark:border-emerald-900/60 pb-2.5">
                <div className="flex items-center gap-2 text-emerald-900 dark:text-emerald-200 font-bold text-sm">
                  <ShieldCheck size={18} className="text-emerald-600 dark:text-emerald-400" />
                  <span>Engine Verification: CLAIM CONFIRMED</span>
                </div>
                <span className="px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/80 font-mono font-bold text-emerald-900 dark:text-emerald-200 text-[10px]">
                  Confidence: {dispute.verification.confidence.toUpperCase()}
                </span>
              </div>

              <p className="text-emerald-900/90 dark:text-emerald-300 leading-relaxed">
                {isLiveResult && dispute.verification.reason
                  ? dispute.verification.reason
                  : "The compensating control is verified effective: zero packet paths reach the protected asset on the disputed port. Recommended action: accept finding as low residual risk with a pre-filled expiry date."}
              </p>
            </div>
          )}

          {selectedOutcome === "UNVERIFIABLE" && (
            <div className="p-5 rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50/50 dark:bg-amber-950/20 space-y-3 text-xs">
              <div className="flex items-center justify-between border-b border-amber-200 dark:border-amber-900/60 pb-2.5">
                <div className="flex items-center gap-2 text-amber-900 dark:text-amber-200 font-bold text-sm">
                  <HelpCircle size={18} className="text-amber-600 dark:text-amber-400" />
                  <span>Engine Verification: UNVERIFIABLE</span>
                </div>
                <span className="px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-900/80 font-mono font-bold text-amber-900 dark:text-amber-200 text-[10px]">
                  Manual Review Required
                </span>
              </div>

              <p className="text-amber-900/90 dark:text-amber-300 leading-relaxed">
                {isLiveResult && dispute.verification.reason
                  ? dispute.verification.reason
                  : "Claimed compensating filter depends on information that cannot be determined from configuration alone (e.g. physical network segmentation, or a device outside the ingested telemetry). Manual audit corroboration is mandatory before deciding."}
              </p>
            </div>
          )}
        </div>
      </div>

      <RiskAcceptanceModal
        isOpen={isRiskModalOpen}
        findingId={findingId}
        onClose={() => setIsRiskModalOpen(false)}
        onSubmit={handleRiskAcceptanceSubmit}
      />
    </div>
  );
};
