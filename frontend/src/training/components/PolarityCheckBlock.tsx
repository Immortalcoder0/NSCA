import React from "react";
import { AlertTriangle, CheckSquare, Square } from "lucide-react";
import type { TrainingPolarityCheck } from "../types";
import { cn } from "../../shared/lib/utils";

interface PolarityCheckBlockProps {
  polarity: TrainingPolarityCheck;
  isConfirmed: boolean;
  onToggleConfirm: () => void;
  className?: string;
}

export const PolarityCheckBlock: React.FC<PolarityCheckBlockProps> = ({
  polarity,
  isConfirmed,
  onToggleConfirm,
  className,
}) => {
  if (!polarity.requires_explicit_confirmation) return null;

  return (
    <div
      className={cn(
        "p-4 rounded-xl border border-amber-400 bg-amber-50/90 dark:bg-amber-950/50 dark:border-amber-700 space-y-3 text-xs text-amber-950 dark:text-amber-200 shadow-md",
        className
      )}
    >
      <div className="flex items-center gap-2 text-amber-900 dark:text-amber-100 font-bold text-sm">
        <AlertTriangle size={17} className="text-amber-600 dark:text-amber-400 shrink-0" />
        <span>Mandatory Verification: Polarity Ambiguity Gate</span>
      </div>

      <p className="text-amber-800 dark:text-amber-300 leading-relaxed">
        {polarity.explanation || "Vendor syntax contains negated or inverted keywords. Incorrect polarity creates inverted audit verdicts."}
      </p>

      {/* Confirmation Checkbox */}
      <div
        onClick={onToggleConfirm}
        className={cn(
          "p-3 rounded-lg border cursor-pointer select-none transition-colors flex items-start gap-2.5",
          isConfirmed
            ? "bg-background border-emerald-500 text-foreground font-bold shadow-sm"
            : "bg-background/80 border-amber-300 dark:border-amber-800 text-foreground"
        )}
      >
        <button
          type="button"
          role="checkbox"
          aria-checked={isConfirmed}
          className="text-primary mt-0.5"
        >
          {isConfirmed ? (
            <CheckSquare size={17} className="text-emerald-600 dark:text-emerald-400" />
          ) : (
            <Square size={17} className="text-muted-foreground" />
          )}
        </button>

        <div className="space-y-0.5">
          <span className="text-xs font-semibold text-foreground block">
            {polarity.prompt}
          </span>
          <span className="text-[11px] text-muted-foreground block">
            I confirm the Boolean state is interpreted accurately before committing rulepack facts.
          </span>
        </div>
      </div>
    </div>
  );
};
