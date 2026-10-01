import React from "react";
import { Link } from "react-router-dom";
import { ShieldAlert, ArrowRight } from "lucide-react";
import { cn } from "../../shared/lib/utils";

interface AttackPathBannerProps {
  pathCount?: number;
  criticalFindingCount?: number;
  className?: string;
}

export const AttackPathBanner: React.FC<AttackPathBannerProps> = ({
  pathCount = 3,
  criticalFindingCount = 6,
  className,
}) => {
  return (
    <div
      className={cn(
        "p-4 rounded-xl border border-red-300 bg-red-50/70 dark:bg-red-950/40 dark:border-red-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-red-950 dark:text-red-200 shadow-sm",
        className
      )}
    >
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-red-600 text-white shrink-0">
          <ShieldAlert size={18} />
        </div>
        <div>
          <div className="font-bold text-sm text-red-950 dark:text-red-100 flex items-center gap-1.5">
            <span>{pathCount} attack paths reach the core management plane</span>
          </div>
          <p className="text-red-800 dark:text-red-300 mt-0.5">
            Breaking {criticalFindingCount} key findings completely eliminates all {pathCount} reachable attack chains.
          </p>
        </div>
      </div>

      <Link
        to="/findings/attack-paths"
        className="flex items-center gap-1 px-3.5 py-1.5 rounded-md bg-red-700 hover:bg-red-800 text-white text-xs font-bold transition-colors shrink-0 shadow-sm"
      >
        <span>Explore Attack Paths</span>
        <ArrowRight size={13} />
      </Link>
    </div>
  );
};
