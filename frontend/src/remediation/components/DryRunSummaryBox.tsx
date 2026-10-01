import React from "react";
import { TrendingUp, AlertTriangle, ShieldCheck, CheckCircle2 } from "lucide-react";
import { SeverityBadge } from "../../shared/components/SeverityBadge";
import type { RemediationDryRunModel } from "../types";
import { cn } from "../../shared/lib/utils";

interface DryRunSummaryBoxProps {
  dryRun: RemediationDryRunModel;
  className?: string;
}

export const DryRunSummaryBox: React.FC<DryRunSummaryBoxProps> = ({
  dryRun,
  className,
}) => {
  const hasNewlyFailing = dryRun.newly_failing_controls.length > 0;

  return (
    <div className={cn("space-y-4 select-none", className)}>
      {/* Top Headline Banner */}
      <div className="p-5 rounded-xl border border-border bg-card flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
        <div className="space-y-1">
          <span className="text-xs font-mono uppercase text-muted-foreground tracking-wider">
            Simulated Posture Shift
          </span>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-black text-foreground">
              {Math.round(dryRun.metrics.before_compliance * 100)}%
            </span>
            <span className="text-muted-foreground text-sm font-medium">to</span>
            <span className="text-2xl font-black text-emerald-600 dark:text-emerald-400">
              {Math.round(dryRun.metrics.after_compliance * 100)}%
            </span>
            <span className="inline-flex items-center gap-1 font-bold text-xs text-emerald-600 bg-emerald-100 dark:bg-emerald-950 px-2 py-0.5 rounded">
              <TrendingUp size={14} />
              +{Math.round(dryRun.metrics.delta * 100)}% Compliance
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-300 text-emerald-800 dark:text-emerald-300 font-semibold flex items-center gap-1.5">
            <CheckCircle2 size={15} />
            <span>{dryRun.metrics.resolved_findings_count} Findings Resolved</span>
          </div>
        </div>
      </div>

      {/* CRITICAL: Newly Failing Controls Warning Block */}
      {hasNewlyFailing && (
        <div className="p-5 rounded-xl border border-amber-400 bg-amber-50/90 dark:bg-amber-950/50 dark:border-amber-700 space-y-3 text-xs text-amber-950 dark:text-amber-200 shadow-md">
          <div className="flex items-center gap-2 text-amber-900 dark:text-amber-100 font-bold text-sm">
            <AlertTriangle size={18} className="text-amber-600 dark:text-amber-400 shrink-0" />
            <span>⚠ Caution: Newly Failing Baseline Controls Detected (Side Effects)</span>
          </div>

          <p className="text-amber-800 dark:text-amber-300 leading-relaxed text-xs">
            Applying this playbook will resolve {dryRun.metrics.resolved_findings_count} targets, but introduces {dryRun.newly_failing_controls.length} new compliance violations. Review the side effects below before approving change execution:
          </p>

          <div className="space-y-2 pt-1">
            {dryRun.newly_failing_controls.map((item, idx) => (
              <div
                key={idx}
                className="p-3 rounded-lg bg-background border border-amber-300 dark:border-amber-800 space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-foreground">{item.control_id}</span>
                  <SeverityBadge severity={item.severity} size="sm" />
                </div>
                <h4 className="font-semibold text-foreground">{item.title}</h4>
                <p className="text-[11px] text-muted-foreground">{item.cause_description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!hasNewlyFailing && (
        <div className="p-3 rounded-lg bg-emerald-50/60 dark:bg-emerald-950/30 border border-emerald-300 text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
          <ShieldCheck size={16} className="text-emerald-600" />
          <span>Zero regression detected: No newly failing controls are introduced by this playbook.</span>
        </div>
      )}
    </div>
  );
};
