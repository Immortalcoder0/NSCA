import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  ChevronDown,
  ChevronUp,
  Wrench,
  MessageSquare,
  ShieldAlert,
  UserPlus,
  Server,
  ExternalLink,
} from "lucide-react";
import { VerdictBadge } from "../../shared/components/VerdictBadge";
import { SeverityBadge } from "../../shared/components/SeverityBadge";
import { TrustTierBadge } from "../../shared/components/TrustTierBadge";
import { EvidenceExcerpt } from "../../shared/components/EvidenceExcerpt";
import type { FindingModel } from "../types";
import { cn } from "../../shared/lib/utils";

export interface FindingCardProps {
  finding: FindingModel;
  initialExpanded?: boolean;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: (id: string, selected: boolean) => void;
  onRemediate?: (id: string) => void;
  onDispute?: (id: string) => void;
  onAcceptRisk?: (id: string) => void;
  onAssign?: (id: string) => void;
  className?: string;
}

export const FindingCard: React.FC<FindingCardProps> = ({
  finding,
  initialExpanded = false,
  selectable = false,
  selected = false,
  onSelect,
  onRemediate,
  onDispute,
  onAcceptRisk,
  onAssign,
  className,
}) => {
  const [isExpanded, setIsExpanded] = useState(initialExpanded);

  const primaryEvidence = finding.evidence[0];

  return (
    <div
      className={cn(
        "rounded-2xl border border-border/70 bg-card shadow-card hover:shadow-elevated transition-all duration-200 text-xs overflow-hidden",
        selected && "border-primary ring-2 ring-primary/20 bg-primary/5",
        className
      )}
    >
      {/* Header Bar */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer hover:bg-secondary/30 select-none transition-colors"
      >
        <div className="flex items-start gap-3.5 flex-1">
          {selectable && (
            <input
              type="checkbox"
              checked={selected}
              onChange={(e) => {
                e.stopPropagation();
                onSelect?.(finding.id, e.target.checked);
              }}
              className="mt-1 rounded-md border-border cursor-pointer accent-primary"
            />
          )}

          <div className="space-y-1.5 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono font-bold text-foreground text-sm">{finding.control_id}</span>
              <span className="text-muted-foreground font-mono text-[11px]">({finding.id})</span>
              <VerdictBadge verdict={finding.verdict} size="sm" />
              <SeverityBadge severity={finding.severity.effective} size="sm" />
              {finding.rulepack_trust_tier !== "CERTIFIED" && (
                <TrustTierBadge tier={finding.rulepack_trust_tier} size="sm" />
              )}
              <span className="text-muted-foreground font-mono text-[11px] flex items-center gap-1 bg-secondary/70 px-2 py-0.5 rounded-full">
                <Server size={11} className="text-indigo-500" />
                <span>{finding.hostname}</span>
              </span>
            </div>

            <h3 className="text-sm font-bold text-foreground tracking-tight">{finding.title}</h3>

            <div className="flex flex-wrap items-center gap-2 text-muted-foreground text-[11px]">
              {finding.severity.reason && (
                <span className="text-amber-700 dark:text-amber-300 font-medium">
                  {finding.severity.base} → <strong className="font-bold">{finding.severity.effective}</strong> (
                  {finding.severity.reason})
                </span>
              )}
              <span>·</span>
              <div className="flex flex-wrap gap-1.5">
                {finding.frameworks.map((fw, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded-full bg-secondary/80 font-mono text-[10px] uppercase font-semibold text-foreground border border-border/50"
                  >
                    {fw.id}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-center">
          <Link
            to={`/findings/${finding.id}`}
            onClick={(e) => e.stopPropagation()}
            title="Open Finding Detail View"
            className="p-1.5 rounded-full text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
          >
            <ExternalLink size={14} />
          </Link>
          <button
            aria-label={isExpanded ? "Collapse finding" : "Expand finding"}
            className="text-muted-foreground hover:text-foreground p-1.5 rounded-full hover:bg-secondary transition-colors"
          >
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {/* Expanded Details & Inline Evidence Excerpt */}
      {isExpanded && (
        <div className="p-5 pt-0 space-y-4 border-t border-border/60 mt-1">
          {primaryEvidence && (
            <div className="space-y-2 pt-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-muted-foreground text-[11px] uppercase tracking-wider">
                  Evidence Excerpt · {primaryEvidence.artifact} (Lines {primaryEvidence.lines[0]}–{primaryEvidence.lines[1]})
                </span>
                {finding.attack_paths.length > 0 && (
                  <Link
                    to="/findings/attack-paths"
                    className="text-[11px] font-bold text-rose-600 dark:text-rose-400 hover:underline flex items-center gap-1"
                  >
                    <span>Contributes to {finding.attack_paths.join(", ")}</span>
                  </Link>
                )}
              </div>
              <EvidenceExcerpt
                content={primaryEvidence.excerpt}
                startLineNumber={primaryEvidence.lines[0]}
                highlightLines={primaryEvidence.highlight}
                filename={primaryEvidence.artifact}
              />
            </div>
          )}

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-border/50">
            <Link
              to={`/remediation?finding=${finding.id}`}
              onClick={(e) => {
                e.stopPropagation();
                onRemediate?.(finding.id);
              }}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-primary text-primary-foreground font-semibold hover:opacity-90 transition-all shadow-sm shadow-primary/20"
            >
              <Wrench size={13} />
              <span>Remediate</span>
            </Link>

            <Link
              to={`/findings/${finding.id}/dispute`}
              onClick={(e) => {
                e.stopPropagation();
                onDispute?.(finding.id);
              }}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border border-border/80 text-foreground font-semibold hover:bg-secondary transition-colors"
            >
              <MessageSquare size={13} />
              <span>Dispute / Compensating Control</span>
            </Link>

            <button
              onClick={(e) => {
                e.stopPropagation();
                onAcceptRisk?.(finding.id);
              }}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border border-border/80 text-foreground font-semibold hover:bg-secondary transition-colors"
            >
              <ShieldAlert size={13} />
              <span>Accept Risk</span>
            </button>

            <button
              onClick={(e) => {
                e.stopPropagation();
                onAssign?.(finding.id);
              }}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border border-border/80 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors ml-auto"
            >
              <UserPlus size={13} />
              <span>{finding.assigned_to ? `Assigned: ${finding.assigned_to}` : "Assign"}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
