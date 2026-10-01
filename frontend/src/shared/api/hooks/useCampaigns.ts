import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../client";

// The real platform (nsca_platform/api/campaigns.py) returns unstructured
// JSON dicts from its routes rather than declaring `response_model=`
// Pydantic classes, so FastAPI's generated OpenAPI schema has no named
// component for these response shapes (only request-body models like
// `CreateCampaignRequest` exist under `components["schemas"]` — see
// types.gen.ts). Each track defines its own richer domain model
// (e.g. `CampaignModel` in campaigns/types.ts) for actual UI use; these
// hook-level aliases just describe what's on the wire honestly instead of
// referencing schema names that don't exist.
type Campaign = Record<string, unknown>;
type CampaignListResponse = Record<string, unknown>;
type CompletenessResponse = Record<string, unknown>;
interface CreateCampaignRequest {
  name: string;
  scope: unknown;
  frameworks?: string[];
  owner?: string;
  window?: unknown;
  [key: string]: unknown;
}

export const CAMPAIGNS_KEY = ["campaigns"] as const;

export function useCampaigns(params?: { status?: string; owner?: string }) {
  return useQuery({
    queryKey: [...CAMPAIGNS_KEY, params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params?.status) query.append("status", params.status);
      if (params?.owner) query.append("owner", params.owner);
      const qs = query.toString();
      return apiClient.get<CampaignListResponse>(`/campaigns${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useCampaign(id: string) {
  return useQuery({
    queryKey: [...CAMPAIGNS_KEY, id],
    queryFn: () => apiClient.get<Campaign>(`/campaigns/${id}`),
    enabled: Boolean(id),
  });
}

export function useCampaignCompleteness(id: string) {
  return useQuery({
    queryKey: [...CAMPAIGNS_KEY, id, "completeness"],
    queryFn: () => apiClient.get<CompletenessResponse>(`/campaigns/${id}/completeness`),
    enabled: Boolean(id),
  });
}

export function useCreateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateCampaignRequest) =>
      apiClient.post<Campaign>("/campaigns", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CAMPAIGNS_KEY });
    },
  });
}

// ---------------------------------------------------------------------------
// Lifecycle transitions (frontend-01 Phase 2 integration) — real endpoints
// backing `nsca_platform/services/campaign.py`. `scope/resolve` is the only
// call that actually moves a campaign out of `Draft` server-side (into
// `Collecting`); `assess` persists real assessments/findings but does NOT
// change `status` (no `Assessing`/`Review` transition endpoint exists yet
// in the live backend — flagged, not silently faked client-side). `issue`
// is reachable from Draft/Collecting/Assessing/Review; `close` only from
// Issued. See campaigns/pages/CampaignDetailPage.tsx for how the UI reads
// the real `status` back after each call rather than assuming a jump.
// ---------------------------------------------------------------------------

type ScopeResolveResponse = Record<string, unknown>;
type AssessResponse = Record<string, unknown>;
type CompareResponse = Record<string, unknown>;

export function useResolveScope(campaignId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<ScopeResolveResponse>(`/campaigns/${campaignId}/scope/resolve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...CAMPAIGNS_KEY, campaignId] });
    },
  });
}

export function useRunAssessment(campaignId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<AssessResponse>(`/campaigns/${campaignId}/assess`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...CAMPAIGNS_KEY, campaignId] });
    },
  });
}

export function useIssueCampaign(campaignId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<Campaign>(`/campaigns/${campaignId}/issue`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...CAMPAIGNS_KEY, campaignId] });
    },
  });
}

export function useCloseCampaign(campaignId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<Campaign>(`/campaigns/${campaignId}/close`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...CAMPAIGNS_KEY, campaignId] });
    },
  });
}

/** `GET /campaigns/{id}/compare/{other}` — real M1 backend keeps this as a
 * literal stub (`api/campaigns.py`'s own docstring: "compare ... needs the
 * finding lifecycle and knowledge-base diffing machinery, both out of M1
 * scope"), so the response is the same fixed delta-decomposition example
 * regardless of which two campaigns are passed. Still a real network call,
 * not client-side mock data. */
export function useCompareCampaigns(campaignId: string, otherId: string) {
  return useQuery({
    queryKey: [...CAMPAIGNS_KEY, campaignId, "compare", otherId],
    queryFn: () => apiClient.get<CompareResponse>(`/campaigns/${campaignId}/compare/${otherId}`),
    enabled: Boolean(campaignId) && Boolean(otherId),
  });
}
