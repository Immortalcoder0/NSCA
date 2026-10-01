import React from "react";
import { Clock, ShieldCheck } from "lucide-react";
import type { SystemFreshnessModel } from "../types";
import { cn } from "../../shared/lib/utils";

interface KnowledgeFreshnessBoxProps {
  freshness: SystemFreshnessModel;
  className?: string;
}

export const KnowledgeFreshnessBox: React.FC<KnowledgeFreshnessBoxProps> = ({
  freshness,
  className,
}) => {
  return (
    <div
      className={cn(
        "p-5 rounded-xl border border-border bg-card shadow-sm space-y-4 select-none",
        className
      )}
    >
      <div className="flex items-center justify-between border-b pb-3">
        <div className="flex items-center gap-2">
          <Clock size={18} className="text-primary" />
          <h3 className="font-bold text-sm text-foreground">
            Knowledge & Offline Vulnerability Freshness
          </h3>
        </div>
        <span className="px-2.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 font-mono text-[10px] font-bold text-emerald-800 dark:text-emerald-300">
          HEALTH: {freshness.platform_health}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
        <div className="p-3 rounded-lg bg-secondary/50 space-y-1">
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
            Vulnerability DB Staleness
          </span>
          <span className="text-xl font-bold font-mono text-amber-600 dark:text-amber-400 block">
            {freshness.vulnerability_db_staleness_text}
          </span>
          <span className="text-[10px] text-muted-foreground">
            Last sync: {freshness.vulnerability_db_date}
          </span>
        </div>

        <div className="p-3 rounded-lg bg-secondary/50 space-y-1">
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
            Rulepack Catalog Status
          </span>
          <span className="text-xl font-bold text-foreground block">
            {freshness.rulepack_freshness_status === "UP_TO_DATE" ? "Up to Date" : "Update Available"}
          </span>
          <span className="text-[10px] text-emerald-600 font-medium flex items-center gap-1">
            <ShieldCheck size={11} />
            Certified Pinning Active
          </span>
        </div>

        <div className="p-3 rounded-lg bg-secondary/50 space-y-1">
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
            Engine Version
          </span>
          <span className="text-xl font-mono font-bold text-foreground block">
            {freshness.engine_version}
          </span>
          <span className="text-[10px] text-muted-foreground">Deterministic Core</span>
        </div>
      </div>
    </div>
  );
};
