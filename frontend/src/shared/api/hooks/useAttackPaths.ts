import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../client";

type AttackPathsResponse = Record<string, unknown>;
type SystemicResponse = Record<string, unknown>;

export const ATTACK_PATHS_KEY = ["attack-paths"] as const;
export const SYSTEMIC_KEY = ["systemic"] as const;

/**
 * `GET /campaigns/{id}/attack-paths` — a real, live network call, but
 * **verified against the running M5 server to still be the M0 stub**
 * (`nsca_platform/api/findings.py::campaign_attack_paths`): it returns the
 * exact same literal `AP-003` example regardless of `campaign_id`, and
 * regardless of whether that campaign has ever been assessed.
 *
 * This is a real backend gap, not a frontend integration bug: the engine
 * *does* compute real per-campaign attack paths
 * (`nsca_engine.risk.attack_paths.compute_attack_paths`, wired into
 * `assess_campaign` and exercised end-to-end by
 * `nsca_engine/tests/test_assess_campaign_ap003.py`), and
 * `services/assessment.py.run_assessment` already calls the real
 * `assess_campaign` and gets a `CampaignAssessment` back — but it only
 * caches `campaign_assessment.graph` (`services/graph_cache.py`, for
 * dispute reachability) and discards `campaign_assessment.attack_paths`.
 * No endpoint currently serves the real computed attack paths for any
 * campaign. Flagged back for Backend Track B / a later milestone rather
 * than silently left looking "done" because the HTTP call succeeds.
 */
export function useCampaignAttackPaths(campaignId: string) {
  return useQuery({
    queryKey: [...ATTACK_PATHS_KEY, campaignId],
    queryFn: () => apiClient.get<AttackPathsResponse>(`/campaigns/${campaignId}/attack-paths`),
    enabled: Boolean(campaignId),
  });
}

/**
 * `GET /campaigns/{id}/systemic` — same situation as attack-paths above: a
 * real network call, verified live to still return the fixed `SYS-000009`
 * example regardless of campaign. There is also no `systemic_id`/cluster
 * column on the `finding` table at all (`db/models/finding.py`), so even a
 * wired version of this endpoint would need new persistence, not just a
 * new query. Flagged, not papered over.
 */
export function useCampaignSystemic(campaignId: string) {
  return useQuery({
    queryKey: [...SYSTEMIC_KEY, campaignId],
    queryFn: () => apiClient.get<SystemicResponse>(`/campaigns/${campaignId}/systemic`),
    enabled: Boolean(campaignId),
  });
}
