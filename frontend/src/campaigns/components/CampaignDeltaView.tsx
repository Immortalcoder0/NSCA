import React from "react";
import {
  TrendingUp,
  TrendingDown,
  ShieldCheck,
  BookOpen,
  Server,
  AlertTriangle,
} from "lucide-react";
import type { CampaignComparisonData, DeltaDecompositionItem } from "../types";
import { cn } from "../../shared/lib/utils";

interface CampaignDeltaViewProps {
  data: CampaignComparisonData;
  className?: string;
}

export const CampaignDeltaView: React.FC<CampaignDeltaViewProps> = ({
  data,
  className,
}) => {
  const netDelta = data.compliance.to - data.compliance.from;
  const isPositive = netDelta >= 0;

  const renderCauseCard = (item: DeltaDecompositionItem, index: number) => {
    switch (item.cause) {
      case "verified_remediation":
        return (
          <div
            key={index}
            className="p-4 rounded-lg border border-emerald-300 bg-emerald-50/70 dark:bg-emerald-950/40 dark:border-emerald-800 space-y-1.5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300 font-semibold text-sm">
                <ShieldCheck size={16} />
                <span>Verified Remediation</span>
              </div>
              <span className="font-mono font-bold text-emerald-700 dark:text-emerald-300 text-sm">
                +{Math.round(item.delta * 100)}%
              </span>
            </div>
            <p className="text-xs text-emerald-900 dark:text-emerald-200">
              Resolved and verified {item.findings ?? 0} compliance findings.
            </p>
          </div>
        );

      case "framework_version_change":
        return (
          <div
            key={index}
            className="p-4 rounded-lg border border-purple-300 bg-purple-50/70 dark:bg-purple-950/40 dark:border-purple-800 space-y-1.5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-purple-800 dark:text-purple-300 font-semibold text-sm">
                <BookOpen size={16} />
                <span>Framework Benchmark Update</span>
              </div>
              <span className="font-mono font-bold text-purple-700 dark:text-purple-300 text-sm">
                {item.delta > 0 ? `+${Math.round(item.delta * 100)}%` : `${Math.round(item.delta * 100)}%`}
              </span>
            </div>
            <p className="text-xs text-purple-900 dark:text-purple-200">
              {item.detail || "Standards tightened; new rules and requirements added."}
            </p>
          </div>
        );

      case "scope_change":
        return (
          <div
            key={index}
            className="p-4 rounded-lg border border-sky-300 bg-sky-50/70 dark:bg-sky-950/40 dark:border-sky-800 space-y-1.5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sky-800 dark:text-sky-300 font-semibold text-sm">
                <Server size={16} />
                <span>Scope Delta</span>
              </div>
              <span className="font-mono font-bold text-sky-700 dark:text-sky-300 text-sm">
                {item.delta > 0 ? `+${Math.round(item.delta * 100)}%` : `${Math.round(item.delta * 100)}%`}
              </span>
            </div>
            <p className="text-xs text-sky-900 dark:text-sky-200">
              {item.detail || "Inventory adjustments, additions, or decommissions."}
            </p>
          </div>
        );

      case "configuration_regression":
      default:
        return (
          <div
            key={index}
            className="p-4 rounded-lg border border-red-300 bg-red-50/70 dark:bg-red-950/40 dark:border-red-800 space-y-1.5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-red-800 dark:text-red-300 font-semibold text-sm">
                <AlertTriangle size={16} />
                <span>Configuration Regression</span>
              </div>
              <span className="font-mono font-bold text-red-700 dark:text-red-300 text-sm">
                {item.delta > 0 ? `+${Math.round(item.delta * 100)}%` : `${Math.round(item.delta * 100)}%`}
              </span>
            </div>
            <p className="text-xs text-red-900 dark:text-red-200">
              {item.findings ? `${item.findings} newly introduced defects.` : "No regression detected."}
            </p>
          </div>
        );
    }
  };

  return (
    <div className={cn("space-y-6 select-none", className)}>
      {/* Top Net Compliance Shift Banner */}
      <div className="p-5 rounded-xl border border-border bg-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            Audit Period Comparison: {data.from} → {data.to}
          </div>
          <div className="flex items-baseline gap-3 mt-1">
            <span className="text-2xl font-black">
              {Math.round(data.compliance.from * 100)}%
            </span>
            <span className="text-muted-foreground text-sm font-medium">to</span>
            <span className="text-2xl font-black">
              {Math.round(data.compliance.to * 100)}%
            </span>
          </div>
        </div>

        <div
          className={cn(
            "inline-flex items-center gap-2 px-4 py-2 rounded-lg border font-bold text-sm",
            isPositive
              ? "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800"
              : "bg-red-50 text-red-800 border-red-300 dark:bg-red-950/60 dark:text-red-300 dark:border-red-800"
          )}
        >
          {isPositive ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
          <span>Net Shift: {isPositive ? `+${Math.round(netDelta * 100)}%` : `${Math.round(netDelta * 100)}%`}</span>
        </div>
      </div>

      {/* Delta Decomposition Section */}
      <div className="space-y-3">
        <div>
          <h3 className="text-sm font-bold text-foreground">Causal Delta Decomposition</h3>
          <p className="text-xs text-muted-foreground">
            Distinguishing actual security remediation from external framework rule changes and inventory shifts.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.decomposition.map((item, idx) => renderCauseCard(item, idx))}
        </div>
      </div>
    </div>
  );
};
