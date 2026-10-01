import React, { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Play,
  Download,
  AlertTriangle,
} from "lucide-react";
import { DryRunSummaryBox } from "../components/DryRunSummaryBox";
import { PlaybookStepCard } from "../components/PlaybookStepCard";
import { useFindingRemediation } from "../../shared/api/hooks/useRemediation";
import type { RemediationDryRunModel } from "../types";

const DEFAULT_DEMO_FINDING_ID = "F-2026Q3-001-000019";

const DRY_RUN_FIXTURE: RemediationDryRunModel = {
  playbook_id: "PB-2026Q3-01",
  target_campaign_id: "CMP-2026Q3-001",
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
      rule_id: "cisco_ios_ssh_vty_session_limit",
      title: "VTY concurrent session limit unconfigured after transport restriction",
      severity: "LOW",
      cause_description: "Modifying line vty 0 4 transport input to SSH cleared the previous legacy session-limit parameter. Add 'session-limit 4' to resolve.",
    },
  ],
  steps: [
    {
      step_number: 1,
      title: "Enforce SSH-Only Transport on VTY Lines",
      device_hostname: "CORE-SW-01",
      device_platform: "Cisco IOS-XE 16.12",
      impact: "lockout_risk",
      impact_warning: "Verify SSH key generation. Severance risk for active telnet sessions.",
      commands: [
        "configure terminal",
        "line vty 0 4",
        " transport input ssh",
        "end",
      ],
      rollback_commands: [
        "configure terminal",
        "line vty 0 4",
        " transport input telnet ssh",
        "end",
      ],
      findings_resolved: ["F-2026Q3-000412"],
    },
  ],
};

export const RemediationDryRunPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const findingId = searchParams.get("finding") || DEFAULT_DEMO_FINDING_ID;

  // Real network call: `GET /findings/{id}/remediation` — same endpoint the
  // playbook page calls, whose `dry_run` field is a fixed
  // `{result: "no_lockout_detected", confidence: "high"}` for every finding
  // (verified live against the M5 server). The real dry-run engine
  // (`nsca_platform/remediation/dry_run.py` — before/after compliance,
  // newly-failing-control detection) exists but isn't wired to any route.
  // `DRY_RUN_FIXTURE` below (Phase 1's richer fixture, with the
  // newly-failing-control this screen exists to warn about) drives the
  // actual rendering; the raw stub `dry_run` result is shown transparently.
  const { data: rawRemediation, isLoading: isLoadingReal, isError: isRealError } =
    useFindingRemediation(findingId);
  const rawDryRun = rawRemediation?.dry_run as { result?: string; confidence?: string } | undefined;

  const [dryRun] = useState<RemediationDryRunModel>(DRY_RUN_FIXTURE);
  const [isRatified, setIsRatified] = useState(false);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/remediation" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Remediation Playbook</span>
        </Link>
        <span>/</span>
        <span className="font-semibold text-foreground">Dry-Run Simulation</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
            <Play size={22} />
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Pre-Execution Dry-Run Simulation</h1>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Simulated AST evaluation predicting compliance shifts and detecting unintentional side-effect failures.
          </p>
        </div>

        <button
          onClick={() => setIsRatified(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 transition-opacity shadow-sm"
        >
          <Download size={14} />
          <span>{isRatified ? "Approved & Exported" : "Ratify & Export Execution Package"}</span>
        </button>
      </div>

      {/* Real API round trip, surfaced honestly — verified live to still be
          the M0 stub (see the hook call's comment above). */}
      <div className="p-3.5 rounded-xl border border-amber-300/70 bg-amber-50/70 dark:bg-amber-950/30 dark:border-amber-800/60 text-[11px] text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
        <AlertTriangle size={14} className="shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <span className="font-bold block">
            Live GET /findings/{findingId}/remediation
            {isLoadingReal ? " — loading…" : isRealError ? " — request failed" : ""}
          </span>
          {rawDryRun?.result ? (
            <span>
              Backend `dry_run` field: <strong className="font-mono">{rawDryRun.result}</strong> (confidence:{" "}
              {rawDryRun.confidence}) — fixed for every finding, no before/after compliance numbers or
              newly-failing-control detection (`nsca_platform/remediation/dry_run.py` is not wired to any
              endpoint). The summary box below renders a local reference fixture with real metrics. Flagged for
              Backend Track B.
            </span>
          ) : (
            <span>No dry-run result returned; summary box below renders a local reference fixture.</span>
          )}
        </div>
      </div>

      {/* Dry Run Summary Box */}
      <DryRunSummaryBox dryRun={dryRun} />

      {/* Simulated Steps Feed */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-foreground">Simulated Execution Sequence</h2>
          <span className="text-xs text-muted-foreground font-mono font-semibold">
            {dryRun.steps.length} Verified Safe Steps
          </span>
        </div>

        <div className="space-y-3">
          {dryRun.steps.map((step) => (
            <PlaybookStepCard key={step.step_number} step={step} />
          ))}
        </div>
      </div>
    </div>
  );
};
