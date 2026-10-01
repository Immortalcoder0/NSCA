import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../client";

// See useCampaigns.ts's note on unstructured JSON dicts. A further,
// important honesty note specific to this file (flagged in the M6
// integration report, not silently hidden): `nsca_platform/api/knowledge.py`
// is only *partially* wired to real logic this milestone.
//   REAL (DB/filesystem backed): rulepack import/export(+download),
//   framework import, `GET /knowledge/frameworks/{id}/items`.
//   Still M0 STUBS (hardcoded literal responses, ignore the id/params
//   passed in): `GET /knowledge/rulepacks`, `.../coverage`, `GET
//   /knowledge/controls`, `GET /knowledge/frameworks`, `.../coverage`,
//   `POST .../preview`, `POST .../ratify` (records the real caller but
//   doesn't persist any state), `GET /knowledge/schema`, `GET
//   /knowledge/freshness`.
// Every hook below still calls the real HTTP route (replacing this track's
// former hardcoded frontend fixtures) — the caveat is about what the
// *backend* currently computes, not about whether the frontend is wired.

export const KNOWLEDGE_KEY = ["knowledge"] as const;

export interface RulepackSummary {
  id: string;
  version: string;
  trust_tier: string;
  platform: string;
}

export function useRulepacks() {
  return useQuery({
    queryKey: [...KNOWLEDGE_KEY, "rulepacks"],
    queryFn: () => apiClient.get<{ items: RulepackSummary[] }>("/knowledge/rulepacks"),
  });
}

export interface RulepackCoverage {
  rulepack_id: string;
  version: string;
  controls_covered: number;
  controls_total: number;
  coverage_rate: number;
}

export function useRulepackCoverage(rulepackId: string | undefined) {
  return useQuery({
    queryKey: [...KNOWLEDGE_KEY, "rulepacks", rulepackId, "coverage"],
    queryFn: () => apiClient.get<RulepackCoverage>(`/knowledge/rulepacks/${encodeURIComponent(rulepackId as string)}/coverage`),
    enabled: Boolean(rulepackId),
  });
}

export interface RulepackExportInfo {
  id: string;
  version: string;
  bundle_url: string;
  signature: string;
}

export function useExportRulepackInfo(rulepackId: string | undefined) {
  return useQuery({
    queryKey: [...KNOWLEDGE_KEY, "rulepacks", rulepackId, "export"],
    queryFn: () => apiClient.get<RulepackExportInfo>(`/knowledge/rulepacks/${encodeURIComponent(rulepackId as string)}/export`),
    enabled: Boolean(rulepackId),
  });
}

export interface ImportRulepackResult {
  id: string;
  version: string;
  status: string;
  signature_verified: boolean;
  trust_tier: string;
}

export function useImportRulepack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiClient.postForm<ImportRulepackResult>("/knowledge/rulepacks/import", form);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...KNOWLEDGE_KEY, "rulepacks"] }),
  });
}

export async function downloadRulepackBundle(rulepackId: string): Promise<Blob> {
  return apiClient.getBlob(`/knowledge/rulepacks/${encodeURIComponent(rulepackId)}/export/download`);
}

export interface ControlSummary {
  id: string;
  title: string;
}

export function useControls() {
  return useQuery({
    queryKey: [...KNOWLEDGE_KEY, "controls"],
    queryFn: () => apiClient.get<{ items: ControlSummary[] }>("/knowledge/controls"),
  });
}

export interface FrameworkSummary {
  framework: string;
  benchmark?: string;
  version?: string;
  catalog?: string;
  revision?: string;
  release?: string;
}

export function useFrameworks() {
  return useQuery({
    queryKey: [...KNOWLEDGE_KEY, "frameworks"],
    queryFn: () => apiClient.get<{ items: FrameworkSummary[] }>("/knowledge/frameworks"),
  });
}

export interface FrameworkCoverageManifest {
  framework: string;
  benchmark?: string;
  version: string;
  total_recommendations: number;
  automated: number;
  manual_only: number;
  data_unavailable: number;
  not_implemented: number;
  automation_rate: number;
  manual_only_items: Array<{ id: string; reason: string }>;
}

export function useFrameworkCoverage(frameworkId: string | undefined) {
  return useQuery({
    queryKey: [...KNOWLEDGE_KEY, "frameworks", frameworkId, "coverage"],
    queryFn: () =>
      apiClient.get<FrameworkCoverageManifest>(`/knowledge/frameworks/${encodeURIComponent(frameworkId as string)}/coverage`),
    enabled: Boolean(frameworkId),
  });
}

export interface FrameworkItem {
  id: string;
  [key: string]: unknown;
}

/** Real, DB-backed (knowledge_service.list_framework_items) — will be an
 * empty array unless a STIG XCCDF / NIST OSCAL bundle has been imported
 * via `POST /knowledge/frameworks/import` first. */
export function useFrameworkItems(frameworkId: string | undefined) {
  return useQuery({
    queryKey: [...KNOWLEDGE_KEY, "frameworks", frameworkId, "items"],
    queryFn: () =>
      apiClient.get<{ items: FrameworkItem[] }>(`/knowledge/frameworks/${encodeURIComponent(frameworkId as string)}/items`),
    enabled: Boolean(frameworkId),
  });
}

// Real shape (knowledge_service.preview_framework_update, Phase 3
// rehearsal follow-up): this build has no versioned framework snapshots,
// so a real added/modified/withdrawn diff or estate-impact simulation
// cannot be computed — `content_changes`/`estate_impact` are genuinely
// `null` rather than fabricated, and `current_item_count`/`note` are the
// only real fields. The richer diff shape this used to assume
// (`from`/`to`/`content_changes.added`/`estate_impact.*`) does not exist
// on the live server and previously crashed this screen with a "Cannot
// read properties of null" render error whenever a real framework had
// been imported (reproduced: import any OSCAL catalog, open Update
// Review).
export interface FrameworkPreview {
  framework_id: string;
  current_item_count: number;
  content_changes: null;
  estate_impact: null;
  note: string;
}

export function useFrameworkPreview() {
  return useMutation({
    mutationFn: (frameworkId: string) =>
      apiClient.post<FrameworkPreview>(`/knowledge/frameworks/${encodeURIComponent(frameworkId)}/preview`),
  });
}

export interface FrameworkRatifyResult {
  framework_id: string;
  status: string;
  ratified_by: string;
}

export function useFrameworkRatify() {
  return useMutation({
    mutationFn: (frameworkId: string) =>
      apiClient.post<FrameworkRatifyResult>(`/knowledge/frameworks/${encodeURIComponent(frameworkId)}/ratify`),
  });
}

export interface KnowledgeFreshness {
  rulepacks: Array<{ id: string; version: string; imported_at: string }>;
  vulnerability_index: { snapshot_date: string; age_days: number };
}

export function useKnowledgeFreshness() {
  return useQuery({
    queryKey: [...KNOWLEDGE_KEY, "freshness"],
    queryFn: () => apiClient.get<KnowledgeFreshness>("/knowledge/freshness"),
  });
}
