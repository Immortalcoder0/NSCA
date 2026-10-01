import React, { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Wrench,
  Play,
  Loader2,
} from "lucide-react";
// Track 2's real FindingCard (findings/components/), swapped in for this
// track's own placeholder per
// plans/frontend-01-ingestion-campaigns-estate.md §3 M4 — the placeholder
// (estate/components/FindingCard.tsx) has been deleted.
import { FindingCard } from "../../findings/components/FindingCard";
import type { FindingModel } from "../../findings/types";
import { UnauditedCapabilityBox } from "../components/UnauditedCapabilityBox";
import { TrustTierBadge } from "../../shared/components/TrustTierBadge";
import type { DeviceDetailModel, FixFirstItem } from "../types";
import { cn } from "../../shared/lib/utils";
import { apiClient } from "../../shared/api/client";
import { useQuery } from "@tanstack/react-query";
import { useCampaignFindings } from "../../shared/api/hooks";

const SAMPLE_DEVICE_DETAIL: DeviceDetailModel = {
  id: "DEV-002",
  hostname: "CORE-SW-01",
  hardware_model: "Cisco Catalyst 9300-48P",
  platform: "Cisco IOS-XE",
  os_version: "16.12.04",
  serial: "FCW2140L0GH",
  role: "Distribution Switch",
  exposure: "internal",
  rulepack_id: "cisco_iosxe",
  rulepack_version: "7.2.1",
  rulepack_trust_tier: "CERTIFIED",
  scores: {
    compliance: 0.78,
    coverage: 0.92,
    meaningful_ratio: 0.64,
    security: 0.61,
  },
  counts: {
    findings: 31,
    passing: 112,
    unknown: 12,
    not_applicable: 14,
  },
  fix_first: [
    {
      rank: 1,
      action: "Remove 0.0.0.0/0 from group Partners",
      commandCount: 1,
      impact: "safe",
      findingId: "F-000518",
    },
    {
      rank: 2,
      action: "Disable Telnet on VTY lines",
      commandCount: 3,
      impact: "lockout_risk",
      findingId: "F-2026Q3-000412",
    },
    {
      rank: 3,
      action: "Replace type 7 reversible credential",
      commandCount: 2,
      impact: "svc_affecting",
      findingId: "F-000603",
    },
  ],
  unaudited_capabilities: [
    {
      path: "services.web_mgmt_8443",
      port: 8443,
      properties: ["listens", "authenticates", "mutates"],
      controls_contaminated: 6,
      description: "Embedded web management service active outside all selected frameworks.",
    },
  ],
};

const FALLBACK_FINDINGS: FindingModel[] = [
  {
    id: "F-2026Q3-000412",
    campaign_id: "CMP-2026Q3-001",
    device_id: "DEV-002",
    hostname: "CORE-SW-01",
    device_platform: "cisco_iosxe",
    control_id: "NSCA-MGMT-002",
    rule_id: "NSCA-MGMT-002",
    title: "Plaintext management protocols enabled on VTY lines",
    description: "Telnet transport remains enabled alongside SSH on the VTY lines.",
    verdict: "FAIL",
    severity: { base: "HIGH", effective: "CRITICAL", reason: "device.exposure == internet_facing" },
    state: "Confirmed",
    rulepack_trust_tier: "CERTIFIED",
    frameworks: [
      { framework: "cis", id: "CIS-IOS-1.2.4" },
      { framework: "nist", id: "NIST AC-17" },
      { framework: "stig", id: "STIG V-216644" },
      { framework: "iso", id: "ISO A.9.4.2" },
    ],
    evidence: [
      {
        artifact: "running-config.txt",
        lines: [141, 145],
        highlight: [143],
        excerpt: "line vty 0 4\n login local\n transport input telnet ssh\n exec-timeout 0 0\n!",
      },
    ],
    attack_paths: [],
    created_at: "2026-08-28T00:00:00Z",
  },
  {
    id: "F-2026Q3-000518",
    campaign_id: "CMP-2026Q3-001",
    device_id: "DEV-002",
    hostname: "CORE-SW-01",
    device_platform: "cisco_iosxe",
    control_id: "NSCA-NET-004",
    rule_id: "NSCA-NET-004",
    title: "Permissive wildcard rule in partner access ACL",
    description: "ACL outside-in permits any source to 0.0.0.0/0.",
    verdict: "FAIL",
    severity: { base: "HIGH", effective: "HIGH" },
    state: "Confirmed",
    rulepack_trust_tier: "CERTIFIED",
    frameworks: [
      { framework: "cis", id: "CIS-IOS-3.1.2" },
      { framework: "nist", id: "NIST SC-7" },
    ],
    evidence: [
      {
        artifact: "running-config.txt",
        lines: [200, 203],
        highlight: [202],
        excerpt: "ip access-list extended outside-in\n permit tcp any host 10.40.7.19 eq 22\n permit ip any host 0.0.0.0/0\n!",
      },
    ],
    attack_paths: [],
    created_at: "2026-08-28T00:00:00Z",
  },
];

/** `GET /assessments/{id}` (`nsca_platform/services/assessment.py
 * ::get_assessment`) — real for both the fixture-then-real worker path and
 * a real engine-assessed device; `unaudited_capabilities` is hardcoded to
 * `[]` even on the real path (that field is never populated by the
 * assessment service — flagged, not a frontend bug). Maps into this
 * track's own `DeviceDetailModel`; `fix_first` has no real backend
 * equivalent (attack-path-ranked remediation isn't wired to any endpoint —
 * see `useFindingRemediation`'s docstring for the sibling gap on
 * `/findings/{id}/remediation`), so it's synthesized client-side from the
 * top real FAIL findings for this device when available. */
function toDeviceDetailModel(raw: Record<string, unknown>, fixFirst: FixFirstItem[]): DeviceDetailModel {
  const scores = (raw.scores as Record<string, number>) ?? {};
  const counts = (raw.counts as Record<string, number>) ?? {};
  const rulepacksUsed = (raw.rulepacks_used as Array<Record<string, unknown>>) ?? [];
  const primaryRulepack = rulepacksUsed[0];
  const serials = (raw.serials as Array<Record<string, unknown>> | string[]) ?? [];
  const firstSerial =
    serials.length > 0
      ? typeof serials[0] === "string"
        ? (serials[0] as string)
        : String((serials[0] as Record<string, unknown>).serial ?? "")
      : "";

  return {
    id: String(raw.id ?? ""),
    hostname: String(raw.device ?? "unknown"),
    hardware_model: "",
    platform: String(raw.platform ?? "unknown"),
    os_version: String(raw.os_version ?? ""),
    serial: firstSerial,
    role: "",
    exposure: "internal",
    rulepack_id: String(primaryRulepack?.id ?? ""),
    rulepack_version: String(primaryRulepack?.version ?? ""),
    rulepack_trust_tier: (String(primaryRulepack?.trust_tier ?? "certified").toUpperCase() as DeviceDetailModel["rulepack_trust_tier"]),
    scores: {
      compliance: scores.compliance ?? 0,
      coverage: scores.coverage ?? 0,
      meaningful_ratio: scores.meaningful_ratio ?? 0,
      security: scores.security ?? 0,
    },
    counts: {
      findings: counts.fail ?? 0,
      passing: (counts.pass ?? 0) + (counts.pass_partial ?? 0),
      unknown: counts.unknown ?? 0,
      not_applicable: counts.not_applicable ?? 0,
    },
    fix_first: fixFirst,
    unaudited_capabilities: (raw.unaudited_capabilities as DeviceDetailModel["unaudited_capabilities"]) ?? [],
  };
}

/** Real findings have no `title`/`description`/`hostname`/`device_platform`
 * /`rule_id`/`created_at` fields at all (`finding_lifecycle._row_to_response`
 * — see useFindings.ts's own docstring for the same verified gap). This
 * synthesizes the rest from device context already loaded on this page so
 * Track 2's real `<FindingCard>` (which requires the full `FindingModel`)
 * has something honest to render, rather than leaving required fields
 * blank. `title` falls back to the control id since no real title exists
 * server-side yet — flagged, not fabricated as if real. */
function toFindingModel(raw: Record<string, unknown>, device: { hostname: string; platform: string }): FindingModel {
  const severity = (raw.severity as FindingModel["severity"]) ?? { base: "LOW", effective: "LOW" };
  return {
    id: String(raw.id ?? ""),
    campaign_id: "",
    device_id: "",
    hostname: device.hostname,
    device_platform: device.platform,
    control_id: String(raw.control ?? ""),
    rule_id: String(raw.control ?? ""),
    title: `Control ${String(raw.control ?? "")} — no title field on the live findings API yet`,
    description: "",
    verdict: (raw.verdict as FindingModel["verdict"]) ?? "UNKNOWN",
    severity,
    // Real state vocabulary ("New"/"Withdrawn"/"Risk Accepted"/"Remediated"
    // /"Verified"/"Closed" — `finding_lifecycle.STATES`) doesn't match this
    // type's ("Open"/"Remediation_Planned"/"Risk_Accepted"/"Verified_Resolved")
    // — a real cross-track vocabulary mismatch, cast through rather than
    // silently coerced to a value that would look correct but isn't.
    state: (raw.state as unknown as FindingModel["state"]) ?? "Open",
    rulepack_trust_tier: (raw.rulepack_trust_tier as FindingModel["rulepack_trust_tier"]) ?? "CERTIFIED",
    frameworks: (raw.frameworks as FindingModel["frameworks"]) ?? [],
    evidence: (raw.evidence as FindingModel["evidence"]) ?? [],
    attack_paths: (raw.attack_paths as string[]) ?? [],
    created_at: "",
  };
}

const SEVERITY_WEIGHT: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFORMATIONAL: 0 };

export const DeviceDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const assessmentId = id || "";
  const [searchParams] = useSearchParams();
  // Optional campaign context (`?campaign=CMP-...`) so this page can pull
  // real findings for the device — see the module-level note on
  // `toFindingModel` / the docstring below on why this is a documented
  // single-device-campaign assumption, not a general solution.
  const campaignId = searchParams.get("campaign") || "";

  const assessmentQuery = useQuery({
    queryKey: ["assessments", assessmentId],
    queryFn: () => apiClient.get<Record<string, unknown>>(`/assessments/${assessmentId}`),
    enabled: Boolean(assessmentId),
    retry: false,
  });

  // The real `/campaigns/{id}/findings` list has no device field at all
  // (see useEstateDevices.ts's docstring for the same verified gap), so
  // there is no way to filter it to "just this device's findings" in
  // general. For a campaign scoped to a single device (true for the
  // seeded demo campaign this integration pass created), every finding in
  // that campaign necessarily belongs to this device — that assumption is
  // stated here explicitly rather than silently generalized.
  const campaignFindingsQuery = useCampaignFindings(campaignId);

  const [activeTab, setActiveTab] = useState<"findings" | "passing" | "unknown" | "na">("findings");

  const usingRealAssessment = Boolean(assessmentQuery.data);

  const realFindings: FindingModel[] = useMemo(() => {
    if (!usingRealAssessment || !campaignId) return [];
    const items = (campaignFindingsQuery.data?.items as Array<Record<string, unknown>> | undefined) ?? [];
    const deviceCtx = {
      hostname: String((assessmentQuery.data as Record<string, unknown> | undefined)?.device ?? ""),
      platform: String((assessmentQuery.data as Record<string, unknown> | undefined)?.platform ?? ""),
    };
    return items.map((raw) => toFindingModel(raw, deviceCtx));
  }, [usingRealAssessment, campaignId, campaignFindingsQuery.data, assessmentQuery.data]);

  const fixFirst: FixFirstItem[] = useMemo(() => {
    if (!usingRealAssessment) return SAMPLE_DEVICE_DETAIL.fix_first;
    // Client-computed heuristic ranking (highest severity FAIL first) —
    // real attack-path-ranked remediation has no backing endpoint yet
    // (see module docstring).
    return realFindings
      .filter((f) => f.verdict === "FAIL")
      .sort((a, b) => (SEVERITY_WEIGHT[b.severity.effective] ?? 0) - (SEVERITY_WEIGHT[a.severity.effective] ?? 0))
      .slice(0, 5)
      .map((f, idx) => ({
        rank: idx + 1,
        action: `Remediate ${f.control_id}`,
        commandCount: 1,
        impact: "safe" as const,
        findingId: f.id,
      }));
  }, [usingRealAssessment, realFindings]);

  const device: DeviceDetailModel = usingRealAssessment
    ? toDeviceDetailModel(assessmentQuery.data as Record<string, unknown>, fixFirst)
    : SAMPLE_DEVICE_DETAIL;

  const findingsToRender = usingRealAssessment ? realFindings : FALLBACK_FINDINGS;

  if (assessmentQuery.isLoading && assessmentId) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-xs text-muted-foreground">
        <Loader2 size={16} className="animate-spin" />
        <span>Loading device assessment…</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/estate" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Estate Topology</span>
        </Link>
        <span>/</span>
        <span className="font-mono text-foreground font-bold">{device.hostname}</span>
      </div>

      {!usingRealAssessment && (
        <div className="p-3 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50/70 dark:bg-amber-950/30 text-[11px] text-amber-900 dark:text-amber-200">
          No real assessment found for id <span className="font-mono">{assessmentId || "(none)"}</span> (
          <span className="font-mono">GET /assessments/{"{id}"}</span> 404'd or the id isn't a real
          <span className="font-mono"> ASM-*</span> id — the estate grid itself doesn't produce real device links yet,
          see EstateGridPage's fallback notice). Showing the documented fixture example instead.
        </div>
      )}

      {/* Main Device Identity Header Block */}
      <div className="p-6 rounded-xl border border-border bg-card shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-2xl font-black font-mono tracking-tight text-foreground">
                {device.hostname}
              </span>
              <TrustTierBadge tier={device.rulepack_trust_tier} size="md" />
            </div>
            <div className="text-xs text-muted-foreground font-medium">
              {device.hardware_model || "—"} · <span className="font-mono">{device.platform} {device.os_version}</span>
            </div>
            <div className="text-[11px] text-muted-foreground font-mono">
              SN: <span className="font-bold text-foreground">{device.serial || "—"}</span> · {device.role || "—"} · Zone: {device.exposure}
            </div>
          </div>

          <div className="flex items-center gap-4 bg-secondary/70 p-3 rounded-lg border text-xs">
            <div className="text-center">
              <span className="text-[10px] text-muted-foreground block uppercase font-semibold">Coverage</span>
              <span className="text-lg font-black text-sky-600 dark:text-sky-400">
                {Math.round(device.scores.coverage * 100)}%
              </span>
            </div>
            <div className="h-7 w-px bg-border" />
            <div className="text-center">
              <span className="text-[10px] text-muted-foreground block uppercase font-semibold">Compliance</span>
              <span className="text-lg font-black text-emerald-600 dark:text-emerald-400">
                {Math.round(device.scores.compliance * 100)}%
              </span>
            </div>
            <div className="h-7 w-px bg-border" />
            <div className="text-center">
              <span className="text-[10px] text-muted-foreground block uppercase font-semibold">Meaningful</span>
              <span className="text-lg font-black text-purple-600 dark:text-purple-400">
                {Math.round(device.scores.meaningful_ratio * 100)}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* FIX THESE FIRST: Attack-Path-Ranked Remediation Strip */}
      <div className="p-5 rounded-xl border border-red-300 bg-red-50/70 dark:bg-red-950/40 dark:border-red-800 space-y-4 shadow-sm text-xs">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <div className="font-bold text-sm text-red-950 dark:text-red-100 flex items-center gap-1.5">
              <Wrench size={16} className="text-red-600 dark:text-red-400" />
              <span>FIX THESE FIRST {usingRealAssessment ? "(Severity-Ranked)" : "(Attack-Path Ranked Remediation)"}</span>
            </div>
            <p className="text-red-800 dark:text-red-300 text-[11px]">
              {usingRealAssessment
                ? "Client-computed severity ranking — real attack-path-ranked remediation has no backing endpoint on the live platform yet (GET /findings/{id}/remediation is still an M0 stub)."
                : `Resolving 5 key findings makes 23 of ${device.counts.findings} total vulnerabilities unreachable across all attack paths.`}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              to="/findings/remediation"
              className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-secondary border border-border text-foreground font-semibold hover:bg-secondary/80 transition-colors"
            >
              <span>Full Playbook</span>
            </Link>
            <Link
              to="/findings/remediation/dry-run"
              className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-red-700 hover:bg-red-800 text-white font-bold transition-colors shadow-sm"
            >
              <Play size={12} />
              <span>Dry Run</span>
            </Link>
          </div>
        </div>

        <div className="space-y-2">
          {device.fix_first.length === 0 && (
            <p className="text-red-800 dark:text-red-300 italic">No FAIL findings to rank yet.</p>
          )}
          {device.fix_first.map((item) => (
            <div
              key={item.rank}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2.5 rounded-lg bg-background border border-red-200 dark:border-red-900"
            >
              <div className="flex items-center gap-2.5">
                <span className="w-5 h-5 rounded-full bg-red-600 text-white font-mono font-bold text-[11px] flex items-center justify-center shrink-0">
                  {item.rank}
                </span>
                <span className="font-semibold text-foreground">{item.action}</span>
              </div>

              <div className="flex items-center gap-2 text-[11px] font-mono">
                <span className="text-muted-foreground">{item.commandCount} cmd</span>
                <span>·</span>
                <span
                  className={cn(
                    "px-1.5 py-0.5 rounded font-bold uppercase text-[10px]",
                    item.impact === "safe" && "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
                    item.impact === "lockout_risk" && "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
                    item.impact === "svc_affecting" && "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300"
                  )}
                >
                  {item.impact === "lockout_risk" ? "⚠ Lockout Risk" : item.impact}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Findings Tab Bar */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 border-b pb-2 text-xs">
          <button
            onClick={() => setActiveTab("findings")}
            className={`px-3 py-1.5 rounded-lg font-bold transition-colors flex items-center gap-1.5 ${
              activeTab === "findings"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <span>Findings</span>
            <span className="px-1.5 py-0.2 rounded-full bg-background/20 text-[10px] font-mono">
              {device.counts.findings}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("passing")}
            className={`px-3 py-1.5 rounded-lg font-semibold transition-colors flex items-center gap-1.5 ${
              activeTab === "passing"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <span>Passing</span>
            <span className="px-1.5 py-0.2 rounded-full bg-background/20 text-[10px] font-mono">
              {device.counts.passing}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("unknown")}
            className={`px-3 py-1.5 rounded-lg font-semibold transition-colors flex items-center gap-1.5 ${
              activeTab === "unknown"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <span>Unknown (⊥)</span>
            <span className="px-1.5 py-0.2 rounded-full bg-background/20 text-[10px] font-mono">
              {device.counts.unknown}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("na")}
            className={`px-3 py-1.5 rounded-lg font-semibold transition-colors flex items-center gap-1.5 ${
              activeTab === "na"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <span>N/A</span>
            <span className="px-1.5 py-0.2 rounded-full bg-background/20 text-[10px] font-mono">
              {device.counts.not_applicable}
            </span>
          </button>
        </div>

        {/* Embedded Finding Cards with Inline Evidence (Track 2's real
            <FindingCard>, expanded first by default per UX Spec §5) */}
        {activeTab === "findings" && (
          <div className="space-y-4">
            {usingRealAssessment && !campaignId && (
              <p className="text-[11px] text-muted-foreground italic">
                Add <span className="font-mono">?campaign=CMP-...</span> to this URL to load this device's real
                findings (the live findings API has no device field to filter by automatically — see the module
                docstring).
              </p>
            )}
            {findingsToRender.length === 0 ? (
              <p className="text-xs text-muted-foreground italic p-4">No FAIL findings to display.</p>
            ) : (
              findingsToRender
                .filter((f) => f.verdict === "FAIL")
                .map((finding, idx) => (
                  <FindingCard key={finding.id} finding={finding} initialExpanded={idx === 0} />
                ))
            )}
          </div>
        )}

        {activeTab !== "findings" && (
          <div className="p-8 text-center text-xs text-muted-foreground border rounded-xl bg-card">
            Rendering {device.counts[activeTab === "passing" ? "passing" : activeTab === "unknown" ? "unknown" : "not_applicable"]} evaluation records.
          </div>
        )}
      </div>

      {/* Unaudited Surface Callout Box */}
      {device.unaudited_capabilities.length > 0 ? (
        <UnauditedCapabilityBox capabilities={device.unaudited_capabilities} />
      ) : (
        usingRealAssessment && (
          <p className="text-[11px] text-muted-foreground italic">
            No unaudited capabilities reported — the real assessment service always returns an empty list for this
            field today (`unaudited_capabilities` is hardcoded to <span className="font-mono">[]</span> in
            <span className="font-mono"> services/assessment.py::get_assessment</span>, not yet computed).
          </p>
        )
      )}
    </div>
  );
};
