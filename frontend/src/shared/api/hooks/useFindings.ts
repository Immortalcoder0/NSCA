import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../client";

// See useCampaigns.ts's note: nsca_platform's findings routes return
// unstructured JSON, so no named `components["schemas"]` response type
// exists for these — each track's own domain model (e.g. `FindingModel`)
// is the real typed shape used for rendering.
type Finding = Record<string, unknown>;
type FindingListResponse = Record<string, unknown>;
type DisputeResponse = Record<string, unknown>;
type BulkResponse = Record<string, unknown>;
type HistoryResponse = Record<string, unknown>;
type ArtifactResponse = Record<string, unknown>;

export const FINDINGS_KEY = ["findings"] as const;

export interface FindingsFilterParams {
  verdict?: string;
  severity?: string;
  state?: string;
  control?: string;
}

// M5 correction: the real router (nsca_platform/api/findings.py) exposes
// findings as `GET /campaigns/{campaign_id}/findings` (campaign-scoped path
// segment), not `GET /findings?campaign_id=...` — the M1-era shape this
// hook previously assumed. Query params are the real filter keys the
// service layer (`finding_lifecycle.list_findings`) actually reads:
// verdict/severity/state/control (no `device_id` filter exists server-side
// today — findings don't even carry a `device` field in the response, see
// `fetchFinding` below).
export function fetchCampaignFindings(
  campaignId: string,
  filters?: FindingsFilterParams
): Promise<FindingListResponse> {
  const query = new URLSearchParams();
  if (filters?.verdict) query.append("verdict", filters.verdict);
  if (filters?.severity) query.append("severity", filters.severity);
  if (filters?.state) query.append("state", filters.state);
  if (filters?.control) query.append("control", filters.control);
  const qs = query.toString();
  return apiClient.get<FindingListResponse>(
    `/campaigns/${campaignId}/findings${qs ? `?${qs}` : ""}`
  );
}

export function useCampaignFindings(campaignId: string, filters?: FindingsFilterParams) {
  return useQuery({
    queryKey: [...FINDINGS_KEY, campaignId, filters],
    queryFn: () => fetchCampaignFindings(campaignId, filters),
    enabled: Boolean(campaignId),
  });
}

// `GET /findings/{id}` — real, `finding_lifecycle._row_to_response`.
// **Surprise flagged**: the real response has no `hostname`/`device`,
// `campaign_id`, `title`, `description`, `rule_id`, or `created_at` field —
// only `id, control, verdict, severity{base,effective,reason}, evidence[],
// frameworks[], attack_paths[], rulepack_trust_tier, state, owner,
// due_date`. Callers needing the richer `FindingModel` shape (this track's
// components) must synthesize/derive the rest — see
// `findings/api/mapFinding.ts`.
export function fetchFinding(id: string): Promise<Finding> {
  return apiClient.get<Finding>(`/findings/${id}`);
}

export function useFinding(id: string) {
  return useQuery({
    queryKey: [...FINDINGS_KEY, id],
    queryFn: () => fetchFinding(id),
    enabled: Boolean(id),
  });
}

export function useFindingHistory(id: string) {
  return useQuery({
    queryKey: [...FINDINGS_KEY, id, "history"],
    queryFn: () => apiClient.get<HistoryResponse>(`/findings/${id}/history`),
    enabled: Boolean(id),
  });
}

// `GET /artifacts/{id}` (nsca_platform/api/ingestion.py) — the only real
// way to resolve a finding's device hostname/platform today, since findings
// themselves don't carry `device_id`/`hostname`: each evidence entry names
// its source `artifact`, and the artifact row does carry `device`
// (hostname) + `platform`. Best-effort only — findings whose evidence array
// is empty (many controls evaluate to UNKNOWN/NOT_APPLICABLE with no
// artifact line reference in this milestone) cannot be resolved this way.
export function fetchArtifact(artifactId: string): Promise<ArtifactResponse> {
  return apiClient.get<ArtifactResponse>(`/artifacts/${artifactId}`);
}

export function useArtifact(artifactId: string | undefined) {
  return useQuery({
    queryKey: ["artifacts", artifactId],
    queryFn: () => fetchArtifact(artifactId as string),
    enabled: Boolean(artifactId),
    staleTime: 5 * 60 * 1000,
  });
}

function invalidateFinding(queryClient: ReturnType<typeof useQueryClient>, id: string) {
  queryClient.invalidateQueries({ queryKey: FINDINGS_KEY });
  queryClient.invalidateQueries({ queryKey: [...FINDINGS_KEY, id] });
}

export function useConfirmFinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.post<Finding>(`/findings/${id}/confirm`),
    onSuccess: (_data, id) => invalidateFinding(queryClient, id),
  });
}

export function useAssignFinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, assignee }: { id: string; assignee: string }) =>
      apiClient.post<Finding>(`/findings/${id}/assign`, { assignee }),
    onSuccess: (_data, { id }) => invalidateFinding(queryClient, id),
  });
}

export function useMarkFindingRemediated() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.post<Finding>(`/findings/${id}/mark-remediated`),
    onSuccess: (_data, id) => invalidateFinding(queryClient, id),
  });
}

// `POST /findings/{id}/dispute` — real, `services/dispute.py`. For
// `compensating_control` claims this synchronously runs
// `verify_compensating_control` (real engine reachability query when a
// cached campaign `Graph` exists AND the claim names two concrete IPv4
// addresses; otherwise the documented MGMT-SW-04/`UNVERIFIABLE` local
// fallback) and returns the verdict inline — there is no separate "poll for
// verification result" step.
export function useDisputeFinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, type, claim }: { id: string; type: string; claim: string }) =>
      apiClient.post<DisputeResponse>(`/findings/${id}/dispute`, { type, claim }),
    onSuccess: (_data, { id }) => invalidateFinding(queryClient, id),
  });
}

// `POST /findings/{id}/adjudicate` — real, Lead-Assessor-gated
// (`require_role(Role.LEAD_ASSESSOR)`). NOTE the real request literal is
// `decision: "upheld" | "overturned"` (the dispute's claim being upheld or
// rejected) — NOT the three-way `uphold | reject | accept_as_risk` this
// track's mock UI used. `upheld` (claim accepted) -> finding `Withdrawn`;
// `overturned` (claim rejected) -> finding returns to `Confirmed`. Risk
// acceptance is a structurally separate transition (`accept-risk` below),
// not a third adjudication outcome server-side.
export function useAdjudicateFinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      decision,
      notes,
    }: {
      id: string;
      decision: "upheld" | "overturned";
      notes?: string;
    }) => apiClient.post<Finding>(`/findings/${id}/adjudicate`, { decision, notes }),
    onSuccess: (_data, { id }) => invalidateFinding(queryClient, id),
  });
}

export interface AcceptRiskPayload {
  id: string;
  expires_at: string; // YYYY-MM-DD
  justification: string;
  compensating_control?: Record<string, unknown> | null;
}

// `POST /findings/{id}/accept-risk` — real, Lead-Assessor-gated.
// `expires_at` is required + must be strictly future-dated server-side
// (422 otherwise) — the UI-level validation in RiskAcceptanceModal mirrors
// this so the 422 is never the first time a user learns the rule.
export function useAcceptFindingRisk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: AcceptRiskPayload) =>
      apiClient.post<Finding>(`/findings/${id}/accept-risk`, body),
    onSuccess: (_data, { id }) => invalidateFinding(queryClient, id),
  });
}

// `POST /findings/bulk` — real, `finding_lifecycle.bulk_transition`.
// **Verified against the live M5 server (not just source-read)**: the
// action_map only wires `confirm` and `mark-remediated`; any other action
// string is a silent no-op (`updated: 0`) rather than a 4xx — the client
// must not call this with `adjudicate`/`assign`/`accept-risk`. It is also
// NOT cluster-scoped: callers must already know and send the member
// `finding_ids`, there is no server-side `systemic_id` resolution.
export function useBulkFindings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ findingIds, action }: { findingIds: string[]; action: "confirm" | "mark-remediated" }) =>
      apiClient.post<BulkResponse>("/findings/bulk", { finding_ids: findingIds, action }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: FINDINGS_KEY }),
  });
}
