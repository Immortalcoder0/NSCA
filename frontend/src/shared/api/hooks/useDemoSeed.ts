import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../client";

// `POST /admin/seed-demo-data` (nsca_platform/services/demo_seed.py) — real
// dataflow seeding, not fabricated client-side state: creates one campaign,
// uploads 8 real multi-platform artifacts, resolves scope, runs a real
// assessment, issues the campaign, generates a real per-device report, and
// seeds a real training-queue entry. Server-side RBAC requires Platform
// Administrator regardless of the UI's currently-selected dev role — this
// is a one-click demo/recovery action, not a normal user workflow, so it
// overrides the role header for just this one call rather than requiring
// the operator to switch roles first.
export interface DemoSeedResult {
  campaign_id: string;
  devices_uploaded: number;
  artifact_outcomes: string[];
  devices_assessed: number;
  assessment_job: string | null;
  report_id: string | null;
  training_platform_seeded: string | null;
  training_questions_seeded: number;
}

export function useSeedDemoData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.post<DemoSeedResult>(
        "/admin/seed-demo-data",
        undefined,
        { headers: { "X-Dev-Role": "platform_administrator" } }
      ),
    onSuccess: () => {
      // Every screen in the app reads through TanStack Query — invalidating
      // everything (no key = every query) is what makes "fill the app with
      // data" actually show up without a manual reload of each page.
      queryClient.invalidateQueries();
    },
  });
}
