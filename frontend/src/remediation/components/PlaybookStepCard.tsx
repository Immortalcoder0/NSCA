import React, { useState } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  RotateCcw,
  Terminal,
  ChevronDown,
  ChevronUp,
  Server,
  ArrowRight,
} from "lucide-react";
import type { PlaybookStepModel } from "../types";
import { cn } from "../../shared/lib/utils";

interface PlaybookStepCardProps {
  step: PlaybookStepModel;
  className?: string;
}

export const PlaybookStepCard: React.FC<PlaybookStepCardProps> = ({
  step,
  className,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const isLockout = step.impact === "lockout_risk";
  const isSvcAffecting = step.impact === "service_affecting";

  return (
    <div
      className={cn(
        "rounded-2xl border bg-card text-card-foreground shadow-card hover:shadow-elevated transition-all duration-200 text-xs overflow-hidden",
        isLockout
          ? "border-amber-400/80 dark:border-amber-800 bg-amber-50/20"
          : isSvcAffecting
          ? "border-red-300/80 dark:border-red-900 bg-red-50/20"
          : "border-border/70",
        className
      )}
    >
      {/* Step Header */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 cursor-pointer hover:bg-secondary/30 select-none transition-colors"
      >
        <div className="flex items-center gap-3.5">
          <span
            className={cn(
              "w-8 h-8 rounded-full font-mono font-black text-xs flex items-center justify-center shrink-0 shadow-md",
              isLockout
                ? "bg-amber-500 text-white shadow-amber-500/25"
                : isSvcAffecting
                ? "bg-red-600 text-white shadow-red-600/25"
                : "bg-primary text-primary-foreground shadow-primary/25"
            )}
          >
            {step.step_number}
          </span>

          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-bold text-foreground tracking-tight">{step.title}</h3>
              <span
                role="status"
                aria-label={`Impact Level: ${step.impact}`}
                className={cn(
                  "px-2.5 py-0.5 rounded-full font-mono font-bold uppercase text-[10px] shadow-sm",
                  isLockout && "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200 border border-amber-300 dark:border-amber-800 flex items-center gap-1",
                  isSvcAffecting && "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200 border border-red-300 dark:border-red-800 flex items-center gap-1",
                  step.impact === "safe" && "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-800 flex items-center gap-1"
                )}
              >
                {isLockout ? (
                  <>
                    <ShieldAlert size={12} className="text-amber-600" />
                    <span>⚠ LOCKOUT RISK</span>
                  </>
                ) : isSvcAffecting ? (
                  <>
                    <ShieldAlert size={12} className="text-red-600" />
                    <span>SERVICE AFFECTING</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck size={12} className="text-emerald-600" />
                    <span>SAFE (NON-DISRUPTIVE)</span>
                  </>
                )}
              </span>
            </div>

            <div className="flex items-center gap-2 text-muted-foreground text-[11px] font-mono">
              <span className="flex items-center gap-1 text-foreground font-semibold bg-secondary/80 px-2 py-0.5 rounded-full">
                <Server size={11} className="text-indigo-500" />
                {step.device_hostname}
              </span>
              <span>·</span>
              <span>{step.commands.length} commands</span>
              <span>·</span>
              <span>Resolves: {step.findings_resolved.join(", ")}</span>
            </div>
          </div>
        </div>

        <button
          aria-label={isExpanded ? "Collapse step commands" : "Expand step commands"}
          className="text-muted-foreground hover:text-foreground self-end sm:self-center p-1.5 rounded-full hover:bg-secondary transition-colors"
        >
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* Expanded Details: Commands & Rollback */}
      {isExpanded && (
        <div className="p-5 pt-0 space-y-4 border-t border-border/60 mt-1">
          {/* Lockout / Operational Warning Box */}
          {step.impact_warning && (
            <div className="p-4 rounded-xl bg-amber-50/90 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2.5 shadow-sm">
              <ShieldAlert size={17} className="text-amber-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block text-xs">Operator Safety Precaution:</span>
                <p className="text-[11px] text-amber-800 dark:text-amber-300 leading-relaxed mt-0.5">
                  {step.impact_warning}
                </p>
              </div>
            </div>
          )}

          {/* Ordering Dependency Sequencing */}
          {(step.depends_on_steps || step.precedes_steps) && (
            <div className="p-3 rounded-xl bg-secondary/50 text-xs space-y-1 text-muted-foreground border border-border/60">
              {step.depends_on_steps && step.depends_on_steps.length > 0 && (
                <div className="flex items-center gap-1.5 font-medium">
                  <ArrowRight size={12} className="text-primary" />
                  <span>
                    Must follow step {step.depends_on_steps.join(", ")} (prerequisite authentication setup).
                  </span>
                </div>
              )}
              {step.precedes_steps && step.precedes_steps.length > 0 && (
                <div className="flex items-center gap-1.5 font-medium">
                  <ArrowRight size={12} className="text-primary" />
                  <span>
                    Must precede step {step.precedes_steps.join(", ")} before committing changes.
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Forward Remediation CLI Commands */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-muted-foreground font-semibold text-[11px]">
              <span className="flex items-center gap-1.5 uppercase tracking-wider text-foreground">
                <Terminal size={13} className="text-primary" />
                Remediation CLI Commands
              </span>
              <span className="font-mono text-[10px] bg-secondary px-2 py-0.5 rounded-full">{step.device_platform}</span>
            </div>
            <pre className="p-3.5 rounded-xl bg-[#0d1117] text-slate-100 font-mono text-xs overflow-x-auto leading-relaxed border border-slate-800 shadow-md">
              {step.commands.join("\n")}
            </pre>
          </div>

          {/* Rollback Safety Commands */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-muted-foreground font-semibold text-[11px]">
              <span className="flex items-center gap-1.5 uppercase tracking-wider text-amber-700 dark:text-amber-400">
                <RotateCcw size={13} />
                Safety Rollback Script
              </span>
              <span className="text-[10px] text-muted-foreground">Emergency Undo</span>
            </div>
            <pre className="p-3.5 rounded-xl bg-slate-900 text-slate-300 font-mono text-xs overflow-x-auto leading-relaxed border border-slate-800 shadow-md">
              {step.rollback_commands.join("\n")}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
