import React from "react";
import { Sparkles, ArrowRight } from "lucide-react";
import type { TrainingPlainReading } from "../types";
import { cn } from "../../shared/lib/utils";

interface PlainReadingBlockProps {
  reading: TrainingPlainReading;
  className?: string;
}

export const PlainReadingBlock: React.FC<PlainReadingBlockProps> = ({
  reading,
  className,
}) => {
  return (
    <div
      className={cn(
        "p-4 rounded-xl border border-purple-300 bg-purple-50/70 dark:bg-purple-950/40 dark:border-purple-800 space-y-2.5 text-xs text-purple-950 dark:text-purple-200 shadow-sm",
        className
      )}
    >
      <div className="flex items-center gap-1.5 font-bold text-sm text-purple-900 dark:text-purple-100">
        <Sparkles size={16} className="text-purple-600 dark:text-purple-400" />
        <span>Our Interpretation (Plain-Language Meaning)</span>
      </div>

      <p className="text-[11px] text-purple-800 dark:text-purple-300">
        The engine infers that this device configuration clause asserts the following normalized property:
      </p>

      {/* Plain Language Statement */}
      <div className="p-3 rounded-lg bg-background border border-purple-200 dark:border-purple-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 font-medium">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-foreground text-xs">{reading.raw_clause}</span>
          <ArrowRight size={14} className="text-purple-600 dark:text-purple-400 shrink-0" />
          <span className="text-foreground font-bold text-sm">{reading.statement}</span>
        </div>

        <span className="px-2 py-0.5 rounded bg-purple-100 dark:bg-purple-950/80 font-mono text-[10px] font-bold text-purple-800 dark:text-purple-300">
          {reading.normalized_property}
        </span>
      </div>
    </div>
  );
};
