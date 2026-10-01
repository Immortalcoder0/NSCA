import React, { useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Wrench,
  MessageSquare,
  ShieldAlert,
  Server,
  Network,
  Loader2,
} from "lucide-react";
import { VerdictBadge } from "../../shared/components/VerdictBadge";
import { SeverityBadge } from "../../shared/components/SeverityBadge";
import { TrustTierBadge } from "../../shared/components/TrustTierBadge";
import { EvidenceExcerpt } from "../../shared/components/EvidenceExcerpt";
import { RiskAcceptanceModal } from "../components/RiskAcceptanceModal";
import { useFindingDetailModel, DEFAULT_CAMPAIGN_ID } from "../hooks";
import { useAcceptFindingRisk } from "../../shared/api/hooks/useFindings";
import type { RiskAcceptanceSubmission } from "../types";

export const FindingDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const campaignId = searchParams.get("campaign") || DEFAULT_CAMPAIGN_ID;
  const { data: finding, isLoading, isError } = useFindingDetailModel(id, campaignId);
  const acceptRiskMutation = useAcceptFindingRisk();
  const [isRiskModalOpen, setIsRiskModalOpen] = useState(false);

  const handleRiskAcceptanceSubmit = (data: RiskAcceptanceSubmission) => {
    acceptRiskMutation.mutate({
      id: data.finding_id,
      expires_at: data.expires_at,
      justification: data.justification,
      compensating_control: data.compensating_control ? { note: data.compensating_control } : null,
    });
  };

  if (isLoading || !finding) {
    return (
      <div className="flex items-center justify-center gap-2 p-16 text-xs text-muted-foreground">
        <Loader2 size={14} className="animate-spin" />
        <span>Loading finding {id}…</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/findings" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Findings Workbench</span>
        </Link>
        <span>/</span>
        <span className="font-mono text-foreground font-bold">{id || finding.id}</span>
        {isError && <span className="ml-2 text-amber-600">(offline fixture data)</span>}
      </div>

      {/* Main Header Block */}
      <div className="p-6 rounded-xl border border-border bg-card shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono font-bold text-foreground text-sm">{finding.control_id}</span>
              <span className="text-muted-foreground font-mono text-xs">({finding.id})</span>
              <VerdictBadge verdict={finding.verdict} size="md" />
              <SeverityBadge severity={finding.severity.effective} size="md" />
              <TrustTierBadge tier={finding.rulepack_trust_tier} size="md" />
              <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-muted text-foreground">
                State: {finding.state}
              </span>
            </div>

            <h1 className="text-xl font-bold tracking-tight text-foreground">{finding.title}</h1>

            {finding.description && (
              <p className="text-xs text-muted-foreground leading-relaxed max-w-3xl">
                {finding.description}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground pt-1">
              <span className="flex items-center gap-1 font-mono text-foreground font-semibold">
                <Server size={13} className="text-muted-foreground" />
                {finding.hostname} ({finding.device_platform})
              </span>
              {finding.severity.reason && (
                <>
                  <span>·</span>
                  <span className="text-amber-700 dark:text-amber-300 font-medium">
                    Severity Shift: {finding.severity.base} → <strong>{finding.severity.effective}</strong> ({finding.severity.reason})
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap md:flex-col gap-2 shrink-0">
            <Link
              to={`/remediation?finding=${finding.id}`}
              className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 transition-opacity"
            >
              <Wrench size={14} />
              <span>Remediate</span>
            </Link>

            <Link
              to={`/findings/${finding.id}/dispute`}
              className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-md border border-border bg-secondary hover:bg-secondary/80 text-foreground text-xs font-bold transition-colors"
            >
              <MessageSquare size={14} />
              <span>Dispute / Defend</span>
            </Link>

            <button
              onClick={() => setIsRiskModalOpen(true)}
              className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-md border border-border hover:bg-secondary text-foreground text-xs font-semibold transition-colors"
            >
              <ShieldAlert size={14} />
              <span>Accept Risk</span>
            </button>
          </div>
        </div>
      </div>

      {/* Attack Path Callout (if connected) */}
      {finding.attack_paths.length > 0 && (
        <div className="p-4 rounded-xl border border-red-300 bg-red-50/70 dark:bg-red-950/40 dark:border-red-800 flex items-center justify-between gap-4 text-xs text-red-950 dark:text-red-200">
          <div className="flex items-center gap-3">
            <Network size={18} className="text-red-600 dark:text-red-400 shrink-0" />
            <div>
              <span className="font-bold block">Critical Attack Path Contributor</span>
              <p className="text-[11px] text-red-800 dark:text-red-300">
                This vulnerability enables lateral movement on chain {finding.attack_paths.join(", ")}. Remediating this finding severs the reachable path.
              </p>
            </div>
          </div>

          <Link
            to="/findings/attack-paths"
            className="px-3 py-1.5 rounded-md bg-red-700 hover:bg-red-800 text-white font-bold shrink-0 transition-colors shadow-sm"
          >
            Explore Chain
          </Link>
        </div>
      )}

      {/* Primary Evidence Section (Expanded by Default per Principle U1) */}
      <div className="p-6 rounded-xl border border-border bg-card shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-foreground">Definitive Configuration Evidence</h2>
          {finding.evidence[0] && (
            <span className="text-xs font-mono text-muted-foreground">
              {finding.evidence[0].artifact} (Lines {finding.evidence[0].lines[0]}–{finding.evidence[0].lines[1]})
            </span>
          )}
        </div>

        <p className="text-xs text-muted-foreground">
          Line-numbered evidence excerpt proving the non-compliant AST state with secrets redacted.
        </p>

        {finding.evidence[0] ? (
          <EvidenceExcerpt
            content={finding.evidence[0].excerpt}
            startLineNumber={finding.evidence[0].lines[0]}
            highlightLines={finding.evidence[0].highlight}
            filename={finding.evidence[0].artifact}
          />
        ) : (
          <p className="text-xs italic text-muted-foreground">
            No line-level evidence was captured for this finding by the real API (control evaluated without a
            resolvable artifact reference).
          </p>
        )}
      </div>

      {/* Cross-Framework Mappings */}
      {finding.frameworks.length > 0 && (
        <div className="p-6 rounded-xl border border-border bg-card shadow-sm space-y-4">
          <h2 className="text-sm font-bold text-foreground">Harmonized Compliance Standards Mapping</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            {finding.frameworks.map((fw, idx) => (
              <div key={idx} className="p-3 rounded-lg border border-border bg-secondary/30 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-foreground">{fw.id}</span>
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-bold">
                    {fw.framework}
                  </span>
                </div>
                <p className="text-muted-foreground text-[11px]">{fw.category}</p>
                <div className="text-[10px] text-muted-foreground font-mono">
                  {fw.version || fw.revision || fw.release}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Risk Acceptance Modal */}
      <RiskAcceptanceModal
        isOpen={isRiskModalOpen}
        findingId={finding.id}
        onClose={() => setIsRiskModalOpen(false)}
        onSubmit={handleRiskAcceptanceSubmit}
      />
    </div>
  );
};
