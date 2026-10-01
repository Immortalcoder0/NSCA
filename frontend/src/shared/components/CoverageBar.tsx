import React from "react";
import { cn } from "../lib/utils";
import { VERDICT_TOKENS, type VerdictType } from "../theme/tokens";

export interface CoverageBreakdown {
  pass?: number;
  passPartial?: number;
  passVacuous?: number;
  fail?: number;
  unknown?: number;
  notApplicable?: number;
}

export interface CoverageBarProps {
  breakdown: CoverageBreakdown;
  showLegend?: boolean;
  showPercentages?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}

interface CoverageSegment {
  type: VerdictType;
  count: number;
  pct: number;
  bgClass: string;
  label: string;
}

export const CoverageBar: React.FC<CoverageBarProps> = ({
  breakdown,
  showLegend = true,
  showPercentages = true,
  size = "md",
  className,
}) => {
  const {
    pass = 0,
    passPartial = 0,
    passVacuous = 0,
    fail = 0,
    unknown = 0,
    notApplicable = 0,
  } = breakdown;

  const total =
    pass + passPartial + passVacuous + fail + unknown + notApplicable;

  const barHeights = {
    sm: "h-2",
    md: "h-3.5",
    lg: "h-5",
  };

  if (total === 0) {
    return (
      <div className={cn("w-full space-y-1.5", className)}>
        <div
          className={cn(
            "w-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden flex",
            barHeights[size]
          )}
        >
          <div className="w-full h-full bg-slate-300 dark:bg-slate-700 opacity-50" />
        </div>
        <p className="text-xs text-muted-foreground italic">No assessment data available</p>
      </div>
    );
  }

  const rawSegments: CoverageSegment[] = [
    {
      type: "PASS",
      count: pass,
      pct: (pass / total) * 100,
      bgClass: "bg-emerald-500",
      label: VERDICT_TOKENS.PASS.shortLabel,
    },
    {
      type: "PASS_PARTIAL",
      count: passPartial,
      pct: (passPartial / total) * 100,
      bgClass: "bg-amber-500",
      label: VERDICT_TOKENS.PASS_PARTIAL.shortLabel,
    },
    {
      type: "PASS_VACUOUS",
      count: passVacuous,
      pct: (passVacuous / total) * 100,
      bgClass: "bg-sky-500",
      label: VERDICT_TOKENS.PASS_VACUOUS.shortLabel,
    },
    {
      type: "FAIL",
      count: fail,
      pct: (fail / total) * 100,
      bgClass: "bg-red-500",
      label: VERDICT_TOKENS.FAIL.shortLabel,
    },
    {
      type: "UNKNOWN",
      count: unknown,
      pct: (unknown / total) * 100,
      bgClass: "bg-slate-500",
      label: VERDICT_TOKENS.UNKNOWN.shortLabel,
    },
    {
      type: "NOT_APPLICABLE",
      count: notApplicable,
      pct: (notApplicable / total) * 100,
      bgClass: "bg-slate-400",
      label: VERDICT_TOKENS.NOT_APPLICABLE.shortLabel,
    },
  ];

  const segments = rawSegments.filter((s) => s.count > 0);

  return (
    <div className={cn("w-full space-y-2 select-none", className)}>
      <div
        className={cn(
          "w-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden flex shadow-inner",
          barHeights[size]
        )}
        role="progressbar"
        aria-label="Assessment Coverage Breakdown"
        aria-valuenow={total > 0 ? Math.round(((pass + passPartial + passVacuous) / total) * 100) : 0}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        {segments.map((seg) => (
          <div
            key={seg.type}
            style={{ width: `${seg.pct}%` }}
            title={`${seg.label}: ${seg.count} (${seg.pct.toFixed(1)}%)`}
            className={cn("h-full transition-all duration-300 first:rounded-l-full last:rounded-r-full", seg.bgClass)}
          />
        ))}
      </div>

      {showLegend && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex flex-wrap items-center gap-3">
            {segments.map((seg) => (
              <div key={seg.type} className="flex items-center gap-1.5">
                <span className={cn("inline-block w-2.5 h-2.5 rounded-full shrink-0", seg.bgClass)} />
                <span className="text-muted-foreground font-medium">{seg.label}:</span>
                <span className="font-semibold text-foreground">{seg.count}</span>
                {showPercentages && (
                  <span className="text-muted-foreground text-[10px]">({seg.pct.toFixed(0)}%)</span>
                )}
              </div>
            ))}
          </div>
          <div className="text-muted-foreground font-medium text-[11px]">
            Total: <span className="font-semibold text-foreground">{total}</span>
          </div>
        </div>
      )}
    </div>
  );
};
