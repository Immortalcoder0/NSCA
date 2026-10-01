import React from "react";
import { AlertTriangle, ArrowRight } from "lucide-react";
import type { UnauditedCapabilityItem } from "../types";
import { cn } from "../../shared/lib/utils";

interface UnauditedCapabilityBoxProps {
  capabilities: UnauditedCapabilityItem[];
  onAssess?: (item: UnauditedCapabilityItem) => void;
  className?: string;
}

export const UnauditedCapabilityBox: React.FC<UnauditedCapabilityBoxProps> = ({
  capabilities,
  onAssess,
  className,
}) => {
  if (!capabilities || capabilities.length === 0) return null;

  return (
    <div
      className={cn(
        "rounded-xl border border-amber-300 bg-amber-50/60 dark:bg-amber-950/40 dark:border-amber-800 p-4 space-y-3 text-xs shadow-sm",
        className
      )}
    >
      <div className="flex items-center gap-2 text-amber-900 dark:text-amber-200 font-bold text-sm">
        <AlertTriangle size={16} className="text-amber-600 dark:text-amber-400" />
        <span>Unaudited Surface & Scope Contamination</span>
      </div>

      <p className="text-amber-800 dark:text-amber-300 text-[11px]">
        Configuration elements discovered that listen or authenticate outside all selected audit framework controls.
      </p>

      <div className="space-y-2">
        {capabilities.map((cap, idx) => (
          <div
            key={idx}
            className="p-3 rounded-lg border border-amber-200 dark:border-amber-800 bg-background/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
          >
            <div className="space-y-0.5">
              <div className="font-mono font-bold text-foreground">
                {cap.path} (Port TCP/{cap.port})
              </div>
              <p className="text-muted-foreground text-[11px]">{cap.description}</p>
              <div className="text-[10px] text-amber-700 dark:text-amber-300 font-semibold mt-1">
                → {cap.controls_contaminated} controls downgraded to PASS (PARTIAL)
              </div>
            </div>

            <button
              onClick={() => onAssess?.(cap)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-amber-700 hover:bg-amber-800 text-white font-bold text-xs transition-colors shrink-0 shadow-sm self-start sm:self-center"
            >
              <span>Assess Capability</span>
              <ArrowRight size={13} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
