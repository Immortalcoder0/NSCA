import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../client";

type RemediationResponse = Record<string, unknown>;

export const REMEDIATION_KEY = ["remediation"] as const;

/**
 * `GET /findings/{id}/remediation` — a real, live network call, but
 * **verified against the running M5 server to still be the M0 stub**
 * (`nsca_platform/api/findings.py::finding_remediation`): the response is
 * two hardcoded steps ("disable telnet" / "enable ssh v2 only") plus a
 * fixed `dry_run: {result: "no_lockout_detected", confidence: "high"}`,
 * identical for every `finding_id`.
 *
 * The real remediation planner/dry-run/lockout-check logic *exists* —
 * `nsca_platform/remediation/planner.py`, `dry_run.py`, `lockout.py` (M4,
 * version-specific command selection, dependency ordering, impact
 * classification, all reading the control packs' `remediation:` YAML
 * blocks) — but is not wired to any HTTP route yet (confirmed: no
 * `nsca_platform/api/*.py` router imports from `nsca_platform.remediation`
 * at all). The playbook/dry-run screens on this track therefore cannot
 * show real, finding-specific remediation content from the live API today
 * — flagged back rather than silently left looking wired.
 */
export function useFindingRemediation(findingId: string) {
  return useQuery({
    queryKey: [...REMEDIATION_KEY, findingId],
    queryFn: () => apiClient.get<RemediationResponse>(`/findings/${findingId}/remediation`),
    enabled: Boolean(findingId),
  });
}
