import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, AlertTriangle } from "lucide-react";
import { AutomationCoverageManifest } from "../components/AutomationCoverageManifest";
import { useFrameworks, useFrameworkCoverage } from "../../shared/api/hooks";
import type { AutomationCoverageManifestData } from "../types";

export const FrameworkCatalogPage: React.FC = () => {
  const frameworksQuery = useFrameworks();
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (!selected && frameworksQuery.data?.items.length) {
      setSelected(frameworksQuery.data.items[0].framework);
    }
  }, [frameworksQuery.data, selected]);

  const coverageQuery = useFrameworkCoverage(selected ?? undefined);

  const manifest: AutomationCoverageManifestData | undefined = coverageQuery.data
    ? {
        framework_name: coverageQuery.data.benchmark
          ? `${coverageQuery.data.framework.toUpperCase()} ${coverageQuery.data.benchmark}`
          : coverageQuery.data.framework.toUpperCase(),
        version: coverageQuery.data.version,
        total_controls: coverageQuery.data.total_recommendations,
        automated_count: coverageQuery.data.automated,
        manual_only_count: coverageQuery.data.manual_only,
        data_unavailable_count: coverageQuery.data.data_unavailable,
        not_implemented_count: coverageQuery.data.not_implemented,
        manual_only_items: coverageQuery.data.manual_only_items.map((i) => ({
          control_id: i.id,
          reason: i.reason,
        })),
      }
    : undefined;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/knowledge" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Knowledge Base</span>
        </Link>
        <span>/</span>
        <span className="font-semibold text-foreground">Framework Catalogs & Manifests</span>
      </div>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Compliance Framework Catalogs
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Explore benchmark control families, automation manifests, and verifiable scope exclusions.
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

      {(frameworksQuery.isLoading || coverageQuery.isLoading) && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-6 justify-center">
          <Loader2 size={16} className="animate-spin" />
          <span>Loading manifest…</span>
        </div>
      )}

      {(frameworksQuery.isError || coverageQuery.isError) && (
        <div className="p-4 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300 flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>Failed to load the automation coverage manifest.</span>
        </div>
      )}

      {/* Manifest Display */}
      {manifest && <AutomationCoverageManifest manifest={manifest} />}
    </div>
  );
};
