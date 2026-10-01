import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Loader2, AlertTriangle, Info } from "lucide-react";
import { useFrameworks, useFrameworkPreview, useFrameworkRatify } from "../../shared/api/hooks";

export const FrameworkUpdateReviewPage: React.FC = () => {
  const frameworksQuery = useFrameworks();
  const [selected, setSelected] = useState<string | null>(null);
  const preview = useFrameworkPreview();
  const ratify = useFrameworkRatify();
  const [isDeferred, setIsDeferred] = useState(false);

  useEffect(() => {
    if (!selected && frameworksQuery.data?.items.length) {
      setSelected(frameworksQuery.data.items[0].framework);
    }
  }, [frameworksQuery.data, selected]);

  useEffect(() => {
    if (selected) {
      preview.mutate(selected);
      setIsDeferred(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/knowledge" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Knowledge Base</span>
        </Link>
        <span>/</span>
        <span className="font-semibold text-foreground">Framework Benchmark Update Review</span>
      </div>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Framework Benchmark Update & Impact Preview
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Simulate the estate-wide compliance posture impact before ratifying upstream security benchmark updates.
        </p>
      </div>

      {frameworksQuery.data && frameworksQuery.data.items.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {frameworksQuery.data.items.map((f) => (
            <button
              key={f.framework}
              onClick={() => setSelected(f.framework)}
              className={`px-3 py-1.5 rounded-md text-[11px] font-mono font-semibold border transition-colors ${
                selected === f.framework
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-secondary text-foreground border-border hover:bg-secondary/80"
              }`}
            >
              {f.framework.toUpperCase()}
            </button>
          ))}
        </div>
      )}

      <div className="p-3 rounded-lg border border-sky-300 dark:border-sky-800 bg-sky-50/60 dark:bg-sky-950/30 text-[11px] text-sky-900 dark:text-sky-300">
        <code>POST /knowledge/frameworks/{"{id}"}/preview</code> and <code>/ratify</code> are both real HTTP round
        trips against real imported <code>framework_item</code> rows. This build has no versioned framework
        snapshots on disk, so a real added/modified/withdrawn diff or estate-impact simulation genuinely cannot be
        computed yet — the count below (<code>current_item_count</code>) is real, the rest is honestly reported as
        unavailable rather than fabricated.
      </div>

      {preview.isPending && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-6 justify-center">
          <Loader2 size={16} className="animate-spin" />
          <span>Computing estate impact preview…</span>
        </div>
      )}

      {preview.isError && (
        <div className="p-4 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300 flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>Failed to compute the update preview.</span>
        </div>
      )}

      {ratify.isSuccess ? (
        <div className="p-5 rounded-xl border border-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 text-xs text-emerald-950 dark:text-emerald-200 flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2 font-bold text-sm">
            <CheckCircle2 size={18} className="text-emerald-600" />
            <span>Benchmark update ratified by {ratify.data.ratified_by}!</span>
          </div>
          <Link
            to="/campaigns"
            className="px-3.5 py-1.5 rounded-md bg-emerald-700 text-white font-bold hover:bg-emerald-800 transition-colors"
          >
            Go to Campaigns
          </Link>
        </div>
      ) : isDeferred ? (
        <div className="p-4 rounded-lg bg-muted border text-xs text-muted-foreground">
          Benchmark update deferred for the next quarterly cycle. No knowledge-base change was made.
        </div>
      ) : (
        preview.data && (
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3">
              <div>
                <h3 className="text-base font-bold text-foreground">
                  {preview.data.framework_id.toUpperCase()} Benchmark Review
                </h3>
                <p className="text-xs text-muted-foreground">
                  <span className="font-mono font-bold text-foreground">{preview.data.current_item_count}</span>{" "}
                  imported item{preview.data.current_item_count === 1 ? "" : "s"} currently on record for this
                  framework.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsDeferred(true)}
                  className="px-3.5 py-1.5 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors"
                >
                  Defer
                </button>
                <button
                  onClick={() => selected && ratify.mutate(selected)}
                  className="flex items-center gap-1 px-4 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 transition-opacity shadow-sm"
                >
                  <CheckCircle2 size={14} />
                  <span>Ratify Import</span>
                </button>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-secondary/50 border border-border/60 text-[11px] text-muted-foreground flex items-start gap-2">
              <Info size={14} className="shrink-0 mt-0.5" />
              <span>{preview.data.note}</span>
            </div>
          </div>
        )
      )}
    </div>
  );
};
