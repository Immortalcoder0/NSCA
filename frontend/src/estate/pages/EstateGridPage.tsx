import React, { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Server, ArrowRight, ShieldAlert, AlertTriangle, Sparkles, XCircle, ArrowDownWideNarrow } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "../../shared/components/DataTable";
import { EstateStatStrip } from "../components/EstateStatStrip";
import { AttackPathBanner } from "../components/AttackPathBanner";
// Track 2's real SystemicFindingBanner (findings/components/), swapped in
// per plans/frontend-01-ingestion-campaigns-estate.md §3 M4 — replaces this
// track's own placeholder, which has been deleted.
import { SystemicFindingBanner } from "../../findings/components/SystemicFindingBanner";
import { TrustTierBadge } from "../../shared/components/TrustTierBadge";
import type { EstateDeviceItem } from "../types";
import { cn } from "../../shared/lib/utils";
import {
  useEstateDevices,
  DEFAULT_ESTATE_SORT,
  type EstateSortKey,
} from "../hooks/useEstateDevices";
import { useCampaignAttackPaths, useCampaignSystemic } from "../../shared/api/hooks";

const SORT_OPTIONS: Array<{ value: EstateSortKey; label: string }> = [
  { value: "critical_weighted_exposure", label: "Critical findings (exposure-weighted) — default" },
  { value: "compliance_asc", label: "Compliance (lowest first)" },
  { value: "coverage_asc", label: "Coverage (lowest first)" },
  { value: "hostname", label: "Hostname (A–Z)" },
];

export const EstateGridPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const campaignParam = searchParams.get("campaign") || "CMP-2026Q3-001";
  const platformFilter = searchParams.get("platform") || "all";
  const exposureFilter = searchParams.get("exposure") || "all";
  // Sort lives in the URL (not just component state) so a refresh or a
  // shared link preserves it -- the spec explicitly calls out that this
  // must not be "a client-side reorder that resets on refresh."
  const sort = (searchParams.get("sort") as EstateSortKey | null) || DEFAULT_ESTATE_SORT;

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value === "all") next.delete(key);
    else next.set(key, value);
    setSearchParams(next, { replace: true });
  };

  const { data, isLoading } = useEstateDevices({
    campaignId: campaignParam,
    sort,
    platform: platformFilter,
    exposure: exposureFilter,
  });

  // Real (but still M0/M1-stub) network calls — see useAttackPaths.ts's
  // docstrings: both endpoints exist and are hit for real, but the live
  // platform returns the same fixed example regardless of campaign until a
  // later milestone wires the real engine output through.
  const attackPathsQuery = useCampaignAttackPaths(campaignParam);
  const systemicQuery = useCampaignSystemic(campaignParam);

  const devices: EstateDeviceItem[] = data?.devices ?? [];
  const isFixtureFallback = Boolean(data?.isFixture);

  const attackPaths = (attackPathsQuery.data as { attack_paths?: Array<Record<string, unknown>> } | undefined)
    ?.attack_paths;
  const attackPathCount = attackPaths?.length;
  const attackPathCriticalFindings = attackPaths
    ? new Set(attackPaths.flatMap((p) => (p.findings as string[] | undefined) ?? [])).size
    : undefined;

  const systemicFindings = (systemicQuery.data as { systemic_findings?: Array<Record<string, unknown>> } | undefined)
    ?.systemic_findings;
  const primarySystemic = systemicFindings?.[0];

  const filteredDevices = useMemo(() => {
    // Filters are also sent to the query above; this client-side pass
    // only covers the offline-fixture fallback path so filtering still
    // behaves correctly without a reachable backend.
    return devices.filter((d) => {
      const matchPlatform =
        platformFilter === "all" ||
        d.platform.toLowerCase().includes(platformFilter.toLowerCase());
      const matchExposure = exposureFilter === "all" || d.exposure === exposureFilter;
      return matchPlatform && matchExposure;
    });
  }, [devices, platformFilter, exposureFilter]);

  const columns: ColumnDef<EstateDeviceItem>[] = [
    {
      accessorKey: "hostname",
      header: "Device Hostname",
      cell: ({ row }) => {
        const item = row.original;
        return (
          <div className="space-y-0.5">
            <Link
              to={`/estate/${item.id}`}
              className="font-mono font-bold text-primary hover:underline flex items-center gap-1.5"
            >
              <Server size={13} className="text-muted-foreground" />
              <span>{item.hostname}</span>
            </Link>
            <div className="text-[11px] text-muted-foreground font-mono">
              SN: {item.serial || "Uncollected"} · {item.role}
            </div>
          </div>
        );
      },
    },
    {
      accessorKey: "platform",
      header: "Platform / Rulepack",
      cell: ({ row }) => {
        const item = row.original;
        return (
          <div className="space-y-1">
            <div className="font-mono text-foreground font-medium">{item.platform}</div>
            <TrustTierBadge tier={item.rulepack_trust_tier} size="sm" />
          </div>
        );
      },
    },
    {
      accessorKey: "coverage_score",
      header: "Coverage (1st-Class)",
      cell: ({ row }) => {
        const score = row.original.coverage_score;
        if (score === 0) {
          return <span className="font-mono text-muted-foreground font-bold">0%</span>;
        }
        return (
          <div className="space-y-1 min-w-[90px]">
            <div className="flex items-center justify-between font-mono font-bold">
              <span>{Math.round(score * 100)}%</span>
            </div>
            <div className="w-full h-1.5 bg-secondary rounded-full overflow-hidden">
              <div
                style={{ width: `${score * 100}%` }}
                className={cn(
                  "h-full rounded-full",
                  score > 0.85 ? "bg-sky-500" : score > 0.6 ? "bg-amber-500" : "bg-red-500"
                )}
              />
            </div>
          </div>
        );
      },
    },
    {
      accessorKey: "compliance_score",
      header: "Compliance",
      cell: ({ row }) => {
        const score = row.original.compliance_score;
        if (row.original.coverage_score === 0) {
          return <span className="text-muted-foreground font-mono">—</span>;
        }
        return (
          <div className="space-y-1 min-w-[90px]">
            <div className="flex items-center justify-between font-mono font-bold">
              <span>{Math.round(score * 100)}%</span>
            </div>
            <div className="w-full h-1.5 bg-secondary rounded-full overflow-hidden">
              <div
                style={{ width: `${score * 100}%` }}
                className={cn(
                  "h-full rounded-full",
                  score > 0.75 ? "bg-emerald-500" : "bg-red-500"
                )}
              />
            </div>
          </div>
        );
      },
    },
    {
      accessorKey: "critical_findings_count",
      header: "Critical",
      cell: ({ row }) => {
        const crit = row.original.critical_findings_count;
        if (row.original.coverage_score === 0) {
          return <span className="text-muted-foreground font-mono">—</span>;
        }
        return (
          <span
            className={cn(
              "font-mono font-black px-2 py-0.5 rounded text-xs",
              crit > 0
                ? "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200 border border-red-300 dark:border-red-800"
                : "text-muted-foreground"
            )}
          >
            {crit}
          </span>
        );
      },
    },
    {
      accessorKey: "status_annotations",
      header: "Status Annotations",
      cell: ({ row }) => {
        const ann = row.original.status_annotations;
        return (
          <div className="flex flex-wrap gap-1">
            {ann.includes("external") && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 font-semibold text-[10px]">
                <ShieldAlert size={11} />
                ▲ External
              </span>
            )}
            {ann.includes("terse") && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 font-semibold text-[10px]">
                <AlertTriangle size={11} />
                ⚠ Terse
              </span>
            )}
            {ann.includes("local_rulepack") && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300 font-semibold text-[10px]">
                <Sparkles size={11} />
                ⓘ Local RP
              </span>
            )}
            {ann.includes("missing") && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-zinc-200 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 font-semibold text-[10px]">
                <XCircle size={11} />
                ✗ Missing
              </span>
            )}
          </div>
        );
      },
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <Link
          to={`/estate/${row.original.id}`}
          className="flex items-center gap-1 px-2.5 py-1 rounded bg-secondary text-foreground text-xs font-semibold hover:bg-secondary/80 transition-colors"
        >
          <span>Detail</span>
          <ArrowRight size={12} />
        </Link>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Estate Device Topology</h1>
            <span className="text-xs font-mono font-bold bg-primary/10 text-primary px-2 py-0.5 rounded">
              {campaignParam}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Exposure-ranked compliance and coverage auditing across {devices.length} collected assets.
          </p>
        </div>
      </div>

      {isFixtureFallback && (
        <div className="p-3 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50/70 dark:bg-amber-950/30 text-[11px] text-amber-900 dark:text-amber-200">
          <span className="font-mono">GET /campaigns/{"{id}"}/findings?group_by=device</span> was unreachable or
          returned an unexpected shape for <span className="font-mono">{campaignParam}</span>. The table below shows
          realistic, clearly-labelled fixture data as a documented fallback so this screen stays demoable; it is not
          live data.
        </div>
      )}

      {/* Top Stat Strip — averaged from the rendered device rows, real for a
          reachable current server, fixture numbers on the documented
          fallback path (see isFixtureFallback above). */}
      <EstateStatStrip
        compliance={devices.length ? devices.reduce((s, d) => s + d.compliance_score, 0) / devices.length : 0}
        coverage={devices.length ? devices.reduce((s, d) => s + d.coverage_score, 0) / devices.length : 0}
        meaningfulRatio={
          devices.length
            ? devices.reduce((s, d) => s + (d.meaningful_ratio ?? 0), 0) / devices.length
            : 0
        }
        security={
          devices.length ? devices.reduce((s, d) => s + (d.security_score ?? 0), 0) / devices.length : 0
        }
        deviceCount={devices.length}
        totalDeviceCount={devices.length}
      />

      {/* Attack Path and Systemic Defect Banners — real network calls;
          the live platform still returns a fixed M0-stub example for both
          (see useAttackPaths.ts's docstrings), so these render honestly
          only once data comes back, rather than fabricated defaults. */}
      <div className="space-y-3">
        {attackPathCount !== undefined && (
          <AttackPathBanner pathCount={attackPathCount} criticalFindingCount={attackPathCriticalFindings ?? 0} />
        )}
        {primarySystemic && (
          <SystemicFindingBanner
            systemicId={String(primarySystemic.id ?? "")}
            affectedCount={Number(primarySystemic.affected_devices ?? 0)}
            totalGroupCount={Number(primarySystemic.affected_devices ?? 0)}
            groupName={String(primarySystemic.control ?? "affected devices")}
            defectSummary={String(primarySystemic.pattern ?? "")}
          />
        )}
      </div>

      {/* Filters Toolbar */}
      <div className="flex flex-wrap items-center gap-3 p-3 rounded-lg border border-border bg-card text-xs">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground font-semibold">Platform:</span>
          <select
            value={platformFilter}
            onChange={(e) => setParam("platform", e.target.value)}
            className="px-2 py-1 rounded border border-input bg-background"
          >
            <option value="all">All Platforms</option>
            <option value="ios">Cisco IOS / IOS-XE</option>
            <option value="pan-os">Palo Alto PAN-OS</option>
            <option value="routeros">MikroTik RouterOS</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-muted-foreground font-semibold">Exposure Tier:</span>
          <select
            value={exposureFilter}
            onChange={(e) => setParam("exposure", e.target.value)}
            className="px-2 py-1 rounded border border-input bg-background"
          >
            <option value="all">All Exposure Zones</option>
            <option value="internet_facing">Internet-Facing (Perimeter)</option>
            <option value="internal">Internal / Core</option>
            <option value="isolated">Isolated OOB</option>
          </select>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <label htmlFor="estate-sort" className="text-muted-foreground font-semibold flex items-center gap-1">
            <ArrowDownWideNarrow size={13} />
            <span>Sort by:</span>
          </label>
          <select
            id="estate-sort"
            value={sort}
            onChange={(e) => setParam("sort", e.target.value)}
            className="px-2 py-1 rounded border border-input bg-background font-medium"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Estate Table */}
      <DataTable
        data={filteredDevices}
        columns={columns}
        searchPlaceholder="Filter estate devices by hostname, serial, or platform..."
      />
      {isLoading && (
        <p className="text-xs text-muted-foreground italic">Loading estate devices…</p>
      )}
    </div>
  );
};
