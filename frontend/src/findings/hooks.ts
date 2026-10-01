import { useQuery } from "@tanstack/react-query";
import { fetchCampaignFindings, fetchFinding, fetchArtifact } from "../shared/api/hooks/useFindings";
import type { FindingsFilterParams } from "../shared/api/hooks/useFindings";
import { mapApiFindingToModel } from "./api/mapFinding";
import type { ApiFindingRaw, ResolvedDeviceInfo } from "./api/mapFinding";
import { FINDINGS_FIXTURE, FINDING_DETAIL_FIXTURE } from "./fixtures";
import type { FindingModel } from "./types";

// Same default-campaign convention `estate/pages/EstateGridPage.tsx`
// established (`?campaign=` search param, defaulting to the one seeded for
// M5 integration testing — see this track's M5 report for exactly how it
// was seeded: two real AP-003 fixture artifacts, uploaded + assessed
// through the live API).
export const DEFAULT_CAMPAIGN_ID = "CMP-2026Q3-001";

/** Resolves hostname/platform for every unique evidence artifact id in one
 * raw findings page, tolerating individual lookup failures (an artifact id
 * that 404s, or the whole call failing offline) rather than letting one bad
 * lookup blank out an otherwise-good findings list. */
async function resolveDeviceInfoByArtifact(
  raws: ApiFindingRaw[]
): Promise<Map<string, ResolvedDeviceInfo>> {
  const artifactIds = Array.from(
    new Set(
      raws
        .map((r) => r.evidence?.find((e) => e.artifact)?.artifact)
        .filter((a): a is string => Boolean(a))
    )
  );

  const results = await Promise.allSettled(artifactIds.map((id) => fetchArtifact(id)));
  const byArtifact = new Map<string, ResolvedDeviceInfo>();
  results.forEach((result, idx) => {
    if (result.status === "fulfilled") {
      const artifact = result.value as Record<string, unknown>;
      byArtifact.set(artifactIds[idx], {
        hostname: typeof artifact.device === "string" ? artifact.device : undefined,
        platform: typeof artifact.platform === "string" ? artifact.platform : undefined,
      });
    }
  });

  const byFinding = new Map<string, ResolvedDeviceInfo>();
  for (const raw of raws) {
    const artifactId = raw.evidence?.find((e) => e.artifact)?.artifact;
    if (artifactId && byArtifact.has(artifactId)) {
      byFinding.set(raw.id, byArtifact.get(artifactId) as ResolvedDeviceInfo);
    }
  }
  return byFinding;
}

export const WORKBENCH_FINDINGS_KEY = ["findings", "workbench"] as const;

/**
 * Real end-to-end read for the finding workbench: `GET
 * /campaigns/{id}/findings`, real device-hostname resolution via each
 * finding's primary evidence artifact, mapped onto `FindingModel`. Falls
 * back to the bundled fixture (`findings/fixtures.ts`, same shape the
 * Phase-1 mock used) on any network failure — same fixture-fallback
 * pattern as `estate/hooks/useEstateDevices.ts` — so the workbench still
 * renders deterministically offline or in a test environment with no
 * backend, and never shows a hard error for what is, on this track,
 * a browse-only screen degrading gracefully.
 */
export function useWorkbenchFindings(campaignId: string, filters?: FindingsFilterParams) {
  return useQuery({
    queryKey: [...WORKBENCH_FINDINGS_KEY, campaignId, filters],
    queryFn: async (): Promise<FindingModel[]> => {
      try {
        const response = await fetchCampaignFindings(campaignId, filters);
        const items = (response.items as ApiFindingRaw[] | undefined) ?? [];
        const deviceInfoByFinding = await resolveDeviceInfoByArtifact(items);
        return items.map((raw) => mapApiFindingToModel(raw, campaignId, deviceInfoByFinding.get(raw.id)));
      } catch {
        return FINDINGS_FIXTURE;
      }
    },
    enabled: Boolean(campaignId),
  });
}

export const FINDING_DETAIL_KEY = ["findings", "detail"] as const;

/** Real end-to-end read for the finding detail page: `GET
 * /findings/{id}`, same device-hostname resolution + mapping + fixture
 * fallback as `useWorkbenchFindings` above. */
export function useFindingDetailModel(id: string | undefined, campaignId: string) {
  return useQuery({
    queryKey: [...FINDING_DETAIL_KEY, id],
    queryFn: async (): Promise<FindingModel> => {
      try {
        const raw = (await fetchFinding(id as string)) as unknown as ApiFindingRaw;
        const deviceInfoByFinding = await resolveDeviceInfoByArtifact([raw]);
        return mapApiFindingToModel(raw, campaignId, deviceInfoByFinding.get(raw.id));
      } catch {
        return { ...FINDING_DETAIL_FIXTURE, id: id ?? FINDING_DETAIL_FIXTURE.id };
      }
    },
    enabled: Boolean(id),
  });
}
