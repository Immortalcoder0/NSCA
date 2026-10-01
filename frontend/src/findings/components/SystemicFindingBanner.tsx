import React from "react";
import { Link } from "react-router-dom";
import { Network, CheckCircle2, UserPlus } from "lucide-react";
import { cn } from "../../shared/lib/utils";

export interface SystemicFindingBannerProps {
  systemicId?: string;
  affectedCount?: number;
  totalGroupCount?: number;
  groupName?: string;
  defectSummary?: string;
  onAdjudicateAll?: () => void;
  onAssignAll?: () => void;
  className?: string;
}

export const SystemicFindingBanner: React.FC<SystemicFindingBannerProps> = ({
  systemicId = "SF-004",
  affectedCount = 31,
  totalGroupCount = 40,
  groupName = "branch routers",
  defectSummary = "Golden build-template defect, not independent errors. Single template fix resolves all instances.",
  onAdjudicateAll,
  onAssignAll,
  className,
}) => {
  return (
    <div
      className={cn(
        "p-5 rounded-2xl border border-amber-300/80 bg-amber-50/90 dark:bg-amber-950/40 dark:border-amber-700/60 flex flex-col md:flex-row md:items-center justify-between gap-4 text-xs text-amber-950 dark:text-amber-200 shadow-card",
        className
      )}
    >
      <div className="flex items-start gap-3.5">
        <div className="p-2.5 rounded-xl bg-gradient-to-tr from-amber-600 to-orange-500 text-white shrink-0 mt-0.5 shadow-sm">
          <Network size={18} />
        </div>
        <div className="space-y-1">
          <div className="font-bold text-sm text-amber-950 dark:text-amber-100 flex items-center gap-2">
            <span>ⓘ SYSTEMIC FINDING {systemicId}</span>
            <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-amber-200/90 dark:bg-amber-900/80 font-bold border border-amber-300 dark:border-amber-700 text-amber-900 dark:text-amber-200">
              {affectedCount} of {totalGroupCount} {groupName}
            </span>
          </div>
          <p className="text-amber-900/80 dark:text-amber-300/90 text-xs leading-relaxed">{defectSummary}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
        {onAssignAll && (
          <button
            onClick={onAssignAll}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border border-amber-300 bg-background hover:bg-secondary text-foreground font-semibold transition-colors shadow-subtle"
          >
            <UserPlus size={13} />
            <span>Assign All {affectedCount}</span>
          </button>
        )}

        {onAdjudicateAll && (
          <button
            onClick={onAdjudicateAll}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-amber-700 hover:bg-amber-800 text-white font-bold transition-all shadow-sm shadow-amber-700/20"
          >
            <CheckCircle2 size={13} />
            <span>Adjudicate All {affectedCount}</span>
          </button>
        )}

        <Link
          to={`/findings?systemic=${systemicId}`}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border border-border/80 text-foreground font-semibold hover:bg-secondary transition-colors"
        >
          <span>View Cluster</span>
        </Link>
      </div>
    </div>
  );
};
