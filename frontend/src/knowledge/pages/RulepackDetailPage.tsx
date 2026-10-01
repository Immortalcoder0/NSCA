import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, FileCode, Download, Loader2, AlertTriangle } from "lucide-react";
import { TrustTierBadge } from "../../shared/components/TrustTierBadge";
import { RulepackCoverageReport } from "../components/RulepackCoverageReport";
import { useRulepacks, useRulepackCoverage } from "../../shared/api/hooks";
import { downloadRulepackBundle } from "../../shared/api/hooks/useKnowledge";
import { toTrustTierType } from "../lib/trustTier";
import type { RulepackCoverageMetrics } from "../types";

export const RulepackDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const rulepacksQuery = useRulepacks();
  const coverageQuery = useRulepackCoverage(id);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const summary = rulepacksQuery.data?.items.find((r) => r.id === id);
  const { tier } = toTrustTierType(summary?.trust_tier);

  const metrics: RulepackCoverageMetrics = {
    controls_covered: coverageQuery.data?.controls_covered,
    controls_total: coverageQuery.data?.controls_total,
    coverage_rate: coverageQuery.data?.coverage_rate,
    trust_tier: summary?.trust_tier,
  };

  const handleExport = async () => {
    if (!id) return;
    setExportError(null);
    setIsExporting(true);
    try {
      const blob = await downloadRulepackBundle(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${id}.bundle.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/knowledge" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Rulepacks</span>
        </Link>
        <span>/</span>
        <span className="font-mono text-foreground font-bold">{id}</span>
      </div>

      {/* Main Header Block */}
      <div className="p-6 rounded-xl border border-border bg-card shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-foreground font-mono">{id}</span>
              <TrustTierBadge tier={tier} size="md" />
            </div>
            <p className="text-xs text-muted-foreground">
              Platform: <span className="font-mono text-foreground font-bold">{summary?.platform ?? "—"}</span> ·
              Version: <span className="font-mono text-foreground font-bold">{summary?.version ?? "—"}</span>
            </p>
          </div>

          <button
            onClick={handleExport}
            disabled={isExporting || !id}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors disabled:opacity-50"
          >
            {isExporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
            <span>Export Signed Bundle (.zip)</span>
          </button>
        </div>
        {exportError && (
          <p className="text-[11px] text-red-600 dark:text-red-400 flex items-center gap-1">
            <AlertTriangle size={12} />
            {exportError}
          </p>
        )}
      </div>

      {/* Coverage Metrics Strip */}
      {coverageQuery.isLoading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-6 justify-center">
          <Loader2 size={16} className="animate-spin" />
          <span>Loading coverage…</span>
        </div>
      ) : (
        <RulepackCoverageReport metrics={metrics} />
      )}

      {/* Extractors note */}
      <div className="p-6 rounded-xl border border-border bg-card shadow-sm space-y-3 text-xs">
        <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
          <FileCode size={16} className="text-primary" />
          <span>AST Extractors</span>
        </h3>
        <p className="text-muted-foreground">
          There is no API endpoint that lists individual extractors for a rulepack — the extractor definitions
          live inside the signed bundle itself. Use "Export Signed Bundle" above to download the real{" "}
          <code>{id}.yaml</code> and inspect its <code>extractors:</code> section directly.
        </p>
      </div>
    </div>
  );
};
