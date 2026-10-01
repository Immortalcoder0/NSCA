import React from "react";
import { ShieldCheck, Eye, Compass, Lock, TrendingUp } from "lucide-react";
import { cn } from "../../shared/lib/utils";

interface EstateStatStripProps {
  compliance: number;
  coverage: number;
  meaningfulRatio: number;
  security: number;
  deviceCount?: number;
  totalDeviceCount?: number;
  className?: string;
}

export const EstateStatStrip: React.FC<EstateStatStripProps> = ({
  compliance,
  coverage,
  meaningfulRatio,
  security,
  deviceCount = 389,
  totalDeviceCount = 412,
  className,
}) => {
  return (
    <div
      className={cn(
        "grid grid-cols-2 lg:grid-cols-4 gap-3.5 select-none",
        className
      )}
    >
      {/* KPI Tile 1: Coverage */}
      <div className="p-4 rounded-xl border border-border/80 bg-card shadow-xs hover:border-border transition-colors">
        <div className="flex items-center justify-between text-muted-foreground mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-[11px]">
            Estate Coverage
          </span>
          <div className="p-1.5 rounded-md bg-secondary text-foreground">
            <Eye size={15} />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-foreground">
            {Math.round(coverage * 100)}%
          </span>
          <span className="font-mono text-[11px] text-muted-foreground">
            ({deviceCount}/{totalDeviceCount})
          </span>
        </div>
      </div>

      {/* KPI Tile 2: Overall Compliance */}
      <div className="p-4 rounded-xl border border-border/80 bg-card shadow-xs hover:border-border transition-colors">
        <div className="flex items-center justify-between text-muted-foreground mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-[11px]">
            Overall Compliance
          </span>
          <div className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <ShieldCheck size={15} />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-foreground">
            {Math.round(compliance * 100)}%
          </span>
          <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium inline-flex items-center gap-0.5">
            <TrendingUp size={11} />
            +3%
          </span>
        </div>
      </div>

      {/* KPI Tile 3: Meaningful Ratio */}
      <div className="p-4 rounded-xl border border-border/80 bg-card shadow-xs hover:border-border transition-colors">
        <div className="flex items-center justify-between text-muted-foreground mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-[11px]">
            Meaningful Ratio
          </span>
          <div className="p-1.5 rounded-md bg-secondary text-foreground">
            <Compass size={15} />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-foreground">
            {Math.round(meaningfulRatio * 100)}%
          </span>
          <span className="text-[11px] text-muted-foreground font-mono">
            Non-vacuous
          </span>
        </div>
      </div>

      {/* KPI Tile 4: Security Posture */}
      <div className="p-4 rounded-xl border border-border/80 bg-card shadow-xs hover:border-border transition-colors">
        <div className="flex items-center justify-between text-muted-foreground mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-[11px]">
            Security Posture
          </span>
          <div className="p-1.5 rounded-md bg-secondary text-foreground">
            <Lock size={15} />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-foreground">
            {Math.round(security * 100)}%
          </span>
          <span className="font-mono text-[11px] text-muted-foreground">
            Weighted
          </span>
        </div>
      </div>
    </div>
  );
};
