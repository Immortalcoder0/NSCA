import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../shared/api/client";
import type { EstateDeviceItem, DeviceExposure } from "../types";

export const ESTATE_KEY = ["estate", "devices"] as const;

/**
 * Sort keys for the estate grid. `critical_weighted_exposure` is the
 * REQUIRED default per plans/frontend-01-ingestion-campaigns-estate.md §2.3:
 * "Default sort is by critical findings weighted by exposure, not by
 * compliance percentage ... implement this as the actual default `sort`
 * param sent to the API, not just a client-side reorder that resets on
 * refresh."
 */
export type EstateSortKey =
  | "critical_weighted_exposure"
  | "compliance_asc"
  | "coverage_asc"
  | "hostname";

export const DEFAULT_ESTATE_SORT: EstateSortKey = "critical_weighted_exposure";

const EXPOSURE_WEIGHT: Record<DeviceExposure, number> = {
  internet_facing: 3,
  internal: 2,
  isolated: 1,
  unknown: 1,
};

/** Same weighting the API is asked to apply server-side (`sort` param),
 * duplicated here only so the fallback fixture behaves identically when
 * the real endpoint isn't reachable -- never used to silently override a
 * real API-provided order. */
export function criticalWeightedExposureScore(d: EstateDeviceItem): number {
  const exposureWeight = EXPOSURE_WEIGHT[d.exposure] ?? 1;
  return d.critical_findings_count * exposureWeight * 100 + d.high_findings_count * exposureWeight;
}

export function sortDevicesLocally(devices: EstateDeviceItem[], sort: EstateSortKey): EstateDeviceItem[] {
  const copy = [...devices];
  switch (sort) {
    case "critical_weighted_exposure":
      return copy.sort((a, b) => criticalWeightedExposureScore(b) - criticalWeightedExposureScore(a));
    case "compliance_asc":
      return copy.sort((a, b) => a.compliance_score - b.compliance_score);
    case "coverage_asc":
      return copy.sort((a, b) => a.coverage_score - b.coverage_score);
    case "hostname":
      return copy.sort((a, b) => a.hostname.localeCompare(b.hostname));
    default:
      return copy;
  }
}

export interface UseEstateDevicesParams {
  campaignId: string;
  sort?: EstateSortKey;
  platform?: string;
  exposure?: string;
}

interface EstateDevicesResponse {
  devices: EstateDeviceItem[];
  total: number;
  isFixture: boolean;
}

/**
 * Fetches the estate device grid for a campaign with an explicit `sort`
 * query param (always sent, defaulting to `critical_weighted_exposure`),
 * via `GET /campaigns/{id}/findings?group_by=device&sort=...`.
 *
 * Real, server-side aggregation (`nsca_platform/api/findings.py::list_findings`
 * -> `services/finding_lifecycle.py::device_grid`, dispatched when
 * `group_by=device`): hostname/platform/serial from `device`, compliance/
 * coverage from each device's most recent `assessment` row, critical/high
 * finding counts from a real count over `finding`. `role`/`exposure` are
 * honestly `"unknown"` — that data is graph-derived and not built yet (see
 * `estate/types.ts`), not fabricated as a plausible-looking zone.
 *
 * `parseEstateResponse` still falls back to the local fixture on a network
 * failure or an unexpected response shape, so the screen stays demoable
 * even against an unreachable/older backend — but for a reachable current
 * server this now resolves with real data, not the fixture.
 */
function parseEstateResponse(raw: unknown): EstateDevicesResponse | null {
  if (raw && typeof raw === "object" && Array.isArray((raw as Record<string, unknown>).devices)) {
    return { ...(raw as Omit<EstateDevicesResponse, "isFixture">), isFixture: false };
  }
  return null;
}

export function useEstateDevices(params: UseEstateDevicesParams) {
  const sort = params.sort ?? DEFAULT_ESTATE_SORT;

  return useQuery({
    queryKey: [...ESTATE_KEY, params.campaignId, sort, params.platform, params.exposure],
    queryFn: async () => {
      const query = new URLSearchParams();
      query.set("group_by", "device");
      query.set("sort", sort);
      if (params.platform && params.platform !== "all") query.set("platform", params.platform);
      if (params.exposure && params.exposure !== "all") query.set("exposure", params.exposure);

      try {
        const raw = await apiClient.get<unknown>(
          `/campaigns/${params.campaignId}/findings?${query.toString()}`
        );
        const parsed = parseEstateResponse(raw);
        if (parsed) return parsed;
        // Real call succeeded but returned `{items, next_cursor}` (the
        // real findings-list shape, no per-device grid) rather than
        // `{devices, total}` — fall through to the fixture below exactly
        // as if the request had failed.
      } catch {
        // network/HTTP failure — also fall through
      }

      const { ESTATE_FIXTURE_DEVICES } = await import("../fixtures");
      return {
        devices: sortDevicesLocally(ESTATE_FIXTURE_DEVICES, sort),
        total: ESTATE_FIXTURE_DEVICES.length,
        isFixture: true,
      };
    },
    enabled: Boolean(params.campaignId),
  });
}
