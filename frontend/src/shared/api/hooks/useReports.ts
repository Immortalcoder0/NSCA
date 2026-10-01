import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../client";

// See useCampaigns.ts's note: most `/reports/*` routes return unstructured
// JSON dicts (nsca_platform/api/reports.py delegates to
// services/report_service.py, which builds plain dicts, not
// `response_model=` Pydantic classes). The one exception is the JSON
// *download* format (`GET /reports/{id}/download?format=json`, rendered by
// reporting/exports.py:to_json) — that one has a genuinely rich, stable
// shape (it's the same `DeviceReportData` the PDF/DOCX renderers consume),
// so it gets a real interface below instead of `Record<string, unknown>`.
//
// `GET /reports` (optionally `?campaign_id=`) is real — a query against the
// `report` table, ordered newest-first. The Library page previously worked
// around its absence by tracking known report ids client-side
// (`reports/lib/knownReportIds.ts`); that workaround is no longer needed
// for the list itself, though `knownReportIds` is still useful as a
// "recently generated in this browser" convenience.

export const REPORTS_KEY = ["reports"] as const;

export interface ReportListItem {
  id: string;
  campaign_id: string | null;
  device: string | null;
  mode: string;
  state: string;
  generated_at: string;
  formats_available: string[];
  hash: string | null;
}

export function useReportsList(campaignId?: string) {
  return useQuery({
    queryKey: [...REPORTS_KEY, "list", campaignId ?? null],
    queryFn: () => {
      const qs = campaignId ? `?campaign_id=${encodeURIComponent(campaignId)}` : "";
      return apiClient.get<{ items: ReportListItem[]; next_cursor: string | null }>(`/reports${qs}`);
    },
  });
}

export interface ReportMeta {
  id: string;
  campaign_id: string | null;
  device: string | null;
  generated_at: string;
  formats_available: string[];
  hash: string | null;
}

export function useReportMeta(reportId: string | undefined) {
  return useQuery({
    queryKey: [...REPORTS_KEY, "meta", reportId],
    queryFn: () => apiClient.get<ReportMeta>(`/reports/${encodeURIComponent(reportId as string)}`),
    enabled: Boolean(reportId),
  });
}

export interface ReportRatio {
  numerator: number;
  denominator: number;
}

export interface ReportScores {
  compliance: ReportRatio;
  coverage: ReportRatio;
  meaningful: ReportRatio;
  security_posture: ReportRatio;
  pass_count: number;
  fail_count: number;
  unknown_count: number;
  not_applicable_count: number;
  severity_counts: Record<string, number>;
}

export interface ReportFindingJson {
  finding_id: string;
  control_id: string;
  title: string;
  verdict: string;
  severity: { base: string; effective: string; reason: string | null };
  frameworks: string[];
  evidence: {
    artifact: string | null;
    lines: Array<{ number: number; text: string; highlighted: boolean; masked: boolean }>;
  };
  facts: string[];
  is_emergent: boolean;
  counterexample: string[];
  contributing_devices: string[];
  remediation_ref: string | null;
  rule_status: string;
  rulepack_trust_tier: string | null;
}

export interface ReportJsonDocument {
  report_id: string;
  mode: string;
  generated_at: string;
  device: {
    hostname: string;
    model: string | null;
    os_version: string | null;
    serials: Array<{ component: string; serial: string }>;
    role: string | null;
    exposure: string | null;
    location: string | null;
  };
  campaign: {
    name: string;
    assessed_at: string;
    assessor: string;
    frameworks: Array<{ name: string; version: string }>;
  };
  inputs: Array<{ filename: string; sha256: string; export_mode: string }>;
  scores: ReportScores;
  findings: ReportFindingJson[];
  emergent_findings: ReportFindingJson[];
  unassessed: Array<{ control_ids: string[]; cause: string; resolution: string | null }>;
  knowledge_base: {
    engine: string;
    rulepack: { id: string; version: string; trust_tier: string };
    control_pack: { id: string; version: string };
    frameworks: Array<{ label: string; version: string }>;
    schema_registry: string;
  };
  report_hash: string | null;
}

/** Full 8-section source document — fetched via the real JSON *download*
 * format rather than a dedicated "get document" endpoint, because no such
 * endpoint exists; `GET /reports/{id}` only returns lightweight meta
 * (formats available, hash, campaign/device ids). */
export function useReportDocument(reportId: string | undefined) {
  return useQuery({
    queryKey: [...REPORTS_KEY, "document", reportId],
    queryFn: async () => {
      const blob = await apiClient.getBlob(
        `/reports/${encodeURIComponent(reportId as string)}/download?format=json`
      );
      const text = await blob.text();
      return JSON.parse(text) as ReportJsonDocument;
    },
    enabled: Boolean(reportId),
  });
}

export interface ReportManifest {
  report_id: string;
  generated: string;
  inputs: Array<{ artifact: string; sha256: string }>;
  knowledge_base: {
    engine: string;
    rulepacks: Array<{ id: string; version: string }>;
    control_packs: Array<{ id: string; version: string }>;
  };
  report_hash: string;
  statement: string;
}

export function useReportManifest(reportId: string | undefined) {
  return useQuery({
    queryKey: [...REPORTS_KEY, "manifest", reportId],
    queryFn: () => apiClient.get<ReportManifest>(`/reports/${encodeURIComponent(reportId as string)}/manifest`),
    enabled: Boolean(reportId),
  });
}

export interface ReportVerifyResult {
  report_id: string;
  result: "MATCH" | "MISMATCH" | "UNVERIFIABLE";
  original_hash: string | null;
  recomputed_hash: string | null;
  knowledge_base_identical: boolean | null;
}

export function useVerifyReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reportId: string) =>
      apiClient.post<ReportVerifyResult>(`/reports/${encodeURIComponent(reportId)}/verify`),
    onSuccess: (_data, reportId) => {
      queryClient.invalidateQueries({ queryKey: [...REPORTS_KEY, "meta", reportId] });
    },
  });
}

export interface GenerateReportResponse {
  job_id: string;
  status: string;
  report_id: string;
}

export function useGenerateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      campaignId,
      device,
      mode = "issued",
    }: {
      campaignId: string;
      device: string;
      mode?: "draft" | "issued";
    }) =>
      apiClient.post<GenerateReportResponse>(
        `/campaigns/${encodeURIComponent(campaignId)}/reports/generate?device=${encodeURIComponent(
          device
        )}&mode=${mode}`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: REPORTS_KEY });
    },
  });
}

/** Real byte download — builds the same URL the browser will fetch with
 * this session's auth headers, used by ExportFormatDropdown. */
export async function downloadReportFile(reportId: string, format: string, suggestedName: string): Promise<void> {
  const blob = await apiClient.getBlob(`/reports/${encodeURIComponent(reportId)}/download?format=${format}`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
