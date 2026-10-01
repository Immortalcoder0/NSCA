import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, ApiError } from "../client";

// See useCampaigns.ts's note: nsca_platform's ingestion routes
// (`nsca_platform/api/ingestion.py`) return unstructured JSON, so no named
// `components["schemas"]` response type exists for these either — the real
// per-artifact result shape actually *varies by outcome status*
// (`services/ingestion.py::_classify_and_persist`): a `parsed` result has
// no `caveat`/`training` keys, `parsed_with_caveat` adds `caveat`,
// `platform_not_taught` adds `training`, `unidentified` drops `platform`
// entirely. Each track's own domain model does the narrowing; this hook
// layer just describes what's honestly on the wire.
export type IngestionArtifactResult = Record<string, unknown>;

export interface UploadArtifactsResponse {
  job_id: string;
  accepted: number;
  results: IngestionArtifactResult[];
}

export const INGESTION_KEY = ["ingestion"] as const;

/** `POST /campaigns/{id}/artifacts` (multipart) — real, DB-backed hashing +
 * four-outcome-state classification (`services/ingestion.py`).
 *
 * `shared/api/client.ts`'s `ApiClient.post()` always
 * `JSON.stringify()`s its body and forces `Content-Type: application/json`
 * (see its `getHeaders`/`post` implementation) — correct for every other
 * mutation hook in this app, but wrong for a multipart file upload, which
 * needs the browser to set its own `Content-Type: multipart/form-data;
 * boundary=...` header. Since `shared/` is frozen for this track, this
 * hook does its own `fetch` call for just this one request instead of
 * routing it through `apiClient`, reusing the same base URL, dev-role, and
 * bearer-token conventions `apiClient` itself uses so auth still behaves
 * identically to every other call in the app.
 */
export function useUploadArtifacts(campaignId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (files: File[]) => {
      const form = new FormData();
      for (const file of files) form.append("files", file);

      const headers = new Headers();
      try {
        const token = localStorage.getItem("nsca_auth_token");
        if (token) headers.set("Authorization", `Bearer ${token}`);
        const devRole = localStorage.getItem("nsca_dev_role");
        if (devRole) headers.set("X-Dev-Role", devRole);
      } catch {
        // SSR/test environment without localStorage — proceed unauthenticated
      }

      const response = await fetch(`/api/v1/campaigns/${campaignId}/artifacts`, {
        method: "POST",
        headers,
        body: form,
      });

      if (!response.ok) {
        let detail = `HTTP Error ${response.status}: ${response.statusText}`;
        try {
          const body = await response.json();
          if (body && typeof body.detail === "string") detail = body.detail;
        } catch {
          // no JSON body
        }
        throw new ApiError(response.status, response.statusText, detail);
      }

      return response.json() as Promise<UploadArtifactsResponse>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...INGESTION_KEY, campaignId] });
      queryClient.invalidateQueries({ queryKey: ["campaigns", campaignId, "completeness"] });
    },
  });
}

export interface CollectionTargetInput {
  host: string;
  credential_ref: string;
}

export interface StartCollectionBody {
  targets: CollectionTargetInput[];
  artifacts: string[];
  mode: "read_only";
}

type StartCollectionResponse = Record<string, unknown>;

/** `POST /campaigns/{id}/collect` — M1 backend keeps this as the M0 stub
 * (`api/ingestion.py`: "real collectors and the job queue land in a later
 * milestone"), always returning a fixed `{job_id, status: "queued"}`
 * regardless of the real targets/artifacts submitted. Still a real network
 * call with the real, schema-enforced `mode: "read_only"` (Literal type at
 * the Pydantic level — G4), not client-side mock data. */
export function useStartCollection(campaignId: string) {
  return useMutation({
    mutationFn: (body: StartCollectionBody) =>
      apiClient.post<StartCollectionResponse>(`/campaigns/${campaignId}/collect`, body),
  });
}

type JobResponse = Record<string, unknown>;

/** `GET /jobs/{id}` — M1 ingestion runs synchronously (no real job queue
 * yet), so this always reports `completed` for any job id this process
 * issued (`api/ingestion.py`'s own docstring). Kept as a real polling hook
 * regardless, since `ProgressPanel` renders honestly off whatever it
 * returns. */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: [...INGESTION_KEY, "job", jobId],
    queryFn: () => apiClient.get<JobResponse>(`/jobs/${jobId}`),
    enabled: Boolean(jobId),
  });
}
