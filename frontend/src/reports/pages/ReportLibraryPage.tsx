import React, { useState } from "react";
import { Link } from "react-router-dom";
import { FileText, Search, ArrowRight, Lock, Loader2, AlertTriangle, Plus } from "lucide-react";
import { ExportFormatDropdown } from "../components/ExportFormatDropdown";
import {
  useReportsList,
  useReportDocument,
  useGenerateReport,
  useCampaigns,
  type ReportListItem,
} from "../../shared/api/hooks";

interface ReportLibraryCardProps {
  rep: ReportListItem;
}

const ReportLibraryCard: React.FC<ReportLibraryCardProps> = ({ rep }) => {
  // Best-effort: the compliance/coverage figures come from the full JSON
  // document (there is no lightweight "scores only" endpoint) — fetched
  // per card since the list endpoint itself only returns meta fields.
  const doc = useReportDocument(rep.id);
  const scores = doc.data?.scores;

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4 hover:border-border/80 transition-colors">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-mono font-bold text-xs text-muted-foreground">{rep.id}</span>
            <span className="px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 font-mono text-[10px] font-bold text-emerald-800 dark:text-emerald-300 flex items-center gap-1 border border-emerald-300 dark:border-emerald-800">
              <Lock size={10} />
              {doc.data?.mode?.toUpperCase() ?? "SEALED"}
            </span>
          </div>
          <h2 className="text-base font-bold text-foreground">
            <Link to={`/reports/${rep.id}`} className="hover:underline">
              {rep.device ? `${rep.device} compliance report` : rep.id}
            </Link>
          </h2>
          <p className="text-xs text-muted-foreground">
            Campaign: <span className="font-mono text-foreground font-bold">{rep.campaign_id ?? "—"}</span> · Generated:{" "}
            <span className="text-foreground">{new Date(rep.generated_at).toLocaleString()}</span>
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <ExportFormatDropdown reportId={rep.id} availableFormats={rep.formats_available} />
          <Link
            to={`/reports/${rep.id}`}
            className="flex items-center gap-1 px-3.5 py-1.5 rounded-md bg-secondary text-foreground text-xs font-semibold hover:bg-secondary/80 transition-colors"
          >
            <span>Open Report Viewer</span>
            <ArrowRight size={13} />
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t text-xs">
        <div>
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Compliance</span>
          <span className="font-mono font-bold text-foreground">
            {scores && scores.compliance.denominator > 0
              ? `${Math.round((scores.compliance.numerator / scores.compliance.denominator) * 100)}%`
              : "—"}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Coverage</span>
          <span className="font-mono font-bold text-foreground">
            {scores && scores.coverage.denominator > 0
              ? `${Math.round((scores.coverage.numerator / scores.coverage.denominator) * 100)}%`
              : "—"}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Formats</span>
          <span className="font-mono font-bold text-foreground">{rep.formats_available.join(", ") || "—"}</span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">SHA256 Digest</span>
          <span className="font-mono text-[10px] text-muted-foreground truncate block">{rep.hash ?? "—"}</span>
        </div>
      </div>
    </div>
  );
};

export const ReportLibraryPage: React.FC = () => {
  const reportsQuery = useReportsList();
  const [searchTerm, setSearchTerm] = useState("");
  const [showGenerate, setShowGenerate] = useState(false);

  const items = reportsQuery.data?.items ?? [];
  const filtered = items.filter(
    (r) =>
      r.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.device ?? "").toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.campaign_id ?? "").toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-primary">
            <FileText size={22} />
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Compliance Reports Library</h1>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Sealed audit reports, multi-format artifacts (PDF, DOCX, OSCAL, JSON), and cryptographic verification records.
          </p>
        </div>
        <button
          onClick={() => setShowGenerate((v) => !v)}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 transition-opacity shrink-0"
        >
          <Plus size={14} />
          <span>Generate Report</span>
        </button>
      </div>

      {showGenerate && <GenerateReportPanel onGenerated={() => reportsQuery.refetch()} />}

      {/* Search Bar */}
      <div className="relative w-full sm:w-80">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Filter by id, device, or campaign..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-9 pr-4 py-2 text-xs rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>

      {reportsQuery.isLoading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-6 justify-center">
          <Loader2 size={16} className="animate-spin" />
          <span>Loading reports…</span>
        </div>
      )}

      {reportsQuery.isError && (
        <div className="p-4 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300 flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>Failed to load the reports list.</span>
        </div>
      )}

      {/* Report Cards Feed */}
      <div className="space-y-4">
        {!reportsQuery.isLoading && filtered.length === 0 && (
          <div className="p-6 rounded-xl border border-border/80 bg-card text-xs text-muted-foreground text-center">
            No reports yet. Generate one above.
          </div>
        )}
        {filtered.map((rep) => (
          <ReportLibraryCard key={rep.id} rep={rep} />
        ))}
      </div>
    </div>
  );
};

const GenerateReportPanel: React.FC<{ onGenerated: () => void }> = ({ onGenerated }) => {
  const campaignsQuery = useCampaigns();
  const generateReport = useGenerateReport();
  const [campaignId, setCampaignId] = useState("");
  const [device, setDevice] = useState("");
  const [mode, setMode] = useState<"draft" | "issued">("issued");

  const campaigns = (campaignsQuery.data?.items as Array<Record<string, unknown>> | undefined) ?? [];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!campaignId || !device) return;
    generateReport.mutate(
      { campaignId, device, mode },
      { onSuccess: () => onGenerated() }
    );
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3 text-xs"
    >
      <span className="font-bold text-sm text-foreground block">
        Generate a real per-device report (POST /campaigns/&lt;id&gt;/reports/generate)
      </span>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <label className="space-y-1">
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Campaign</span>
          <select
            value={campaignId}
            onChange={(e) => setCampaignId(e.target.value)}
            className="w-full px-2.5 py-1.5 rounded-md border border-input bg-background font-mono text-xs"
          >
            <option value="">Select…</option>
            {campaigns.map((c) => (
              <option key={String(c.id)} value={String(c.id)}>
                {String(c.id)} — {String(c.name)}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Device hostname</span>
          <input
            value={device}
            onChange={(e) => setDevice(e.target.value)}
            placeholder="e.g. CORE-SW-01"
            className="w-full px-2.5 py-1.5 rounded-md border border-input bg-background font-mono text-xs"
          />
        </label>
        <label className="space-y-1">
          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Mode</span>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as "draft" | "issued")}
            className="w-full px-2.5 py-1.5 rounded-md border border-input bg-background font-mono text-xs"
          >
            <option value="issued">issued</option>
            <option value="draft">draft</option>
          </select>
        </label>
      </div>
      <button
        type="submit"
        disabled={!campaignId || !device || generateReport.isPending}
        className="flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 disabled:opacity-50 transition-opacity"
      >
        {generateReport.isPending && <Loader2 size={14} className="animate-spin" />}
        <span>Generate</span>
      </button>
      {generateReport.isError && (
        <p className="text-red-600 dark:text-red-400">
          {generateReport.error instanceof Error ? generateReport.error.message : "Generation failed."}
        </p>
      )}
      {generateReport.isSuccess && (
        <p className="text-emerald-600 dark:text-emerald-400 font-mono">
          Generated {generateReport.data.report_id}
        </p>
      )}
    </form>
  );
};
