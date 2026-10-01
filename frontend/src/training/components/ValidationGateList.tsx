import React from "react";
import { CheckCircle2, XCircle, ShieldCheck } from "lucide-react";
import type { ValidationGateItem } from "../types";
import { cn } from "../../shared/lib/utils";

interface ValidationGateListProps {
  gates: ValidationGateItem[];
  className?: string;
}

export const ValidationGateList: React.FC<ValidationGateListProps> = ({
  gates,
  className,
}) => {
  const allPassed = gates.every((g) => g.status === "passed");

  return (
    <div className={cn("space-y-4 select-none", className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck size={18} className="text-primary" />
          <h3 className="font-bold text-sm text-foreground">Rulepack Validation Gates (6 of 6 Automated Checks)</h3>
        </div>
        <span
          className={cn(
            "px-2.5 py-0.5 rounded-full text-xs font-mono font-bold",
            allPassed
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
              : "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300"
          )}
        >
          {allPassed ? "ALL 6 GATES PASSED" : "VALIDATION FAILED"}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-2.5">
        {gates.map((gate) => {
          const isPassed = gate.status === "passed";
          return (
            <div
              key={gate.id}
              className={cn(
                "p-3.5 rounded-lg border flex items-start justify-between gap-3 text-xs",
                isPassed
                  ? "border-border bg-card"
                  : "border-red-300 dark:border-red-900 bg-red-50/30 dark:bg-red-950/20"
              )}
            >
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-foreground">{gate.name}</span>
                  <span className="text-[10px] text-muted-foreground font-mono">({gate.id})</span>
                </div>
                <p className="text-muted-foreground text-[11px]">{gate.description}</p>
                {gate.details && (
                  <p className="text-[11px] font-mono text-foreground pt-1">{gate.details}</p>
                )}
              </div>

              <div className="flex items-center gap-1 shrink-0">
                {isPassed ? (
                  <span className="inline-flex items-center gap-1 font-bold text-emerald-600 dark:text-emerald-400 font-mono text-[11px]">
                    <CheckCircle2 size={15} />
                    <span>PASSED</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 font-bold text-red-600 dark:text-red-400 font-mono text-[11px]">
                    <XCircle size={15} />
                    <span>FAILED</span>
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
