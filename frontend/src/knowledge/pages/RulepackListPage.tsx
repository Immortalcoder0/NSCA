import React, { useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen, Search, Loader2, AlertTriangle } from "lucide-react";
import { TrustTierBadge } from "../../shared/components/TrustTierBadge";
import { useRulepacks, useRulepackCoverage, type RulepackSummary } from "../../shared/api/hooks";
import { toTrustTierType } from "../lib/trustTier";

const RulepackRow: React.FC<{ rp: RulepackSummary }> = ({ rp }) => {
  const coverage = useRulepackCoverage(rp.id);
  const { tier } = toTrustTierType(rp.trust_tier);

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4 hover:border-border/80 transition-colors">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-mono font-bold text-foreground text-base">{rp.id}</span>
            <TrustTierBadge tier={tier} size="sm" />
          </div>
          <p className="text-xs text-muted-foreground">
            Platform: <span className="font-mono text-foreground">{rp.platform}</span> · Version:{" "}
            <span className="font-mono font-bold text-foreground">{rp.version}</span>
          </p>
        </div>

        <Link
          to={`/knowledge/rulepacks/${rp.id}`}
          className="px-3 py-1.5 rounded-md bg-secondary text-foreground text-xs font-semibold hover:bg-secondary/80 transition-colors self-start sm:self-auto"
        >
          Inspect Grammar
        </Link>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2 border-t text-xs">
        <div>
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Control Coverage</span>
          <span className="font-mono font-bold text-foreground">
            {coverage.data ? `${(coverage.data.coverage_rate * 100).toFixed(1)}%` : coverage.isLoading ? "…" : "—"}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Controls Covered</span>
          <span className="font-mono font-bold text-foreground">
            {coverage.data ? `${coverage.data.controls_covered} / ${coverage.data.controls_total}` : "—"}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Trust Tier</span>
          <span className="text-foreground truncate block">{rp.trust_tier}</span>
        </div>
      </div>
    </div>
  );
};

export const RulepackListPage: React.FC = () => {
  const rulepacksQuery = useRulepacks();
  const [searchTerm, setSearchTerm] = useState("");

  const items = rulepacksQuery.data?.items ?? [];
  const filtered = items.filter(
    (r) => r.id.toLowerCase().includes(searchTerm.toLowerCase()) || r.platform.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-primary">
            <BookOpen size={22} />
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Knowledge Base · Rulepacks</h1>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Certified, community, and synthesized AST parsers, grammar extractors, and normalized facts.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/knowledge/frameworks"
            className="flex items-center gap-1.5 px-3 py-2 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors"
          >
            <span>Framework Catalogs</span>
          </Link>
          <Link
            to="/knowledge/update-review"
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 transition-opacity"
          >
            <span>Review Framework Updates</span>
          </Link>
        </div>
      </div>

      {/* Search Filter */}
      <div className="relative w-full sm:w-80">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Filter rulepacks by vendor or OS..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-9 pr-4 py-2 text-xs rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>

      {rulepacksQuery.isLoading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-6 justify-center">
          <Loader2 size={16} className="animate-spin" />
          <span>Loading rulepacks…</span>
        </div>
      )}

      {rulepacksQuery.isError && (
        <div className="p-4 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300 flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>Failed to load rulepacks.</span>
        </div>
      )}

      {/* Rulepacks List */}
      <div className="grid grid-cols-1 gap-4">
        {filtered.map((rp) => (
          <RulepackRow key={rp.id} rp={rp} />
        ))}
      </div>
    </div>
  );
};
