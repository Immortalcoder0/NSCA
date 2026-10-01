import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Plus,
  Search,
  ArrowRight,
  GitCompare,
  UploadCloud,
  Server,
  Lock,
  Loader2,
} from "lucide-react";
import { CampaignStatusBadge } from "../components/CampaignStatusBadge";
import { CampaignCreateModal } from "../components/CampaignCreateModal";
import type { CampaignModel, CampaignFramework } from "../types";
import { useCampaigns, useCreateCampaign } from "../../shared/api/hooks";

/** Real `GET /campaigns` returns `{items: [...], next_cursor}`, where each
 * item is `nsca_platform/services/campaign.py::_row_to_response`'s shape:
 * `{id, name, status, scope, frameworks, owner, window, knowledge_pin}`.
 * That's a 1:1 match for `CampaignModel` minus `device_count` /
 * `compliance_score` / `coverage_score` — the real backend doesn't compute
 * or return per-campaign rollup scores on the list endpoint (those live on
 * per-device `assessment` rows, not the campaign row itself), so those
 * three fields are left `undefined` here rather than fabricated. */
function toCampaignModel(raw: Record<string, unknown>): CampaignModel {
  return {
    id: String(raw.id ?? ""),
    name: String(raw.name ?? ""),
    status: (raw.status as CampaignModel["status"]) ?? "Draft",
    scope: (raw.scope as CampaignModel["scope"]) ?? { type: "filter", expression: "" },
    frameworks: (raw.frameworks as CampaignFramework[]) ?? [],
    owner: String(raw.owner ?? ""),
    window: (raw.window as CampaignModel["window"]) ?? { start: "", end: "" },
    knowledge_pin: raw.knowledge_pin as CampaignModel["knowledge_pin"],
  };
}

export const CampaignListPage: React.FC = () => {
  const { data, isLoading, isError, error } = useCampaigns();
  const createCampaign = useCreateCampaign();
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const campaigns: CampaignModel[] = useMemo(() => {
    const items = (data?.items as Record<string, unknown>[] | undefined) ?? [];
    return items.map(toCampaignModel);
  }, [data]);

  const filteredCampaigns = campaigns.filter((c) => {
    const matchesSearch =
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.owner.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "active" && (c.status === "Draft" || c.status === "Collecting" || c.status === "Assessing" || c.status === "Review")) ||
      c.status.toLowerCase() === statusFilter.toLowerCase();

    return matchesSearch && matchesStatus;
  });

  const handleCreate = (data: {
    name: string;
    scope: { type: string; expression: string };
    frameworks: CampaignFramework[];
    owner: string;
    window: { start: string; end: string };
  }) => {
    // `useCreateCampaign`'s `CreateCampaignRequest.frameworks` is typed
    // `string[]` (shared/api/hooks/useCampaigns.ts, frozen for this
    // track), but the real body the platform actually accepts is a list of
    // framework descriptor objects (`nsca_platform/services/campaign.py
    // ::create_campaign` stores `body.get("frameworks", [])` verbatim, and
    // `CampaignCreateModal` already builds the richer object shape) — the
    // shared type is just too narrow here, not a real API constraint, so
    // this is cast through rather than flattened to strings that would
    // lose the real framework/version data.
    createCampaign.mutate({ ...data, frameworks: data.frameworks as unknown as string[] });
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Audit Campaigns</h1>
          <p className="text-xs text-muted-foreground mt-1">
            Manage assessment scopes, framework mappings, and audit lifecycles.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/campaigns/compare"
            className="flex items-center gap-1.5 px-3 py-2 rounded-md border border-border text-xs font-medium hover:bg-secondary transition-colors"
          >
            <GitCompare size={14} />
            <span>Compare Campaigns</span>
          </Link>
          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 transition-opacity"
          >
            <Plus size={15} />
            <span>New Campaign</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-b pb-4">
        <div className="flex items-center gap-1 bg-secondary/60 p-1 rounded-lg border text-xs w-full sm:w-auto">
          {["all", "active", "issued", "closed"].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded capitalize font-medium transition-colors ${
                statusFilter === st
                  ? "bg-background text-foreground shadow-sm font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-72">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search campaigns..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 text-xs rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>

      {/* Campaign Cards Grid */}
      <div className="grid grid-cols-1 gap-4">
        {filteredCampaigns.map((camp) => (
          <div
            key={camp.id}
            className="p-5 rounded-xl border border-border bg-card text-card-foreground hover:border-border/90 transition-colors shadow-sm space-y-4"
          >
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-muted-foreground font-bold">{camp.id}</span>
                  <CampaignStatusBadge status={camp.status} />
                  {camp.status === "Issued" && (
                    <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                      <Lock size={11} />
                      Immutable
                    </span>
                  )}
                </div>
                <h2 className="text-base font-bold tracking-tight">
                  <Link to={`/campaigns/${camp.id}`} className="hover:underline text-foreground">
                    {camp.name}
                  </Link>
                </h2>
              </div>

              <div className="flex items-center gap-2">
                <Link
                  to={`/campaigns/${camp.id}/ingest`}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded border border-border text-xs font-medium hover:bg-secondary transition-colors"
                >
                  <UploadCloud size={13} className="text-primary" />
                  <span>Ingest</span>
                </Link>
                <Link
                  to={`/estate?campaign=${camp.id}`}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded border border-border text-xs font-medium hover:bg-secondary transition-colors"
                >
                  <Server size={13} className="text-primary" />
                  <span>Estate</span>
                </Link>
                <Link
                  to={`/campaigns/${camp.id}`}
                  className="flex items-center gap-1 px-3 py-1.5 rounded bg-secondary text-foreground text-xs font-semibold hover:bg-secondary/80 transition-colors"
                >
                  <span>Details</span>
                  <ArrowRight size={13} />
                </Link>
              </div>
            </div>

            {/* Scope and Framework Meta */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t text-xs">
              <div>
                <span className="text-muted-foreground text-[11px] block">Target Scope:</span>
                <span className="font-mono text-foreground font-medium truncate block">
                  {camp.scope.expression}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {camp.status === "Draft"
                    ? "Scope not yet resolved"
                    : "See Details for resolved device count"}
                </span>
              </div>

              <div>
                <span className="text-muted-foreground text-[11px] block">Frameworks:</span>
                <div className="flex flex-wrap gap-1 mt-0.5">
                  {camp.frameworks.map((f, i) => (
                    <span
                      key={i}
                      className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono text-[10px] uppercase font-bold"
                    >
                      {f.framework} {f.version || f.revision || f.release}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <span className="text-muted-foreground text-[11px] block">Window & Owner:</span>
                <div className="text-foreground">
                  {camp.window.start} → {camp.window.end}
                </div>
                <div className="text-[11px] text-muted-foreground">Lead: {camp.owner}</div>
              </div>
            </div>

          </div>
        ))}

        {!isLoading && !isError && filteredCampaigns.length === 0 && (
          <div className="p-8 text-center text-xs text-muted-foreground border rounded-xl bg-card">
            {campaigns.length === 0
              ? "No campaigns yet — create one to get started, or seed the database via the platform API."
              : "No campaigns match the current search/filter."}
          </div>
        )}

        {isLoading && (
          <div className="p-8 flex items-center justify-center gap-2 text-xs text-muted-foreground border rounded-xl bg-card">
            <Loader2 size={14} className="animate-spin" />
            <span>Loading campaigns…</span>
          </div>
        )}

        {isError && (
          <div className="p-4 text-xs text-red-700 dark:text-red-300 border border-red-300 dark:border-red-800 rounded-xl bg-red-50/60 dark:bg-red-950/30">
            Failed to load campaigns from the platform API
            {error instanceof Error ? `: ${error.message}` : "."}
          </div>
        )}
      </div>

      <CampaignCreateModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreate}
      />
    </div>
  );
};
