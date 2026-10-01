import React from "react";
import { Link } from "react-router-dom";
import { Zap, Wrench, ArrowRight, ShieldCheck } from "lucide-react";
import type { AttackPathModel } from "../types";
import { cn } from "../../shared/lib/utils";

interface AttackPathPayoffCardProps {
  path: AttackPathModel;
  className?: string;
}

export const AttackPathPayoffCard: React.FC<AttackPathPayoffCardProps> = ({
  path,
  className,
}) => {
  return (
    <div
      className={cn(
        "p-5 rounded-xl border border-red-300 bg-red-50/80 dark:bg-red-950/40 dark:border-red-800 space-y-3 text-xs text-red-950 dark:text-red-200 shadow-sm",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-red-200 dark:border-red-900/60 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-red-600 text-white">
            <Zap size={16} />
          </div>
          <div>
            <h3 className="font-bold text-sm text-red-950 dark:text-red-100">
              Optimal Remediation Cut-Point (Actionable Payoff)
            </h3>
            <p className="text-[11px] text-red-800 dark:text-red-300">
              Breaking any single link in this DAG completely neutralizes the reachable attack chain.
            </p>
          </div>
        </div>

        <Link
          to={`/remediation?finding=${path.payoff.recommended_break_finding_id}`}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-red-700 hover:bg-red-800 text-white font-bold text-xs transition-colors shrink-0 shadow-sm self-start sm:self-center"
        >
          <Wrench size={13} />
          <span>Remediate Cut-Point</span>
          <ArrowRight size={13} />
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
        <div className="p-2.5 rounded-lg bg-background border border-red-200 dark:border-red-900">
          <span className="text-[10px] text-muted-foreground block font-mono uppercase">Optimal Cut Finding</span>
          <span className="font-mono font-bold text-foreground block">
            {path.payoff.recommended_break_finding_id}
          </span>
          <span className="text-[11px] text-muted-foreground">{path.payoff.recommended_break_device}</span>
        </div>

        <div className="p-2.5 rounded-lg bg-background border border-red-200 dark:border-red-900">
          <span className="text-[10px] text-muted-foreground block font-mono uppercase">Blast-Radius Elimination</span>
          <span className="font-bold text-emerald-600 dark:text-emerald-400 block text-sm">
            {path.payoff.unreachable_findings_count} Downstream Findings
          </span>
          <span className="text-[11px] text-muted-foreground">Made unreachable</span>
        </div>

        <div className="p-2.5 rounded-lg bg-background border border-red-200 dark:border-red-900">
          <span className="text-[10px] text-muted-foreground block font-mono uppercase">Remediation Effort</span>
          <span className="font-bold text-foreground block">{path.payoff.cost_estimate}</span>
          <span className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1">
            <ShieldCheck size={12} />
            Safe (0 lockout risk)
          </span>
        </div>
      </div>
    </div>
  );
};
