import React, { useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  Lock,
  UploadCloud,
  Server,
  Play,
  CheckCircle,
  Layers,
  ArrowLeft,
  Pin,
  Loader2,
  Shield,
} from "lucide-react";
import { CampaignStatusBadge } from "../components/CampaignStatusBadge";
import { ScopeResolverSummary } from "../components/ScopeResolverSummary";
import { RequireRole } from "../../app/auth-guard";
import type { CampaignFramework, CampaignLifecycleState } from "../types";
import { CoverageBar } from "../../shared/components/CoverageBar";
import {
  useCampaign,
  useResolveScope,
  useRunAssessment,
  useIssueCampaign,
  useCloseCampaign,
  useCampaignFindings,
  useCampaignCompleteness,
} from "../../shared/api/hooks";

// Real campaign state machine (`nsca_platform/services/campaign.py`):
// `scope/resolve` is the only call that moves `Draft -> Collecting`;
// `issue` is reachable from Draft/Collecting/Assessing/Review (`Issued`);
// `close` only from `Issued` (`Closed`). `Assessing`/`Review` are listed in
// the backend's own `STATE_ORDER` but no endpoint transitions a campaign
// into either state yet (M1/M2 scope) — `assess` persists real
// assessments/findings without touching `status`. So the UI shows the
// server's real `status` and only offers the actions that exist, instead
// of faking a client-side jump through unreachable states.
const ISSUABLE_FROM: CampaignLifecycleState[] = ["Draft", "Collecting", "Assessing", "Review"];

export const CampaignDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const campaignId = id || "";

  const { data, isLoading, isError, error } = useCampaign(campaignId);
  const resolveScope = useResolveScope(campaignId);
  const runAssessment = useRunAssessment(campaignId);
  const issueCampaign = useIssueCampaign(campaignId);
  const closeCampaign = useCloseCampaign(campaignId);
  const findingsQuery = useCampaignFindings(campaignId);
  // `POST /campaigns/{id}/scope/resolve`'s `device_count` only exists as a
  // one-shot mutation response — there's no GET to re-fetch "the last
  // resolution result" once this page is reloaded in a fresh session.
  // `GET /campaigns/{id}/completeness`'s `in_scope_devices` reflects the
  // same persisted `scope_devices` column, so it's used as the durable
  // fallback source for the resolved count once the in-session mutation
  // result is gone.
  const completenessQuery = useCampaignCompleteness(campaignId);

  const [lastAssessMessage, setLastAssessMessage] = useState<string | null>(null);

  const campaign = data as
    | {
        id: string;
        name: string;
        status: CampaignLifecycleState;
        scope: { type: string; expression?: string; devices?: string[] };
        frameworks: CampaignFramework[];
        owner: string;
        window: { start?: string; end?: string };
        knowledge_pin?: Record<string, unknown>;
      }
    | undefined;

  const status: CampaignLifecycleState = campaign?.status ?? "Draft";
  const isIssuedOrClosed = status === "Issued" || status === "Closed";
  const canIssue = ISSUABLE_FROM.includes(status);

  const scopeResolveResult = resolveScope.data as
    | { device_count?: number; devices?: unknown[] }
    | undefined;
  const persistedInScopeDevices = (completenessQuery.data as { in_scope_devices?: number } | undefined)
    ?.in_scope_devices;
  const resolvedDeviceCount = scopeResolveResult?.device_count ?? persistedInScopeDevices ?? 0;

  // Coverage breakdown computed from the real per-campaign findings list
  // (`GET /campaigns/{id}/findings`), grouped by `verdict` client-side —
  // the real backend has no separate "compliance ratio" rollup endpoint,
  // so this is the honest real number, not a fabricated placeholder.
  const coverageBreakdown = useMemo(() => {
    const items = (findingsQuery.data?.items as Array<Record<string, unknown>> | undefined) ?? [];
    const counts = { pass: 0, passPartial: 0, passVacuous: 0, fail: 0, unknown: 0, notApplicable: 0 };
    for (const item of items) {
      switch (item.verdict) {
        case "PASS":
          counts.pass += 1;
          break;
        case "PASS_PARTIAL":
          counts.passPartial += 1;
          break;
        case "PASS_VACUOUS":
          counts.passVacuous += 1;
          break;
        case "FAIL":
          counts.fail += 1;
          break;
        case "UNKNOWN":
          counts.unknown += 1;
          break;
        case "NOT_APPLICABLE":
          counts.notApplicable += 1;
          break;
        default:
          break;
      }
    }
    return counts;
  }, [findingsQuery.data]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-xs text-muted-foreground">
        <Loader2 size={16} className="animate-spin" />
        <span>Loading campaign…</span>
      </div>
    );
  }

  if (isError || !campaign) {
    return (
      <div className="max-w-3xl mx-auto p-6 rounded-xl border border-red-300 dark:border-red-800 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-200 space-y-2">
        <p className="font-semibold">Could not load campaign {campaignId || "(no id)"}.</p>
        <p>{error instanceof Error ? error.message : "It may not exist yet on the platform API."}</p>
        <Link to="/campaigns" className="underline font-medium">
          Back to all campaigns
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/campaigns" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>All Campaigns</span>
        </Link>
        <span>/</span>
        <span className="font-mono text-foreground">{campaign.id}</span>
      </div>

      {/* Main Campaign Header Block */}
      <div className="p-6 rounded-xl border border-border bg-card shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-muted-foreground">{campaign.id}</span>
              <CampaignStatusBadge status={status} />
              {isIssuedOrClosed && (
                <span className="text-xs text-muted-foreground flex items-center gap-1 font-semibold">
                  <Lock size={12} className="text-amber-500" />
                  Immutable Baseline
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">{campaign.name}</h1>
            <p className="text-xs text-muted-foreground">
              Lead Assessor: <span className="font-semibold text-foreground">{campaign.owner || "—"}</span> · Window:{" "}
              {campaign.window?.start || "—"} → {campaign.window?.end || "—"}
            </p>
          </div>

          {/* Quick Action Navigation Buttons */}
          <div className="flex items-center gap-2">
            <Link
              to={`/campaigns/${campaign.id}/ingest`}
              className="flex items-center gap-1.5 px-3 py-2 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors"
            >
              <UploadCloud size={14} className="text-primary" />
              <span>Ingestion Dashboard</span>
            </Link>
            <Link
              to={`/estate?campaign=${campaign.id}`}
              className="flex items-center gap-1.5 px-3 py-2 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors"
            >
              <Server size={14} className="text-primary" />
              <span>Estate Device Grid</span>
            </Link>
          </div>
        </div>

        {/* State Machine Transition Toolbar */}
        <div className="pt-4 border-t border-border flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground font-semibold">Lifecycle Progression:</span>
            <div className="flex items-center gap-1 bg-secondary p-1 rounded-md">
              {(["Draft", "Collecting", "Assessing", "Review", "Issued", "Closed"] as CampaignLifecycleState[]).map(
                (step) => (
                  <span
                    key={step}
                    className={`px-2 py-0.5 rounded text-[11px] font-mono ${
                      status === step ? "bg-primary text-primary-foreground font-bold" : "text-muted-foreground"
                    }`}
                  >
                    {step}
                  </span>
                )
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {status === "Draft" && (
              <button
                onClick={() => resolveScope.mutate()}
                disabled={resolveScope.isPending}
                className="flex items-center gap-1 px-3 py-1.5 rounded bg-primary text-primary-foreground font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {resolveScope.isPending ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
                <span>Resolve Scope & Start Collection</span>
              </button>
            )}

            {(status === "Collecting" || status === "Assessing" || status === "Review") && (
              <button
                onClick={() => {
                  runAssessment.mutate(undefined, {
                    onSuccess: (res) => {
                      const assessments = (res as { assessments?: string[] }).assessments ?? [];
                      setLastAssessMessage(
                        `Assessment run complete — ${assessments.length} device assessment(s) persisted. Status remains ${status} (the live backend has no Collecting→Assessing transition endpoint yet).`
                      );
                    },
                  });
                }}
                disabled={runAssessment.isPending}
                className="flex items-center gap-1 px-3 py-1.5 rounded bg-purple-600 text-white font-semibold hover:bg-purple-700 transition-colors disabled:opacity-50"
              >
                {runAssessment.isPending ? <Loader2 size={13} className="animate-spin" /> : <Layers size={13} />}
                <span>Run Assessment Engine</span>
              </button>
            )}

            {canIssue && (
              <RequireRole
                roles={["lead_assessor"]}
                fallback={
                  <span className="text-muted-foreground italic text-[11px]">
                    Lead Assessor role required to Issue Campaign
                  </span>
                }
              >
                <button
                  onClick={() => issueCampaign.mutate()}
                  disabled={issueCampaign.isPending}
                  className="flex items-center gap-1 px-3 py-1.5 rounded bg-emerald-600 text-white font-semibold hover:bg-emerald-700 transition-colors disabled:opacity-50"
                >
                  {issueCampaign.isPending ? <Loader2 size={13} className="animate-spin" /> : <Lock size={13} />}
                  <span>Issue Campaign (Seal Immutability)</span>
                </button>
              </RequireRole>
            )}

            {status === "Issued" && (
              <button
                onClick={() => closeCampaign.mutate()}
                disabled={closeCampaign.isPending}
                className="flex items-center gap-1 px-3 py-1.5 rounded bg-zinc-700 text-zinc-100 font-semibold hover:bg-zinc-800 transition-colors disabled:opacity-50"
              >
                {closeCampaign.isPending ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle size={13} />}
                <span>Archive & Close</span>
              </button>
            )}
          </div>
        </div>

        {lastAssessMessage && (
          <p className="text-[11px] text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 rounded px-3 py-2">
            {lastAssessMessage}
          </p>
        )}
        {resolveScope.isError && (
          <p className="text-[11px] text-red-700 dark:text-red-300">
            Scope resolution failed:{" "}
            {resolveScope.error instanceof Error ? resolveScope.error.message : "unknown error"}
          </p>
        )}
      </div>

      {/* Scope and Assessment Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: Scope & Resolution */}
        <div className="md:col-span-2 space-y-4">
          <div className="p-5 rounded-xl border border-border bg-card space-y-3">
            <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
              <Shield size={16} className="text-primary" />
              <span>Audit Scope & Framework Standards</span>
            </h3>

            <ScopeResolverSummary
              expression={campaign.scope?.expression || (campaign.scope?.devices ?? []).join(", ") || "—"}
              resolvedCount={resolvedDeviceCount}
              totalInventoryCount={Math.max(resolvedDeviceCount, 1)}
              isLoading={resolveScope.isPending}
            />

            <div className="space-y-2 pt-2 border-t text-xs">
              <span className="text-muted-foreground font-semibold">Active Framework Benchmarks:</span>
              {campaign.frameworks.length === 0 ? (
                <p className="text-muted-foreground italic text-[11px]">No frameworks recorded on this campaign.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {campaign.frameworks.map((fw, i) => (
                    <div key={i} className="p-2.5 rounded border border-border bg-secondary/40 space-y-1">
                      <div className="font-semibold text-foreground uppercase">{fw.framework}</div>
                      <div className="text-muted-foreground font-mono text-[10px]">
                        {fw.benchmark || fw.catalog || ""} {fw.version || fw.revision || fw.release || ""}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Compliance Breakdown Strip */}
          <div className="p-5 rounded-xl border border-border bg-card space-y-3">
            <h3 className="text-sm font-bold text-foreground">Current Compliance Ratio Breakdown</h3>
            <p className="text-[11px] text-muted-foreground">
              Computed live from <span className="font-mono">GET /campaigns/{campaign.id}/findings</span>, grouped
              by verdict.
            </p>
            <CoverageBar breakdown={coverageBreakdown} size="lg" />
          </div>
        </div>

        {/* Right Column: Knowledge Pin & Custody */}
        <div className="space-y-4">
          <div className="p-5 rounded-xl border border-border bg-card space-y-3 text-xs">
            <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
              <Pin size={15} className="text-amber-500" />
              <span>Knowledge Pin (Integrity)</span>
            </h3>
            <p className="text-muted-foreground text-[11px]">
              Pinned engine & rulepack signatures ensure byte-identical reproducibility (G1 / G3).
            </p>

            {campaign.knowledge_pin && Object.keys(campaign.knowledge_pin).length > 0 ? (
              <pre className="space-y-2 font-mono text-[11px] bg-secondary/60 p-3 rounded border whitespace-pre-wrap break-all">
                {JSON.stringify(campaign.knowledge_pin, null, 2)}
              </pre>
            ) : (
              <p className="text-[11px] text-muted-foreground italic bg-secondary/60 p-3 rounded border">
                No knowledge pin recorded on this campaign yet.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
