import React from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import {
  Sparkles,
  TrendingUp,
  Clock,
  CheckCircle2,
  ArrowRight,
  Shield,
} from "lucide-react";
import { prettyPlatformName } from "../lib/prettyPlatformName";

// No backend endpoint aggregates "this teaching session's" elapsed time or
// coverage shift — `GET /training/metrics` (learning/transfer_metrics.py)
// only exposes a cross-session historical curve, and there is no
// `POST /training/sessions/{id}/complete` HTTP route (that service
// function, `transfer_metrics.complete_session`, is only ever called from
// platform test code today). So this screen's headline numbers are
// computed from real, locally-observed data handed off by
// TrainingQuestionPage via router `state` — actual wall-clock elapsed time
// (`Date.now()` at session start vs. session end) and the actual
// `impact.controls_unlocked` sum of the real questions this session
// confirmed, against the real total controls_unlocked for the platform's
// full question set (`GET /training/queue/{platform}`) — never a
// fabricated static number.
interface TrainingSessionState {
  platform: string;
  confirmations_count: number;
  confirmed_controls: number;
  total_controls: number;
  elapsed_ms: number;
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes} min ${seconds} s`;
}

export const TrainingResultPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const state = (location.state as TrainingSessionState | null) ?? null;

  const platform = searchParams.get("platform") || state?.platform || "mikrotik_routeros";
  const displayName = prettyPlatformName(platform);

  const hasSessionData = state !== null;
  const previousCoverage = 0; // "platform_not_taught" is 0% coverage by definition
  const newCoverage =
    hasSessionData && state.total_controls > 0 ? state.confirmed_controls / state.total_controls : 0;
  const confirmationsCount = state?.confirmations_count ?? 0;
  const elapsedFormatted = hasSessionData ? formatElapsed(state.elapsed_ms) : "0 min 0 s";

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="text-center space-y-2 py-4">
        <div className="inline-flex p-3 rounded-full bg-purple-100 dark:bg-purple-950 text-purple-600 dark:text-purple-400 mb-2">
          <Sparkles size={32} />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Teaching Session Completed Successfully
        </h1>
        <p className="text-xs text-muted-foreground max-w-md mx-auto">
          Grammar rules for <strong className="text-foreground">{displayName}</strong> have been extracted and mapped to normalized security properties.
        </p>
      </div>

      {!hasSessionData && (
        <div className="p-3 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-950/30 text-xs text-amber-800 dark:text-amber-300 text-center">
          This screen was opened directly (no live session data was handed off from the question flow), so the
          figures below default to zero rather than a fabricated example.
        </div>
      )}

      {/* Headline Result Payoff Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Coverage Shift Card */}
        <div className="p-6 rounded-xl border border-border bg-card shadow-sm space-y-2 text-center">
          <span className="text-xs font-mono uppercase text-muted-foreground font-semibold block">
            Automated Audit Coverage Shift
          </span>
          <div className="flex items-baseline justify-center gap-3">
            <span className="text-3xl font-black text-muted-foreground line-through">
              {Math.round(previousCoverage * 100)}%
            </span>
            <span className="text-muted-foreground text-sm font-medium">to</span>
            <span className="text-4xl font-black text-emerald-600 dark:text-emerald-400">
              {Math.round(newCoverage * 100)}%
            </span>
          </div>
          <div className="inline-flex items-center gap-1 font-bold text-xs text-emerald-600 bg-emerald-100 dark:bg-emerald-950 px-2.5 py-0.5 rounded-full">
            <TrendingUp size={13} />
            <span>+{Math.round((newCoverage - previousCoverage) * 100)}% Coverage Unlocked</span>
          </div>
        </div>

        {/* Elapsed Time & Confirmations Card */}
        <div className="p-6 rounded-xl border border-border bg-card shadow-sm space-y-2 text-center">
          <span className="text-xs font-mono uppercase text-muted-foreground font-semibold block">
            Assessor Teaching Efficiency
          </span>
          <div className="flex items-center justify-center gap-2 text-3xl font-black font-mono text-purple-700 dark:text-purple-300">
            <Clock size={28} />
            <span>{elapsedFormatted}</span>
          </div>
          <div className="inline-flex items-center gap-1 font-bold text-xs text-purple-700 dark:text-purple-300 bg-purple-100 dark:bg-purple-950 px-2.5 py-0.5 rounded-full">
            <CheckCircle2 size={13} />
            <span>{confirmationsCount} Confirmations Answered</span>
          </div>
        </div>
      </div>

      {/* Next Step Box */}
      <div className="p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs">
        <div className="space-y-1">
          <div className="font-bold text-sm text-foreground flex items-center gap-1.5">
            <Shield size={16} className="text-primary" />
            <span>Ready for Automated Validation & Two-Person Ratification</span>
          </div>
          <p className="text-muted-foreground text-[11px]">
            Candidate rules for <code>{platform}</code> were saved in the Synthesized/Provisional tier as each
            question was confirmed — see the ratification screen for the full list.
          </p>
        </div>

        <Link
          to={`/training/ratify?platform=${encodeURIComponent(platform)}`}
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-md bg-primary text-primary-foreground font-bold text-xs hover:opacity-90 transition-opacity shrink-0 shadow-sm"
        >
          <span>Review Validation Gates</span>
          <ArrowRight size={14} />
        </Link>
      </div>
    </div>
  );
};
