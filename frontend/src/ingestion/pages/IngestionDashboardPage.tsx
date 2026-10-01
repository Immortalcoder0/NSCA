import React, { useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  UploadCloud,
  DownloadCloud,
  ArrowLeft,
  Server,
  Loader2,
} from "lucide-react";
import { AccessibleFileDropzone, type StagedFile } from "../components/AccessibleFileDropzone";
import { ProgressPanel } from "../../shared/components/ProgressPanel";
import { ArtifactOutcomeCard } from "../components/ArtifactOutcomeCard";
import { CollectionCompleteness } from "../components/CollectionCompleteness";
import { LiveCollectionModal } from "../components/LiveCollectionModal";
import type { IngestionArtifactItem, CollectionCompletenessData, ArtifactOutcomeState } from "../types";
import {
  useUploadArtifacts,
  useStartCollection,
  useCampaignCompleteness,
} from "../../shared/api/hooks";

/** Maps one real `results[]` entry from `POST /campaigns/{id}/artifacts`
 * (`nsca_platform/services/ingestion.py::_classify_and_persist`) into this
 * track's `IngestionArtifactItem`. The real shape genuinely varies by
 * `status` (see that function's docstring): `parsed` has no `caveat`, only
 * `parsed_with_caveat` has `caveat.controls_unassessable`, only
 * `platform_not_taught` has `training.*`, `unidentified` has no `platform`
 * at all. The real response also never includes `correlated_artifacts` —
 * multi-artifact-per-device correlation display (the UX mock's "3
 * artifacts · running-config · version · inventory" line) is not
 * implemented server-side yet (`api/ingestion.py`'s own docstring: a
 * multi-file archive upload today is treated as one opaque artifact per
 * file, not split/correlated), so that array is always empty for real
 * data — flagged, not fabricated. */
function toIngestionArtifactItem(raw: Record<string, unknown>): IngestionArtifactItem {
  const caveat = raw.caveat as Record<string, unknown> | undefined;
  const training = raw.training as Record<string, unknown> | undefined;
  return {
    id: String(raw.artifact_id ?? raw.filename ?? "unknown"),
    device: String(raw.device ?? raw.filename ?? "unidentified artifact"),
    platform: raw.platform ? String(raw.platform) : undefined,
    os_version: raw.os_version ? String(raw.os_version) : undefined,
    status: (raw.status as ArtifactOutcomeState) ?? "unidentified",
    export_mode: raw.export_mode as IngestionArtifactItem["export_mode"],
    correlated_artifacts: [],
    unassessable_controls_count: caveat?.controls_unassessable as number | undefined,
    training_questions_count: training?.questions_prepared as number | undefined,
    training_estimate_minutes: training?.estimated_minutes as number | undefined,
    grammar_coverage: raw.grammar_coverage as number | undefined,
    message: raw.message as string | undefined,
  };
}

/** Maps the real `GET /campaigns/{id}/completeness` response
 * (`nsca_platform/services/campaign.py::completeness`) — `{campaign_id,
 * in_scope_devices, collected, outcomes, not_yet_collected,
 * missing_devices: string[]}` — into this track's
 * `CollectionCompletenessData`. `percentage` isn't returned by the real
 * endpoint (computed client-side here); `missing_devices` is a bare
 * hostname list (no ip/role/owner — see ingestion/types.ts's note). */
function toCompletenessData(raw: Record<string, unknown>): CollectionCompletenessData {
  const totalInScope = Number(raw.in_scope_devices ?? 0);
  const collected = Number(raw.collected ?? 0);
  const missing = Number(raw.not_yet_collected ?? 0);
  const missingHostnames = (raw.missing_devices as string[] | undefined) ?? [];
  return {
    total_in_scope: totalInScope,
    collected,
    missing,
    percentage: totalInScope > 0 ? (collected / totalInScope) * 100 : 0,
    missing_devices: missingHostnames.map((name) => ({ name })),
  };
}

export const IngestionDashboardPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const campaignId = id || "";

  const uploadArtifacts = useUploadArtifacts(campaignId);
  const startCollection = useStartCollection(campaignId);
  const completenessQuery = useCampaignCompleteness(campaignId);

  const [isCollectingOpen, setIsCollectingOpen] = useState(false);
  const [lastResults, setLastResults] = useState<IngestionArtifactItem[]>([]);
  const [collectionMessage, setCollectionMessage] = useState<string | null>(null);

  const handleFilesSelected = (staged: StagedFile[]) => {
    const files = staged.map((s) => s.file).filter((f): f is File => Boolean(f));
    if (files.length === 0) return;
    uploadArtifacts.mutate(files, {
      onSuccess: (res) => {
        setLastResults(res.results.map((r) => toIngestionArtifactItem(r as Record<string, unknown>)));
      },
    });
  };

  const handleLiveCollection = (data: {
    targets: Array<{ host: string; credential_ref: string }>;
    artifacts: string[];
    mode: "read_only";
  }) => {
    startCollection.mutate(data, {
      onSuccess: (res) => {
        const jobId = (res as Record<string, unknown>).job_id;
        setCollectionMessage(
          `Dispatched real read-only collection request for ${data.targets.length} target(s) — job ${jobId}. ` +
            `Note: the live platform's /collect endpoint is still an M0 stub (no real collector/job queue yet), ` +
            `so it always reports "queued" and never actually reaches out to these hosts.`
        );
      },
    });
  };

  const artifacts = lastResults;

  const completenessData: CollectionCompletenessData | null = useMemo(() => {
    if (!completenessQuery.data) return null;
    return toCompletenessData(completenessQuery.data as Record<string, unknown>);
  }, [completenessQuery.data]);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb & Top Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link to="/campaigns" className="hover:text-foreground flex items-center gap-1">
            <ArrowLeft size={13} />
            <span>Campaigns</span>
          </Link>
          <span>/</span>
          <Link to={`/campaigns/${campaignId}`} className="hover:text-foreground font-mono">
            {campaignId || "(no campaign selected)"}
          </Link>
          <span>/</span>
          <span className="font-semibold text-foreground">Ingestion Dashboard</span>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to={`/estate?campaign=${campaignId}`}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors"
          >
            <Server size={13} className="text-primary" />
            <span>View Estate Grid</span>
          </Link>
        </div>
      </div>

      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-primary">
          <UploadCloud size={22} />
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Configuration Ingestion Dashboard</h1>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Upload single/bulk configuration archives or trigger live read-only device collection across the target estate.
        </p>
      </div>

      {/* Upload Zone & Actions */}
      <div className="p-6 rounded-xl border border-border bg-card space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold text-foreground">Artifact Ingestion</h2>
            <p className="text-xs text-muted-foreground">
              Drop single/bulk text configs, XML, JSON, or zipped show-tech support archives.
            </p>
          </div>

          <button
            onClick={() => setIsCollectingOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-secondary border border-border text-xs font-bold hover:bg-secondary/80 text-foreground transition-colors shadow-sm"
          >
            <DownloadCloud size={15} className="text-primary" />
            <span>Collect from Devices (Read-Only)</span>
          </button>
        </div>

        <AccessibleFileDropzone onFilesSelected={handleFilesSelected} />

        {uploadArtifacts.isError && (
          <p className="text-xs text-red-700 dark:text-red-300">
            Upload failed:{" "}
            {uploadArtifacts.error instanceof Error ? uploadArtifacts.error.message : "unknown error"}
          </p>
        )}
        {collectionMessage && (
          <p className="text-[11px] text-sky-700 dark:text-sky-300 bg-sky-50 dark:bg-sky-950/30 border border-sky-200 dark:border-sky-800 rounded px-3 py-2">
            {collectionMessage}
          </p>
        )}
      </div>

      {/* Processing Progress Panel (Principle U5) */}
      {(uploadArtifacts.isPending || lastResults.length > 0) && (
        <ProgressPanel
          title={
            uploadArtifacts.isPending
              ? "Uploading & classifying artifact batch…"
              : `Batch classification complete · ${lastResults.length} artifacts`
          }
          processedCount={uploadArtifacts.isPending ? 0 : lastResults.length}
          totalCount={lastResults.length || undefined}
          currentStepLabel={
            uploadArtifacts.isPending
              ? "Hashing, fingerprinting, and correlating against the live platform API"
              : "Batch classification complete"
          }
          status={uploadArtifacts.isPending ? "running" : "completed"}
          steps={[
            { id: "1", label: "Archive Extraction & Content-Addressed Hashing", status: "completed" },
            {
              id: "2",
              label: "Platform Fingerprinting & Grammar Resolution",
              status: "completed",
              detail: `${lastResults.length} artifact(s) classified`,
            },
            {
              id: "3",
              label: "Multi-Artifact Device Correlation",
              status: "completed",
              detail: "Real hostname correlation; multi-file archive splitting not yet implemented server-side",
            },
          ]}
        />
      )}

      {/* Four-State Classification Results List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-foreground">Classified Artifact Outcomes</h2>
            <p className="text-xs text-muted-foreground">
              Four non-binary outcome states with automated training studio invitations.
            </p>
          </div>
          <span className="text-xs font-mono text-muted-foreground font-semibold">
            {artifacts.length} Result{artifacts.length === 1 ? "" : "s"}
          </span>
        </div>

        {artifacts.length === 0 ? (
          <div className="p-8 text-center text-xs text-muted-foreground border rounded-xl bg-card">
            No artifacts uploaded yet this session. Drop files above to see real classification results from the
            live platform API.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {artifacts.map((art) => (
              <ArtifactOutcomeCard key={art.id} item={art} />
            ))}
          </div>
        )}
      </div>

      {/* Collection Completeness Block (FR-ING-016) */}
      {completenessQuery.isLoading && (
        <div className="p-6 flex items-center justify-center gap-2 text-xs text-muted-foreground border rounded-xl bg-card">
          <Loader2 size={14} className="animate-spin" />
          <span>Loading collection completeness…</span>
        </div>
      )}
      {completenessData && <CollectionCompleteness data={completenessData} />}

      {/* Live Collection Modal */}
      <LiveCollectionModal
        isOpen={isCollectingOpen}
        onClose={() => setIsCollectingOpen(false)}
        onStartCollection={handleLiveCollection}
      />
    </div>
  );
};
