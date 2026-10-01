import React, { useMemo } from "react";
import { Network, ShieldCheck } from "lucide-react";
import type { AttackPathModel } from "../types";
import { cn } from "../../shared/lib/utils";

export interface AttackPathEstateSummaryBannerProps {
  paths: AttackPathModel[];
  targetLabel?: string;
  className?: string;
}

/**
 * Estate-level rollup for the attack path explorer — `<SystemicFindingBanner>`'s
 * sibling summary component (frontend-02 §2.4 / 12-ux-specification.md §4):
 * "3 attack paths reach the core management plane · Breaking 6 findings
 * eliminates all 3." Surfaces the cross-path payoff (the set of distinct
 * findings that, if remediated, break every listed chain) above the
 * per-path detail, per U4 ("lead with action").
 */
export const AttackPathEstateSummaryBanner: React.FC<AttackPathEstateSummaryBannerProps> = ({
  paths,
  targetLabel = "the core management plane",
  className,
}) => {
  const { pathCount, distinctBreakFindingCount } = useMemo(() => {
    const breakFindings = new Set(paths.map((p) => p.payoff.recommended_break_finding_id));
    return {
      pathCount: paths.length,
      distinctBreakFindingCount: breakFindings.size,
    };
  }, [paths]);

  if (pathCount === 0) return null;

  return (
    <div
      className={cn(
        "p-5 rounded-2xl border border-red-300/80 bg-red-50/90 dark:bg-red-950/40 dark:border-red-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs text-red-950 dark:text-red-200 shadow-card",
        className
      )}
    >
      <div className="flex items-start gap-3.5">
        <div className="p-2.5 rounded-xl bg-gradient-to-tr from-red-600 to-rose-500 text-white shrink-0 mt-0.5 shadow-sm">
          <Network size={18} />
        </div>
        <div className="space-y-1">
          <div className="font-bold text-sm text-red-950 dark:text-red-100">
            {pathCount} attack {pathCount === 1 ? "path" : "paths"} reach {targetLabel}
          </div>
          <p className="text-red-900/80 dark:text-red-300/90 text-xs leading-relaxed flex items-center gap-1.5">
            <ShieldCheck size={13} className="shrink-0" />
            Breaking {distinctBreakFindingCount} {distinctBreakFindingCount === 1 ? "finding" : "findings"} eliminates all {pathCount}.
          </p>
        </div>
      </div>
    </div>
  );
};
