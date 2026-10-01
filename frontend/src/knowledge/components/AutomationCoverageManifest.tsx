import React from "react";
import { FileSpreadsheet } from "lucide-react";
import type { AutomationCoverageManifestData } from "../types";
import { cn } from "../../shared/lib/utils";

interface AutomationCoverageManifestProps {
  manifest: AutomationCoverageManifestData;
  className?: string;
}

export const AutomationCoverageManifest: React.FC<AutomationCoverageManifestProps> = ({
  manifest,
  className,
}) => {
  const autoPercent = Math.round((manifest.automated_count / manifest.total_controls) * 100);

  return (
    <div className={cn("space-y-6 select-none", className)}>
      {/* Top Coverage Strip */}
      <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3">
          <div className="space-y-0.5">
            <h3 className="text-base font-bold text-foreground flex items-center gap-2">
              <FileSpreadsheet size={18} className="text-primary" />
              <span>Automation Coverage Manifest</span>
            </h3>
            <p className="text-xs text-muted-foreground">
              {manifest.framework_name} {manifest.version} · {manifest.total_controls} total benchmark controls
            </p>
          </div>

          <span className="text-xs font-mono font-bold px-3 py-1 rounded bg-primary/10 text-primary self-start sm:self-center">
            {autoPercent}% Automated Engine Evaluation
          </span>
        </div>

        {/* 4 Manifest Classification Blocks */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 space-y-0.5">
            <span className="text-emerald-800 dark:text-emerald-300 font-semibold block text-[11px] uppercase">
              Fully Automated
            </span>
            <span className="text-2xl font-black text-emerald-900 dark:text-emerald-100 font-mono">
              {manifest.automated_count}
            </span>
            <span className="text-[10px] text-emerald-700 dark:text-emerald-400 block">
              Evaluated directly from AST
            </span>
          </div>

          <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 space-y-0.5">
            <span className="text-amber-800 dark:text-amber-300 font-semibold block text-[11px] uppercase">
              Manual-Only
            </span>
            <span className="text-2xl font-black text-amber-900 dark:text-amber-100 font-mono">
              {manifest.manual_only_count}
            </span>
            <span className="text-[10px] text-amber-700 dark:text-amber-400 block">
              Physical / policy checks
            </span>
          </div>

          <div className="p-3 rounded-lg bg-sky-50 dark:bg-sky-950/40 border border-sky-300 dark:border-sky-800 space-y-0.5">
            <span className="text-sky-800 dark:text-sky-300 font-semibold block text-[11px] uppercase">
              Data-Unavailable
            </span>
            <span className="text-2xl font-black text-sky-900 dark:text-sky-100 font-mono">
              {manifest.data_unavailable_count}
            </span>
            <span className="text-[10px] text-sky-700 dark:text-sky-400 block">
              Requires live telemetry
            </span>
          </div>

          <div className="p-3 rounded-lg bg-zinc-100 dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-800 space-y-0.5">
            <span className="text-zinc-700 dark:text-zinc-300 font-semibold block text-[11px] uppercase">
              Not Implemented
            </span>
            <span className="text-2xl font-black text-zinc-900 dark:text-zinc-100 font-mono">
              {manifest.not_implemented_count}
            </span>
            <span className="text-[10px] text-zinc-500 block">Roadmap scope</span>
          </div>
        </div>
      </div>

      {/* Manual-Only Reasons Disclosure */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-bold text-foreground">
              Manual-Only Controls & Justifications ({manifest.manual_only_items.length})
            </h4>
            <p className="text-xs text-muted-foreground">
              Full transparency on why automated AST evaluation is out-of-scope for specific controls.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2.5">
          {manifest.manual_only_items.map((item) => (
            <div
              key={item.control_id}
              className="p-4 rounded-xl border border-border bg-card space-y-2 text-xs"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-foreground">{item.framework_id ?? item.control_id}</span>
                  {item.framework_id && (
                    <span className="text-muted-foreground font-mono text-[11px]">({item.control_id})</span>
                  )}
                </div>
                <span className="px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-950 font-mono font-bold text-[10px] text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                  MANUAL AUDIT REQUIRED
                </span>
              </div>

              {item.title && <h5 className="font-semibold text-foreground text-sm">{item.title}</h5>}

              <div className="p-2.5 rounded bg-muted/60 text-muted-foreground space-y-1">
                <div>
                  <strong className="text-foreground">Automation Exclusion Rationale:</strong>{" "}
                  {item.reason}
                </div>
                {item.recommended_manual_procedure && (
                  <div className="text-[11px] text-foreground font-medium pt-1 border-t border-border/50">
                    <strong className="text-muted-foreground">Recommended Manual Procedure:</strong>{" "}
                    {item.recommended_manual_procedure}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
