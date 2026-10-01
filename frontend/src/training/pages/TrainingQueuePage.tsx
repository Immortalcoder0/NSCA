import React from "react";
import { Sparkles, Loader2, AlertTriangle, Inbox } from "lucide-react";
import { PlatformQueueCard } from "../components/PlatformQueueCard";
import { useTrainingQueue } from "../../shared/api/hooks";
import { prettyPlatformName } from "../lib/prettyPlatformName";
import type { TrainingQueueItem } from "../types";

export const TrainingQueuePage: React.FC = () => {
  const { data, isLoading, isError, error } = useTrainingQueue();

  // Real `GET /training/queue` (services/training.py
  // platforms_with_pending_questions) now reports a real coverage fraction
  // and derives `gap` from it, so "partial" is reachable with real data —
  // it has no device inventory or time-estimate fields, so those remain
  // undefined rather than fabricated (see PlatformQueueCard.tsx). The
  // "unidentified" state still has no backing signal from this endpoint.
  const queue: TrainingQueueItem[] = (data?.platforms ?? []).map((p) => ({
    platform: p.platform,
    display_name: prettyPlatformName(p.platform),
    status: p.gap === "platform_not_taught" ? "not_taught" : "partial",
    current_coverage: p.coverage ?? 0,
    question_count: p.questions_remaining,
  }));

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-purple-600 dark:text-purple-400">
          <Sparkles size={24} />
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Training Studio Learning Queue</h1>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Zero-code interactive grammar teaching. Ingest untaught vendor platforms and bring coverage from 0% to ≥70% in under 10 minutes.
        </p>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-6 justify-center">
          <Loader2 size={16} className="animate-spin" />
          <span>Loading training queue from the platform API…</span>
        </div>
      )}

      {isError && (
        <div className="p-4 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300 flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>Failed to load the training queue: {error instanceof Error ? error.message : "unknown error"}</span>
        </div>
      )}

      {!isLoading && !isError && queue.length === 0 && (
        <div className="p-6 rounded-xl border border-border/80 bg-card text-xs text-muted-foreground flex flex-col items-center gap-2 text-center">
          <Inbox size={22} className="text-muted-foreground" />
          <span>No untaught platforms are queued right now — every ingested platform already has a certified rulepack.</span>
        </div>
      )}

      {/* Queue Cards */}
      <div className="space-y-4">
        {queue.map((item) => (
          <PlatformQueueCard key={item.platform} item={item} />
        ))}
      </div>
    </div>
  );
};
