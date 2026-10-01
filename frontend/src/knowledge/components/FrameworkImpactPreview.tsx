import React from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { FrameworkUpdateDiff } from "../types";
import { cn } from "../../shared/lib/utils";

interface FrameworkImpactPreviewProps {
  diff: FrameworkUpdateDiff;
  onRatify?: () => void;
  onDefer?: () => void;
  className?: string;
}

export const FrameworkImpactPreview: React.FC<FrameworkImpactPreviewProps> = ({
  diff,
  onRatify,
  onDefer,
  className,
}) => {
  const isNegativeDelta = diff.estate_impact.net_compliance_delta < 0;

  return (
    <div className={cn("space-y-5 select-none", className)}>
      {/* Header Comparison Banner */}
      <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3">
          <div>
            <h3 className="text-base font-bold text-foreground">
              {diff.framework} Benchmark Update Review
            </h3>
            <p className="text-xs text-muted-foreground">
              Current: <strong className="font-mono text-foreground">{diff.current_version}</strong> → Available:{" "}
              <strong className="font-mono text-foreground">{diff.available_version}</strong>
              {diff.release_date ? ` (Released ${diff.release_date})` : ""}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {onDefer && (
              <button
                onClick={onDefer}
                className="px-3.5 py-1.5 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors"
              >
                Defer
              </button>
            )}
            {onRatify && (
              <button
                onClick={onRatify}
                className="flex items-center gap-1 px-4 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 transition-opacity shadow-sm"
              >
                <CheckCircle2 size={14} />
                <span>Ratify Benchmark Update</span>
              </button>
            )}
          </div>
        </div>

        {/* Content Rule Changes Count */}
        <div className="grid grid-cols-3 gap-3 text-center text-xs">
          <div className="p-3 rounded-lg bg-secondary/60 border border-border space-y-0.5">
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
              Added Rules
            </span>
            <span className="text-2xl font-black text-foreground font-mono">
              +{diff.added_controls_count}
            </span>
          </div>

          <div className="p-3 rounded-lg bg-secondary/60 border border-border space-y-0.5">
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
              Modified Rules
            </span>
            <span className="text-2xl font-black text-foreground font-mono">
              {diff.modified_controls_count}
            </span>
          </div>

          <div className="p-3 rounded-lg bg-secondary/60 border border-border space-y-0.5">
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
              Withdrawn Rules
            </span>
            <span className="text-2xl font-black text-muted-foreground font-mono">
              -{diff.withdrawn_controls_count}
            </span>
          </div>
        </div>
      </div>

      {/* Estate Dry Run Impact Forecast */}
      <div className="p-5 rounded-xl border border-purple-300 bg-purple-50/70 dark:bg-purple-950/40 dark:border-purple-800 space-y-3 text-xs text-purple-950 dark:text-purple-200 shadow-sm">
        <div className="flex items-center justify-between border-b border-purple-200 dark:border-purple-900/60 pb-2">
          <div className="flex items-center gap-2 font-bold text-sm text-purple-900 dark:text-purple-100">
            <AlertTriangle size={17} className="text-purple-600 dark:text-purple-400" />
            <span>Simulated Estate-Wide Impact Forecast</span>
          </div>

          <span
            className={cn(
              "font-mono font-bold px-2 py-0.5 rounded text-xs",
              isNegativeDelta
                ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300"
                : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
            )}
          >
            {isNegativeDelta
              ? `${Math.round(diff.estate_impact.net_compliance_delta * 100)}% Net Posture Shift`
              : `+${Math.round(diff.estate_impact.net_compliance_delta * 100)}% Net Posture Shift`}
          </span>
        </div>

        <p className="text-[11px] text-purple-800 dark:text-purple-300 leading-relaxed">
          Upgrading this benchmark tightens baseline audit criteria
          {diff.estate_impact.affected_devices !== undefined
            ? ` across ${diff.estate_impact.affected_devices} in-scope assets.`
            : "."}
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
          <div className="p-2.5 rounded-lg bg-background border border-purple-200 dark:border-purple-900">
            <span className="text-[10px] text-muted-foreground block uppercase font-mono">
              New Findings Introduced
            </span>
            <span className="font-mono font-bold text-red-600 dark:text-red-400 text-sm">
              +{diff.estate_impact.new_findings_predicted} Findings
            </span>
            <span className="text-[10px] text-muted-foreground block">Tighter security standards</span>
          </div>

          <div className="p-2.5 rounded-lg bg-background border border-purple-200 dark:border-purple-900">
            <span className="text-[10px] text-muted-foreground block uppercase font-mono">
              Severity Tightened
            </span>
            <span className="font-mono font-bold text-amber-600 dark:text-amber-400 text-sm">
              {diff.estate_impact.severity_tightened_count} Controls
            </span>
            <span className="text-[10px] text-muted-foreground block">Medium → High elevations</span>
          </div>

          <div className="p-2.5 rounded-lg bg-background border border-purple-200 dark:border-purple-900">
            <span className="text-[10px] text-muted-foreground block uppercase font-mono">
              Auto-Closed Findings
            </span>
            <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 text-sm">
              {diff.estate_impact.findings_auto_resolvable} Findings
            </span>
            <span className="text-[10px] text-muted-foreground block">Withdrawn / obsolete rules</span>
          </div>
        </div>
      </div>
    </div>
  );
};
