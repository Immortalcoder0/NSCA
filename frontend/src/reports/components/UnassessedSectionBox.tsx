import React from "react";
import { HelpCircle } from "lucide-react";
import type { ReportUnassessedControl } from "../types";
import { cn } from "../../shared/lib/utils";

interface UnassessedSectionBoxProps {
  determinedPercentage: number;
  undeterminedPercentage: number;
  items: ReportUnassessedControl[];
  className?: string;
}

export const UnassessedSectionBox: React.FC<UnassessedSectionBoxProps> = ({
  determinedPercentage = 78,
  undeterminedPercentage = 22,
  items,
  className,
}) => {
  return (
    <div
      className={cn(
        "p-6 rounded-xl border border-amber-300 bg-amber-50/60 dark:bg-amber-950/40 dark:border-amber-800 space-y-4 text-xs shadow-sm",
        className
      )}
    >
      <div className="flex items-center gap-2 font-bold text-sm text-amber-950 dark:text-amber-100">
        <HelpCircle size={18} className="text-amber-600 dark:text-amber-400" />
        <span>Section 6 · Unassessed Controls & Scope Boundaries</span>
      </div>

      <p className="text-amber-900 dark:text-amber-200 leading-relaxed">
        NSCA provides complete transparency on benchmark rules that could not be evaluated due to missing telemetry, uncollected targets, or manual-only inspection scopes.
      </p>

      {/* Unassessed Controls Table */}
      <div className="rounded-lg border border-amber-200 dark:border-amber-800 overflow-hidden bg-background">
        <table className="w-full text-left">
          <thead className="bg-amber-100/50 dark:bg-amber-950 text-amber-900 dark:text-amber-200 font-semibold border-b">
            <tr>
              <th className="p-2.5">Control ID</th>
              <th className="p-2.5">Title</th>
              <th className="p-2.5">Unassessed Rationale</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((item) => (
              <tr key={item.control_id} className="hover:bg-muted/30">
                <td className="p-2.5 font-mono font-bold text-foreground">{item.control_id}</td>
                <td className="p-2.5 font-medium text-foreground">{item.title}</td>
                <td className="p-2.5 text-muted-foreground text-[11px]">{item.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mandatory Verbatim Closing Statement (10-reporting.md §2 Section 6) */}
      <div className="p-4 rounded-lg bg-amber-100/70 dark:bg-amber-900/50 border border-amber-300 dark:border-amber-700 text-amber-950 dark:text-amber-100 font-serif italic text-xs leading-relaxed text-center">
        "This assessment determined {determinedPercentage}% of applicable controls. It is not a statement that the remaining {undeterminedPercentage}% are compliant."
      </div>
    </div>
  );
};
