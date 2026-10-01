import React from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  XCircle,
  FileCode,
  ArrowRight,
  Layers,
} from "lucide-react";
import type { IngestionArtifactItem } from "../types";
import { cn } from "../../shared/lib/utils";

interface ArtifactOutcomeCardProps {
  item: IngestionArtifactItem;
  className?: string;
}

export const ArtifactOutcomeCard: React.FC<ArtifactOutcomeCardProps> = ({
  item,
  className,
}) => {
  const renderStatusBadge = () => {
    switch (item.status) {
      case "parsed":
        return (
          <span
            role="status"
            aria-label="Status: Fully Parsed"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
          >
            <CheckCircle2 size={13} className="stroke-[2.5]" />
            <span>Parsed</span>
          </span>
        );

      case "parsed_with_caveat":
        return (
          <span
            role="status"
            aria-label="Status: Parsed with Caveat"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800"
          >
            <AlertTriangle size={13} className="stroke-[2]" />
            <span>Parsed with Caveat</span>
          </span>
        );

      case "platform_not_taught":
        return (
          <span
            role="status"
            aria-label="Status: Platform Not Taught"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold bg-purple-100 text-purple-900 dark:bg-purple-950/80 dark:text-purple-200 border border-purple-300 dark:border-purple-700"
          >
            <Sparkles size={13} />
            <span>NOT TAUGHT</span>
          </span>
        );

      case "unidentified":
      default:
        return (
          <span
            role="status"
            aria-label="Status: Unidentified"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border border-red-300 dark:border-red-800"
          >
            <XCircle size={13} className="stroke-[2.5]" />
            <span>Unidentified</span>
          </span>
        );
    }
  };

  return (
    <div
      className={cn(
        "p-4 rounded-xl border bg-card text-card-foreground shadow-sm transition-colors space-y-3",
        item.status === "platform_not_taught"
          ? "border-purple-300 dark:border-purple-900 bg-purple-50/20 dark:bg-purple-950/10"
          : "border-border",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          {renderStatusBadge()}
          <span className="font-mono font-bold text-sm text-foreground">{item.device}</span>
          {item.platform && (
            <span className="text-xs text-muted-foreground font-mono">
              {item.platform} {item.os_version}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {item.correlated_artifacts.length > 0 && (
            <span className="flex items-center gap-1 font-mono text-[11px] bg-secondary px-2 py-0.5 rounded">
              <Layers size={12} />
              {item.correlated_artifacts.length}{" "}
              {item.correlated_artifacts.length === 1 ? "artifact" : "artifacts correlated"}
            </span>
          )}
        </div>
      </div>

      {/* Correlated Artifact List Line */}
      {item.correlated_artifacts.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <span className="text-[11px] font-semibold text-slate-500">Sources:</span>
          {item.correlated_artifacts.map((art, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1 font-mono text-[11px] bg-muted/60 px-1.5 py-0.5 rounded border border-border/50 text-foreground"
            >
              <FileCode size={11} className="text-muted-foreground" />
              {art.name}
            </span>
          ))}
        </div>
      )}

      {/* Outcome-Specific Explanations & Invitations */}
      {item.status === "parsed_with_caveat" && (
        <div className="p-2.5 rounded bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 text-xs text-amber-900 dark:text-amber-200 flex items-center justify-between gap-2">
          <span>
            ⚠ <strong className="font-semibold">{item.export_mode || "Terse"} export</strong> detected →{" "}
            {item.unassessable_controls_count ?? 34} controls unassessable.
          </span>
        </div>
      )}

      {item.status === "platform_not_taught" && (
        <div className="p-3 rounded-lg bg-purple-100/70 dark:bg-purple-950/60 border border-purple-300 dark:border-purple-800 text-xs text-purple-900 dark:text-purple-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="font-bold flex items-center gap-1.5">
              <Sparkles size={14} className="text-purple-600 dark:text-purple-300" />
              <span>Training Questions Prepared ({item.training_questions_count ?? 9} questions)</span>
            </div>
            <p className="text-[11px] text-purple-800 dark:text-purple-300 mt-0.5">
              Grammar inferred at {(item.grammar_coverage ? item.grammar_coverage * 100 : 98.4).toFixed(1)}% line coverage.
              Est. time: {item.training_estimate_minutes ?? 8} min.
            </p>
          </div>

          <Link
            to={`/training/queue/${encodeURIComponent(item.platform || "mikrotik_routeros")}`}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-purple-700 text-white dark:bg-purple-600 font-bold hover:bg-purple-800 transition-colors shrink-0 shadow-sm"
          >
            <span>Teach Grammar</span>
            <ArrowRight size={13} />
          </Link>
        </div>
      )}

      {item.status === "unidentified" && (
        <div className="p-2.5 rounded bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/60 text-xs text-red-900 dark:text-red-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <span>
            ✗ Unidentified syntax (Grammar inference {((item.grammar_coverage || 0.43) * 100).toFixed(0)}% — unreliable).
          </span>
          <Link
            to="/training"
            className="font-bold text-red-700 dark:text-red-300 underline hover:no-underline text-xs"
          >
            Assisted grammar authoring →
          </Link>
        </div>
      )}
    </div>
  );
};
