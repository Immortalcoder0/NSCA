import React from "react";
import { Link } from "react-router-dom";
import { Sparkles, ArrowRight, Play, FileCode2, AlertCircle } from "lucide-react";
import type { TrainingQueueItem } from "../types";
import { cn } from "../../shared/lib/utils";

interface PlatformQueueCardProps {
  item: TrainingQueueItem;
  className?: string;
}

export const PlatformQueueCard: React.FC<PlatformQueueCardProps> = ({
  item,
  className,
}) => {
  const isNotTaught = item.status === "not_taught";
  const isPartial = item.status === "partial";
  const isUnidentified = item.status === "unidentified";

  return (
    <div
      className={cn(
        "p-5 rounded-xl border bg-card text-card-foreground shadow-xs hover:border-border transition-colors space-y-3.5",
        isNotTaught && "border-border/90",
        isPartial && "border-amber-300/80 dark:border-amber-900 bg-amber-50/10",
        isUnidentified && "border-rose-300/80 dark:border-rose-900 bg-rose-50/10",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/60 pb-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-bold text-base text-foreground tracking-tight">
              {item.display_name}
            </span>
            <span
              role="status"
              className={cn(
                "px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase",
                isNotTaught && "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700",
                isPartial && "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200 border border-amber-300 dark:border-amber-700",
                isUnidentified && "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200 border border-red-300 dark:border-red-700"
              )}
            >
              {item.status.replace(/_/g, " ")}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {item.device_count !== undefined
              ? `${item.device_count} collected ${item.device_count === 1 ? "device" : "devices"} awaiting AST grammar resolution`
              : "Awaiting AST grammar resolution"}
          </p>
        </div>

        {/* Action Buttons */}
        <div>
          {isNotTaught && (
            <Link
              to={`/training/questions?platform=${encodeURIComponent(item.platform)}`}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-primary hover:opacity-90 text-primary-foreground font-semibold text-xs transition-colors shadow-xs"
            >
              <Sparkles size={13} />
              <span>Begin Teaching Session</span>
              <ArrowRight size={13} />
            </Link>
          )}

          {isPartial && (
            <Link
              to={`/training/questions?platform=${encodeURIComponent(item.platform)}`}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs transition-colors shadow-xs"
            >
              <Play size={13} />
              <span>Resume Teaching</span>
              <ArrowRight size={13} />
            </Link>
          )}

          {isUnidentified && (
            <button
              onClick={() => alert("Assisted grammar authoring environment loaded.")}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md border border-rose-300 bg-rose-50 dark:bg-rose-950 text-rose-800 dark:text-rose-200 font-semibold text-xs transition-colors"
            >
              <FileCode2 size={13} />
              <span>Assisted Grammar Authoring</span>
            </button>
          )}
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="p-2.5 rounded-lg bg-secondary/50 border border-border/40">
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Current Coverage</span>
          <span className="font-bold text-sm text-foreground">
            {Math.round(item.current_coverage * 100)}%
          </span>
        </div>

        {item.grammar_coverage !== undefined && (
          <div className="p-2.5 rounded-lg bg-secondary/50 border border-border/40">
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Grammar Inferred</span>
            <span className="font-bold text-sm text-foreground">
              {(item.grammar_coverage * 100).toFixed(1)}%
            </span>
          </div>
        )}

        <div className="p-2.5 rounded-lg bg-secondary/50 border border-border/40">
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Questions</span>
          <span className="font-bold text-sm text-foreground">
            {item.question_count} items
          </span>
        </div>

        <div className="p-2.5 rounded-lg bg-secondary/50 border border-border/40">
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Est. Completion</span>
          <span className="font-bold text-sm text-foreground">
            {item.estimated_minutes !== undefined ? `~${item.estimated_minutes} min` : "—"}
          </span>
        </div>
      </div>

      {isUnidentified && (
        <div className="p-3 rounded-lg bg-rose-50/80 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-800 dark:text-rose-300 flex items-center gap-2">
          <AlertCircle size={14} className="shrink-0 text-rose-600" />
          <span>Grammar inference is below reliable teaching threshold (43%). Direct assisted authoring is required.</span>
        </div>
      )}
    </div>
  );
};
