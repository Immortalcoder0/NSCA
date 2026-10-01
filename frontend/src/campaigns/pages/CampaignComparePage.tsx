import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, GitCompare, Download, Loader2 } from "lucide-react";
import { CampaignDeltaView } from "../components/CampaignDeltaView";
import type { CampaignComparisonData, DeltaDecompositionItem } from "../types";
import { useCampaigns, useCompareCampaigns } from "../../shared/api/hooks";

export const CampaignComparePage: React.FC = () => {
  const { data: campaignsData, isLoading: campaignsLoading } = useCampaigns();
  const campaignItems = useMemo(
    () => (campaignsData?.items as Array<Record<string, unknown>> | undefined) ?? [],
    [campaignsData]
  );

  const [fromId, setFromId] = useState<string>("");
  const [toId, setToId] = useState<string>("");

  // Default the two pickers to the two most recent real campaigns once
  // they load, so the compare view isn't stuck empty on first render.
  const effectiveFromId = fromId || (campaignItems[1]?.id as string) || (campaignItems[0]?.id as string) || "";
  const effectiveToId = toId || (campaignItems[0]?.id as string) || "";

  const { data: compareData, isLoading: compareLoading, isError, error } = useCompareCampaigns(
    effectiveFromId,
    effectiveToId
  );

  // `GET /campaigns/{id}/compare/{other}` is a real network call, but the
  // live M1 backend keeps it as a literal stub (see
  // `nsca_platform/api/campaigns.py::compare_campaigns` — comparison needs
  // the finding lifecycle + knowledge-base diffing machinery, out of M1
  // scope) that always returns the same fixed delta-decomposition example
  // regardless of which two campaign ids are passed. Flagged here rather
  // than silently presented as campaign-specific.
  const data: CampaignComparisonData | undefined = compareData
    ? {
        from: String((compareData as Record<string, unknown>).from ?? effectiveFromId),
        to: String((compareData as Record<string, unknown>).to ?? effectiveToId),
        compliance: (compareData as Record<string, unknown>).compliance as CampaignComparisonData["compliance"],
        decomposition: (compareData as Record<string, unknown>).decomposition as DeltaDecompositionItem[],
      }
    : undefined;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link to="/campaigns" className="hover:text-foreground flex items-center gap-1">
            <ArrowLeft size={13} />
            <span>All Campaigns</span>
          </Link>
          <span>/</span>
          <span className="font-semibold text-foreground">Compare Campaigns</span>
        </div>

        <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors">
          <Download size={13} />
          <span>Export Delta Decomposition (PDF/JSON)</span>
        </button>
      </div>

      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-primary">
          <GitCompare size={20} />
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Audit Campaign Delta Comparison</h1>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Rigorous delta decomposition isolating true security remediation from framework revisions and scope adjustments.
        </p>
      </div>

      {/* Campaign pickers */}
      <div className="flex flex-wrap items-center gap-3 p-4 rounded-xl border border-border bg-card text-xs">
        <div className="flex items-center gap-2">
          <label htmlFor="from-campaign" className="font-semibold text-foreground">
            From:
          </label>
          <select
            id="from-campaign"
            value={effectiveFromId}
            onChange={(e) => setFromId(e.target.value)}
            className="px-2 py-1.5 rounded border border-input bg-background font-mono"
          >
            {campaignItems.map((c) => (
              <option key={String(c.id)} value={String(c.id)}>
                {String(c.id)} — {String(c.name)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="to-campaign" className="font-semibold text-foreground">
            To:
          </label>
          <select
            id="to-campaign"
            value={effectiveToId}
            onChange={(e) => setToId(e.target.value)}
            className="px-2 py-1.5 rounded border border-input bg-background font-mono"
          >
            {campaignItems.map((c) => (
              <option key={String(c.id)} value={String(c.id)}>
                {String(c.id)} — {String(c.name)}
              </option>
            ))}
          </select>
        </div>
        {campaignsLoading && (
          <span className="text-muted-foreground flex items-center gap-1">
            <Loader2 size={12} className="animate-spin" /> Loading campaigns…
          </span>
        )}
      </div>

      <p className="text-[11px] text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2">
        Note: <span className="font-mono">GET /campaigns/{"{id}"}/compare/{"{other}"}</span> is still an M0/M1 stub
        on the live platform API — it returns the same fixed example decomposition regardless of which two
        campaigns are selected above (real per-cause diffing is out of M1 scope). The call below is real, the
        numbers are not yet campaign-specific.
      </p>

      {/* Comparison View */}
      {compareLoading && (
        <div className="p-8 flex items-center justify-center gap-2 text-xs text-muted-foreground border rounded-xl bg-card">
          <Loader2 size={14} className="animate-spin" />
          <span>Loading comparison…</span>
        </div>
      )}
      {isError && (
        <div className="p-4 text-xs text-red-700 dark:text-red-300 border border-red-300 dark:border-red-800 rounded-xl bg-red-50/60 dark:bg-red-950/30">
          Failed to load comparison{error instanceof Error ? `: ${error.message}` : "."}
        </div>
      )}
      {data && <CampaignDeltaView data={data} />}
      {!compareLoading && !isError && !data && (
        <div className="p-8 text-center text-xs text-muted-foreground border rounded-xl bg-card">
          Select two campaigns above to compare (at least one real campaign must exist).
        </div>
      )}
    </div>
  );
};
