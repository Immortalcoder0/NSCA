import React, { useState, useMemo, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ShieldAlert, Wrench, Filter, AlertTriangle, Loader2 } from "lucide-react";
import { SystemicFindingBanner } from "../components/SystemicFindingBanner";
import { FindingFilterToolbar } from "../components/FindingFilterToolbar";
import { BulkActionBar } from "../components/BulkActionBar";
import { RiskAcceptanceModal } from "../components/RiskAcceptanceModal";
import { VirtualizedFindingList } from "../components/VirtualizedFindingList";
import { useWorkbenchFindings, DEFAULT_CAMPAIGN_ID } from "../hooks";
import {
  useBulkFindings,
  useAssignFinding,
  useAcceptFindingRisk,
} from "../../shared/api/hooks/useFindings";
import type { FindingModel, FindingGroupBy, RiskAcceptanceSubmission } from "../types";
import { cn } from "../../shared/lib/utils";

// A control-id whose FAIL count across the campaign meets/exceeds this is
// treated as a systemic cluster for grouping/banner purposes. The real API
// has no `systemic_id`/cluster column on `finding` at all (`db/models
// /finding.py`) and `GET /campaigns/{id}/systemic` is still an M0 stub
// (verified live — see `shared/api/hooks/useAttackPaths.ts`'s sibling
// docstring for the same situation on attack-paths), so this client-side
// "N+ devices FAIL the same control" heuristic is the most honest signal
// available from real data today — flagged as a judgment call, not
// silently presented as a server-computed cluster.
const SYSTEMIC_CLUSTER_THRESHOLD = 3;

function deriveSystemicClusters(findings: FindingModel[]): Map<string, string> {
  const failCountByControl = new Map<string, number>();
  for (const f of findings) {
    if (f.verdict === "FAIL") {
      failCountByControl.set(f.control_id, (failCountByControl.get(f.control_id) ?? 0) + 1);
    }
  }
  const systemicIdByControl = new Map<string, string>();
  for (const [controlId, count] of failCountByControl) {
    if (count >= SYSTEMIC_CLUSTER_THRESHOLD) {
      systemicIdByControl.set(controlId, `SYS-${controlId}`);
    }
  }
  return systemicIdByControl;
}

export const FindingWorkbenchPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const campaignId = searchParams.get("campaign") || DEFAULT_CAMPAIGN_ID;

  const { data: fetchedFindings, isLoading, isError } = useWorkbenchFindings(campaignId);
  const bulkFindingsMutation = useBulkFindings();
  const assignFindingMutation = useAssignFinding();
  const acceptRiskMutation = useAcceptFindingRisk();

  const [findings, setFindings] = useState<FindingModel[]>([]);
  useEffect(() => {
    if (fetchedFindings) setFindings(fetchedFindings);
  }, [fetchedFindings]);

  const [groupBy, setGroupBy] = useState<FindingGroupBy>("control");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [verdictFilter, setVerdictFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [riskModalFindingId, setRiskModalFindingId] = useState<string | null>(null);

  const systemicIdByControl = useMemo(() => deriveSystemicClusters(findings), [findings]);

  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      const matchSearch =
        f.control_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        f.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        f.hostname.toLowerCase().includes(searchTerm.toLowerCase()) ||
        f.id.toLowerCase().includes(searchTerm.toLowerCase());

      const matchSeverity =
        severityFilter === "all" ||
        f.severity.effective.toLowerCase() === severityFilter.toLowerCase() ||
        f.severity.base.toLowerCase() === severityFilter.toLowerCase();

      const matchVerdict =
        verdictFilter === "all" || f.verdict.toLowerCase() === verdictFilter.toLowerCase();

      return matchSearch && matchSeverity && matchVerdict;
    });
  }, [findings, searchTerm, severityFilter, verdictFilter]);

  const groupedData = useMemo(() => {
    const groups: Record<string, FindingModel[]> = {};
    filteredFindings.forEach((f) => {
      let key = "Unclassified";
      if (groupBy === "control") key = `${f.control_id} — ${f.title}`;
      else if (groupBy === "device") key = `${f.hostname} (${f.device_platform})`;
      else if (groupBy === "attack_path") key = f.attack_paths[0] || "No Attack Path Association";
      else if (groupBy === "systemic") {
        const systemicId = systemicIdByControl.get(f.control_id);
        key = systemicId ? `Systemic Cluster ${systemicId}` : "Independent Findings";
      }

      if (!groups[key]) groups[key] = [];
      groups[key].push(f);
    });
    return groups;
  }, [filteredFindings, groupBy, systemicIdByControl]);

  // Bulk-adjudication decision (frontend-02 §5's open question, re-verified
  // live against the running M5 server, not just the source):
  //
  //   POST /findings/bulk  { finding_ids: string[], action: string }
  //
  // is a single-call bulk endpoint, but `bulk_transition`'s action_map only
  // wires `confirm` and `mark-remediated` server-side — any other action
  // string silently no-ops (`updated: 0`, not a 4xx). It is also NOT
  // cluster-scoped: the client supplies `finding_ids` itself.
  //
  // "Adjudicate all N" (SystemicFindingBanner): the *existing Phase-1 mock*
  // already defined this action as moving the cluster's findings to
  // `Confirmed` state, not as calling the dispute-adjudication endpoint
  // (`POST /findings/{id}/adjudicate`, which only applies to a finding
  // already in `Disputed` state and would 409 on anything else). So the
  // real, correct wiring for this button is `POST /findings/bulk` with
  // `action: "confirm"`, scoped to the cluster's ids the client already
  // computed (`deriveSystemicClusters` above) — a single real network call,
  // matching the plan doc's stated preference for the bulk endpoint over N
  // calls whenever the payload supports what's needed.
  //
  // "Assign all N": `/findings/bulk` has no `assign` action server-side at
  // all (only per-finding `POST /findings/{id}/assign` exists) — this one
  // genuinely has no single-call path today, so it runs as N sequential
  // real `assign` calls behind one optimistic UI update, per the plan's
  // documented fallback.
  const handleSelect = (id: string, isSelected: boolean) => {
    setSelectedIds((prev) =>
      isSelected ? [...prev, id] : prev.filter((item) => item !== id)
    );
  };

  const handleClearSelection = () => setSelectedIds([]);

  const handleBulkConfirm = () => {
    const ids = [...selectedIds];
    setFindings((prev) => prev.map((f) => (ids.includes(f.id) ? { ...f, state: "Confirmed" } : f)));
    setSelectedIds([]);
    bulkFindingsMutation.mutate({ findingIds: ids, action: "confirm" });
  };

  const handleBulkAssign = (assignee: string) => {
    const ids = [...selectedIds];
    setFindings((prev) => prev.map((f) => (ids.includes(f.id) ? { ...f, assigned_to: assignee } : f)));
    setSelectedIds([]);
    // N sequential real calls behind one optimistic UI action — see comment
    // block above.
    ids.forEach((id) => assignFindingMutation.mutate({ id, assignee }));
  };

  const handleRiskAcceptanceSubmit = (data: RiskAcceptanceSubmission) => {
    setFindings((prev) =>
      prev.map((f) => (f.id === data.finding_id ? { ...f, state: "Risk_Accepted" } : f))
    );
    acceptRiskMutation.mutate({
      id: data.finding_id,
      expires_at: data.expires_at,
      justification: data.justification,
      compensating_control: data.compensating_control ? { note: data.compensating_control } : null,
    });
  };

  const handleClusterAdjudicateAll = (clusterFindingIds: string[]) => {
    setFindings((prev) =>
      prev.map((f) => (clusterFindingIds.includes(f.id) ? { ...f, state: "Confirmed" } : f))
    );
    bulkFindingsMutation.mutate({ findingIds: clusterFindingIds, action: "confirm" });
  };

  const handleClusterAssignAll = (clusterFindingIds: string[]) => {
    setFindings((prev) =>
      prev.map((f) => (clusterFindingIds.includes(f.id) ? { ...f, assigned_to: "p.sharma" } : f))
    );
    clusterFindingIds.forEach((id) => assignFindingMutation.mutate({ id, assignee: "p.sharma" }));
  };

  const criticalCount = findings.filter((f) => f.severity.effective === "CRITICAL").length;
  const highCount = findings.filter((f) => f.severity.effective === "HIGH").length;
  const mediumCount = findings.filter((f) => f.severity.effective === "MEDIUM").length;

  return (
    <div className="space-y-5">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/70 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">Findings & Risk Workbench</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Triage compliance exceptions, verify dispute evidence, and sequence safety-verified remediation.
          </p>
          <p className="text-[11px] text-muted-foreground mt-0.5 font-mono">
            Campaign: {campaignId}
            {isLoading && (
              <span className="inline-flex items-center gap-1 ml-2 text-primary">
                <Loader2 size={11} className="animate-spin" /> loading live data…
              </span>
            )}
            {isError && <span className="ml-2 text-amber-600">showing offline fixture data</span>}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/findings/attack-paths"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-card text-xs font-semibold hover:bg-secondary transition-colors"
          >
            <ShieldAlert size={14} className="text-rose-600" />
            <span>Attack Paths</span>
          </Link>
          <Link
            to="/remediation"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 transition-opacity"
          >
            <Wrench size={14} />
            <span>Remediation Playbook</span>
          </Link>
        </div>
      </div>

      {/* Filter and Group-by Toolbar */}
      <FindingFilterToolbar
        groupBy={groupBy}
        onGroupByChange={setGroupBy}
        severityFilter={severityFilter}
        onSeverityFilterChange={setSeverityFilter}
        verdictFilter={verdictFilter}
        onVerdictFilterChange={setVerdictFilter}
        searchTerm={searchTerm}
        onSearchTermChange={setSearchTerm}
      />

      {/* 2-Column Responsive Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Filter & Grouping Rail (Sticky on Large Screens) */}
        <div className="lg:col-span-3 space-y-4 lg:sticky lg:top-20">
          {/* Quick Severity Breakdown Rail */}
          <div className="p-4 rounded-xl border border-border/80 bg-card space-y-2.5">
            <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <AlertTriangle size={13} />
              Severity Breakdown
            </span>
            <div className="flex flex-col gap-1 text-xs">
              {[
                { id: "all", label: "All Severities", count: findings.length },
                { id: "critical", label: "Critical", count: criticalCount },
                { id: "high", label: "High", count: highCount },
                { id: "medium", label: "Medium", count: mediumCount },
              ].map((sev) => (
                <button
                  key={sev.id}
                  onClick={() => setSeverityFilter(sev.id)}
                  className={cn(
                    "flex items-center justify-between px-2.5 py-1.5 rounded-md transition-colors font-medium",
                    severityFilter === sev.id
                      ? "bg-secondary text-foreground font-bold"
                      : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                  )}
                >
                  <span>{sev.label}</span>
                  <span className="font-mono text-[11px] px-1.5 py-0.2 rounded bg-muted text-foreground">
                    {sev.count}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Verdict Scope Rail */}
          <div className="p-4 rounded-xl border border-border/80 bg-card space-y-2.5">
            <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Filter size={13} />
              Verdict Breakdown
            </span>
            <div className="flex flex-col gap-1 text-xs">
              {[
                { id: "all", label: "All Verdicts" },
                { id: "fail", label: "Fail" },
                { id: "pass", label: "Pass" },
                { id: "unknown", label: "Unknown (⊥)" },
              ].map((v) => (
                <button
                  key={v.id}
                  onClick={() => setVerdictFilter(v.id)}
                  className={cn(
                    "flex items-center justify-between px-2.5 py-1.5 rounded-md transition-colors font-medium text-left",
                    verdictFilter === v.id
                      ? "bg-secondary text-foreground font-bold"
                      : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                  )}
                >
                  <span>{v.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Main Findings Feed & Cards */}
        <div className="lg:col-span-9 space-y-4">
          {Object.entries(groupedData).length === 0 ? (
            <div className="p-12 text-center border border-border rounded-xl bg-card text-muted-foreground italic text-xs">
              {isLoading ? "Loading findings…" : "No matching findings found for the selected criteria."}
            </div>
          ) : (
            Object.entries(groupedData).map(([groupTitle, groupItems]) => {
              const systemicId = systemicIdByControl.get(groupItems[0]?.control_id ?? "");
              const isSystemicGroup = groupItems.every(
                (item) => systemicIdByControl.get(item.control_id) === systemicId
              ) && Boolean(systemicId);
              const clusterFindingIds = groupItems.map((f) => f.id);

              return (
                <div key={groupTitle} className="space-y-3">
                  {/* Group Header */}
                  <div className="flex items-center justify-between border-b border-border/60 pb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-secondary text-foreground">
                        {groupItems.length}
                      </span>
                      <h2 className="text-sm font-bold text-foreground">{groupTitle}</h2>
                    </div>
                  </div>

                  {/* Inline Systemic Finding Banner */}
                  {isSystemicGroup && systemicId && (
                    <SystemicFindingBanner
                      systemicId={systemicId}
                      affectedCount={groupItems.length}
                      totalGroupCount={groupItems.length}
                      onAdjudicateAll={() => handleClusterAdjudicateAll(clusterFindingIds)}
                      onAssignAll={() => handleClusterAssignAll(clusterFindingIds)}
                    />
                  )}

                  {/* Cards inside Group — virtualised past a small-group
                      threshold (frontend-02 §2.1 / A7: "an assessor works
                      with hundreds of findings at once," and systemic
                      clusters in particular can run to dozens of rows). */}
                  <VirtualizedFindingList
                    findings={groupItems}
                    selectedIds={selectedIds}
                    onSelect={handleSelect}
                    onAcceptRisk={(id) => setRiskModalFindingId(id)}
                  />
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Floating Bulk Action Bar */}
      <BulkActionBar
        selectedCount={selectedIds.length}
        onClearSelection={handleClearSelection}
        onBulkConfirm={handleBulkConfirm}
        onBulkAssign={handleBulkAssign}
        onBulkAcceptRisk={() => {
          if (selectedIds[0]) setRiskModalFindingId(selectedIds[0]);
        }}
      />

      {/* Risk Acceptance Modal */}
      {riskModalFindingId && (
        <RiskAcceptanceModal
          isOpen={Boolean(riskModalFindingId)}
          findingId={riskModalFindingId}
          onClose={() => setRiskModalFindingId(null)}
          onSubmit={handleRiskAcceptanceSubmit}
        />
      )}
    </div>
  );
};
