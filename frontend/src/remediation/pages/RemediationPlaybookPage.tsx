import React, { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Wrench,
  ArrowLeft,
  Play,
  Download,
  FileCode,
  ShieldAlert,
  AlertTriangle,
} from "lucide-react";
import { PlaybookStepCard } from "../components/PlaybookStepCard";
import { useFindingRemediation } from "../../shared/api/hooks/useRemediation";
import type { PlaybookStepModel } from "../types";

// Default finding used when no `?finding=` is present — a real FAIL finding
// on EDGE-FW-01 in this track's seeded M5 integration campaign (telnet
// enabled, NSCA-MGMT-002), so `useFindingRemediation` below hits a finding
// id that genuinely exists on the live server.
const DEFAULT_DEMO_FINDING_ID = "F-2026Q3-001-000019";

const SAMPLE_STEPS: PlaybookStepModel[] = [
  {
    step_number: 1,
    title: "Enforce SSH-Only Transport on VTY Lines",
    device_hostname: "CORE-SW-01",
    device_platform: "Cisco IOS-XE 16.12",
    impact: "lockout_risk",
    impact_warning: "Verify that SSH key pair is generated and 'ip ssh version 2' is active before applying. Applying without active SSH will permanently sever administrative access.",
    commands: [
      "configure terminal",
      "line vty 0 4",
      " transport input ssh",
      " exec-timeout 15 0",
      "end",
      "write memory",
    ],
    rollback_commands: [
      "configure terminal",
      "line vty 0 4",
      " transport input telnet ssh",
      "end",
      "write memory",
    ],
    precedes_steps: [2],
    findings_resolved: ["F-2026Q3-000412", "F-2026Q3-000413"],
  },
  {
    step_number: 2,
    title: "Restrict Partner Access ACL Ingress Rule",
    device_hostname: "CORE-SW-01",
    device_platform: "Cisco IOS-XE 16.12",
    impact: "safe",
    commands: [
      "configure terminal",
      "ip access-list extended outside-in",
      " no permit ip any host 0.0.0.0/0",
      " permit tcp 198.51.100.0 0.0.0.255 host 10.40.7.19 eq 22",
      "end",
      "write memory",
    ],
    rollback_commands: [
      "configure terminal",
      "ip access-list extended outside-in",
      " permit ip any host 0.0.0.0/0",
      "end",
      "write memory",
    ],
    depends_on_steps: [1],
    findings_resolved: ["F-2026Q3-000518"],
  },
  {
    step_number: 3,
    title: "Enable NTP Cryptographic Authentication",
    device_hostname: "BR-RTR-014",
    device_platform: "Cisco IOS 15.2",
    impact: "service_affecting",
    impact_warning: "Clock resynchronization will temporarily occur during key handshake.",
    commands: [
      "configure terminal",
      "ntp authenticate",
      "ntp authentication-key 1 md5 094F471A1A0A 7",
      "ntp trusted-key 1",
      "ntp server 10.10.1.5 key 1",
      "end",
      "write memory",
    ],
    rollback_commands: [
      "configure terminal",
      "no ntp authenticate",
      "ntp server 10.10.1.5",
      "end",
      "write memory",
    ],
    findings_resolved: ["F-2026Q3-000601"],
  },
];

export const RemediationPlaybookPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const findingId = searchParams.get("finding") || DEFAULT_DEMO_FINDING_ID;

  // Real network call: `GET /findings/{id}/remediation`. **Verified live
  // against the M5 server: still the M0 stub** — two hardcoded steps
  // ("disable telnet" / "enable ssh v2 only") for every finding id, ignoring
  // `campaign` entirely. The real planner (`nsca_platform/remediation
  // /planner.py`, version-specific command selection + dependency ordering
  // + impact classification from the control packs' `remediation:` YAML)
  // exists but is confirmed NOT wired to any HTTP route — no
  // `nsca_platform/api/*.py` router imports `nsca_platform.remediation` at
  // all. `SAMPLE_STEPS` below (Phase 1's richer fixture — commands,
  // rollback, dependency ordering) is used for the actual rendering; the
  // raw stub response is shown transparently beneath the meta strip.
  const { data: rawRemediation, isLoading: isLoadingReal, isError: isRealError } =
    useFindingRemediation(findingId);
  const rawSteps =
    (rawRemediation?.plan as { steps?: Array<{ order: number; action: string; impact: string; lockout_risk: boolean }> } | undefined)
      ?.steps ?? [];

  const [steps] = useState<PlaybookStepModel[]>(SAMPLE_STEPS);

  const lockoutCount = steps.filter((s) => s.impact === "lockout_risk").length;
  const svcAffectingCount = steps.filter((s) => s.impact === "service_affecting").length;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/findings" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Findings Workbench</span>
        </Link>
        <span>/</span>
        <span className="font-semibold text-foreground">Remediation Playbook</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-primary">
            <Wrench size={22} />
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Safety-Sequenced Remediation Playbook</h1>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Ordered execution plan with explicit lockout-risk warnings, rollback scripts, and dependency validation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/remediation/dry-run"
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-colors shadow-sm"
          >
            <Play size={13} />
            <span>Simulate Dry Run</span>
          </Link>
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors">
            <Download size={13} />
            <span>Export CLI Script</span>
          </button>
        </div>
      </div>

      {/* Real API round trip, surfaced honestly — see the hook call's
          comment above: verified live to still be the M0 stub. */}
      <div className="p-3.5 rounded-xl border border-amber-300/70 bg-amber-50/70 dark:bg-amber-950/30 dark:border-amber-800/60 text-[11px] text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
        <AlertTriangle size={14} className="shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <span className="font-bold block">
            Live GET /findings/{findingId}/remediation
            {isLoadingReal ? " — loading…" : isRealError ? " — request failed" : ""}
          </span>
          {rawSteps.length > 0 ? (
            <span>
              Backend returned {rawSteps.length} step(s), e.g.{" "}
              <strong className="font-mono">
                {rawSteps[0].order}. {rawSteps[0].action} (impact: {rawSteps[0].impact}, lockout_risk:{" "}
                {String(rawSteps[0].lockout_risk)})
              </strong>{" "}
              — the same fixed pair for every finding id (the real version-specific planner in
              `nsca_platform/remediation/planner.py` is not wired to any endpoint yet). The richer step cards below
              render a local reference fixture with real commands, rollback scripts, and dependency ordering.
              Flagged for Backend Track B.
            </span>
          ) : (
            <span>No steps returned; step cards below render a local reference fixture.</span>
          )}
        </div>
      </div>

      {/* Meta Strip */}
      <div className="p-4 rounded-xl border border-border bg-card flex flex-wrap items-center justify-between gap-4 text-xs shadow-sm">
        <div className="flex items-center gap-4">
          <div>
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Total Steps</span>
            <span className="text-base font-bold text-foreground">{steps.length} sequential steps</span>
          </div>
          <div className="h-6 w-px bg-border" />
          <div>
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Safety Profile</span>
            <span className="text-amber-600 dark:text-amber-400 font-bold flex items-center gap-1">
              <ShieldAlert size={13} />
              {lockoutCount} lockout risk · {svcAffectingCount} svc-affecting
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button className="flex items-center gap-1 px-2.5 py-1.5 rounded bg-secondary text-foreground text-xs font-medium hover:bg-secondary/80 transition-colors">
            <FileCode size={13} className="text-primary" />
            <span>Ansible Role</span>
          </button>
        </div>
      </div>

      {/* Ordered Step Cards */}
      <div className="space-y-4">
        {steps.map((step) => (
          <PlaybookStepCard key={step.step_number} step={step} />
        ))}
      </div>
    </div>
  );
};
