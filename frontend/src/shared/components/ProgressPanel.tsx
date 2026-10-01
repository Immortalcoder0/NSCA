import React from "react";
import { CheckCircle2, Loader2, AlertCircle, Circle } from "lucide-react";
import { cn } from "../lib/utils";

export interface ProgressStep {
  id: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed";
  detail?: string;
}

export interface ProgressPanelProps {
  title: string;
  processedCount?: number;
  totalCount?: number;
  percentage?: number;
  steps?: ProgressStep[];
  currentStepLabel?: string;
  status?: "running" | "completed" | "failed";
  errorMessage?: string;
  className?: string;
}

export const ProgressPanel: React.FC<ProgressPanelProps> = ({
  title,
  processedCount,
  totalCount,
  percentage,
  steps,
  currentStepLabel,
  status = "running",
  errorMessage,
  className,
}) => {
  const calculatedPct =
    percentage !== undefined
      ? percentage
      : totalCount && totalCount > 0 && processedCount !== undefined
      ? Math.min(100, Math.round((processedCount / totalCount) * 100))
      : 0;

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-5 space-y-4 shadow-sm select-none",
        status === "failed" && "border-red-300 dark:border-red-900",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {status === "running" && (
            <Loader2 size={16} className="text-primary animate-spin" />
          )}
          {status === "completed" && (
            <CheckCircle2 size={16} className="text-emerald-500" />
          )}
          {status === "failed" && (
            <AlertCircle size={16} className="text-red-500" />
          )}
          <h3 className="text-sm font-bold text-foreground">{title}</h3>
        </div>

        <div className="text-xs font-mono font-bold text-muted-foreground">
          {processedCount !== undefined && totalCount !== undefined ? (
            <span>
              {processedCount} / {totalCount} ({calculatedPct}%)
            </span>
          ) : (
            <span>{calculatedPct}%</span>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full h-2.5 bg-secondary rounded-full overflow-hidden">
        <div
          style={{ width: `${calculatedPct}%` }}
          className={cn(
            "h-full transition-all duration-300 rounded-full",
            status === "failed"
              ? "bg-red-500"
              : status === "completed"
              ? "bg-emerald-500"
              : "bg-primary"
          )}
        />
      </div>

      {/* Current stage label or error */}
      {currentStepLabel && status === "running" && (
        <div className="text-xs text-muted-foreground italic flex items-center justify-between">
          <span>Current stage: {currentStepLabel}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-2.5 rounded bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-300">
          {errorMessage}
        </div>
      )}

      {/* Detailed Steps List (if provided) */}
      {steps && steps.length > 0 && (
        <div className="pt-2 border-t border-border space-y-2">
          {steps.map((step) => (
            <div
              key={step.id}
              className="flex items-center justify-between text-xs py-1"
            >
              <div className="flex items-center gap-2">
                {step.status === "completed" && (
                  <CheckCircle2 size={13} className="text-emerald-500 shrink-0" />
                )}
                {step.status === "running" && (
                  <Loader2 size={13} className="text-primary animate-spin shrink-0" />
                )}
                {step.status === "failed" && (
                  <AlertCircle size={13} className="text-red-500 shrink-0" />
                )}
                {step.status === "pending" && (
                  <Circle size={13} className="text-muted-foreground/50 shrink-0" />
                )}

                <span
                  className={cn(
                    "font-medium",
                    step.status === "running"
                      ? "text-primary font-semibold"
                      : step.status === "completed"
                      ? "text-foreground"
                      : "text-muted-foreground"
                  )}
                >
                  {step.label}
                </span>
              </div>

              {step.detail && (
                <span className="text-[11px] text-muted-foreground font-mono">
                  {step.detail}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
