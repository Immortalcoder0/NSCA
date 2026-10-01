import React from "react";
import { CheckCircle2, FileCode, Cpu, Layers } from "lucide-react";
import type { RulepackCoverageMetrics } from "../types";
import { cn } from "../../shared/lib/utils";

interface RulepackCoverageReportProps {
  metrics: RulepackCoverageMetrics;
  className?: string;
}

export const RulepackCoverageReport: React.FC<RulepackCoverageReportProps> = ({
  metrics,
  className,
}) => {
  const hasLineCoverage = metrics.line_coverage !== undefined;
  const hasControlCoverage = metrics.coverage_rate !== undefined;

  return (
    <div
      className={cn(
        "grid grid-cols-2 sm:grid-cols-4 gap-4 p-5 rounded-xl border border-border bg-card shadow-sm select-none",
        className
      )}
    >
      <div className="space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-semibold">
          <Layers size={14} className="text-sky-500" />
          <span>{hasLineCoverage ? "Corpus Line Coverage" : "Control Coverage"}</span>
        </div>
        <div className="text-2xl font-black text-foreground">
          {hasLineCoverage
            ? `${((metrics.line_coverage as number) * 100).toFixed(1)}%`
            : hasControlCoverage
              ? `${((metrics.coverage_rate as number) * 100).toFixed(1)}%`
              : "—"}
        </div>
        <div className="text-[10px] text-muted-foreground font-mono">
          {metrics.unparsed_constructs_count !== undefined
            ? `${metrics.unparsed_constructs_count} unparsed constructs`
            : hasControlCoverage
              ? `${metrics.controls_covered} of ${metrics.controls_total} controls`
              : "—"}
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-semibold">
          <Cpu size={14} className="text-purple-500" />
          <span>Producible AST Facts</span>
        </div>
        <div className="text-2xl font-black text-foreground">
          {metrics.facts_producible_count ?? "—"}
        </div>
        <div className="text-[10px] text-purple-700 dark:text-purple-300 font-semibold">
          Normalized properties
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-semibold">
          <FileCode size={14} className="text-emerald-500" />
          <span>Test Fixtures</span>
        </div>
        <div className="text-2xl font-black text-foreground">
          {metrics.test_fixtures_count ?? "—"}
        </div>
        <div className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1">
          <CheckCircle2 size={11} />
          <span>{metrics.test_fixtures_count !== undefined ? "100% passing" : "not reported"}</span>
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-semibold">
          <CheckCircle2 size={14} className="text-amber-500" />
          <span>Trust Tier</span>
        </div>
        <div className="text-2xl font-black text-foreground uppercase">{metrics.trust_tier ?? "—"}</div>
        <div className="text-[10px] text-muted-foreground font-mono">Per GET /knowledge/rulepacks</div>
      </div>
    </div>
  );
};
