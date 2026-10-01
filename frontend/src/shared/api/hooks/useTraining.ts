import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, ApiError } from "../client";

// See useCampaigns.ts's note: no named response schema exists for these
// routes (the backend returns unstructured JSON dicts). The interfaces
// below describe the *real* wire shapes observed from the live server
// (nsca_platform/api/training.py + services/training.py), captured while
// wiring this track's screens to real data (Phase 2 / M6) — not the
// spec's illustrative examples, which drifted from what the service
// layer actually returns in a few places (documented per-field below).

export const TRAINING_KEY = ["training"] as const;

export interface TrainingQueuePlatformSummary {
  platform: string;
  // The service layer (services/training.py:platforms_with_pending_questions)
  // cross-references the real KnowledgeBase (the same computation
  // `GET /knowledge/rulepacks/{id}/coverage` uses) so this reflects live
  // teaching progress within the same session — "platform_not_taught" while
  // coverage is genuinely 0, "platform_partially_taught" once any ratified
  // extractor has raised it. "unidentified" (12-ux-specification.md §6.1)
  // still has no backing signal from this endpoint.
  gap: string;
  questions_prepared: number;
  questions_remaining: number;
  coverage: number;
}

interface TrainingQueueResponse {
  platforms: TrainingQueuePlatformSummary[];
}

export function useTrainingQueue() {
  return useQuery({
    queryKey: [...TRAINING_KEY, "queue"],
    queryFn: () => apiClient.get<TrainingQueueResponse>("/training/queue"),
  });
}

export interface TrainingQuestionExample {
  line: number | null;
  text: string;
}

export interface TrainingProposalMapping {
  fact: string;
  token: string;
  justification: string;
}

export interface TrainingProposalSignal {
  kind: string;
  detail: string;
  contribution: number;
}

export interface TrainingProposalPolarity {
  inverted: boolean;
  indicator: string | null;
  requires_explicit_confirmation: boolean;
}

export interface TrainingProposal {
  source: string;
  signals: TrainingProposalSignal[];
  mappings: TrainingProposalMapping[];
  polarity: TrainingProposalPolarity;
  confidence: number;
  description: string;
}

export interface TrainingQuestionImpact {
  facts_resolved: number;
  controls_unlocked: number;
  coverage_before: number | null;
  coverage_after_estimate: number | null;
}

export interface TrainingQuestionApiModel {
  question_id: string;
  position: number;
  total: number;
  section: string;
  pattern: string;
  examples: TrainingQuestionExample[];
  proposal: TrainingProposal;
  impact: TrainingQuestionImpact;
}

export function useTrainingQueuePlatform(platform: string) {
  return useQuery({
    queryKey: [...TRAINING_KEY, "queue", platform],
    queryFn: () =>
      apiClient.get<{ platform: string; questions: TrainingQuestionApiModel[] }>(
        `/training/queue/${encodeURIComponent(platform)}`
      ),
    enabled: Boolean(platform),
  });
}

/** `GET /training/queue/{platform}/next` 404s once every question has been
 * answered — that is the real, documented "queue exhausted" signal
 * (services/training.py:next_question returns None -> the router raises
 * 404), not an error condition, so this hook resolves it to `null` rather
 * than surfacing it as a query error. */
export function useTrainingNextQuestion(platform: string) {
  return useQuery({
    queryKey: [...TRAINING_KEY, "next", platform],
    queryFn: async (): Promise<TrainingQuestionApiModel | null> => {
      try {
        return await apiClient.get<TrainingQuestionApiModel>(
          `/training/queue/${encodeURIComponent(platform)}/next`
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    enabled: Boolean(platform),
  });
}

export interface TrainingSessionResponse {
  id: string;
  platform: string;
  order: number;
  administrator: string;
  corpus_size: number;
  construct_count: number;
  complete: boolean;
  same_family_as: string | null;
  confirmations_to_70pct: number | null;
  wall_clock_minutes: number | null;
  proposal_acceptance_rate: number | null;
  edit_rate: number | null;
  polarity_correction_rate: number | null;
  not_relevant_rate: number | null;
  questions_to_first_finding: number | null;
}

/** `POST /training/sessions` — opens the `transfer_metric_session` row a
 * teaching pass needs so `POST /training/answer`'s `session_id` has
 * somewhere real to point, and so `GET /training/metrics` has anything to
 * report at all (previously unreachable from the UI — no route exposed
 * `transfer_metrics.start_session`, so every live confirmation was recorded
 * session-less and the learning curve stayed permanently empty). */
export function useStartTrainingSession() {
  return useMutation({
    mutationFn: (body: { platform: string; corpus_size?: number; construct_count?: number }) =>
      apiClient.post<TrainingSessionResponse>("/training/sessions", body),
  });
}

export function useCompleteTrainingSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sessionId, wallClockMinutes }: { sessionId: string; wallClockMinutes: number }) =>
      apiClient.post<TrainingSessionResponse>(`/training/sessions/${encodeURIComponent(sessionId)}/complete`, {
        wall_clock_minutes: wallClockMinutes,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...TRAINING_KEY, "metrics"] }),
  });
}

export type TrainingAnswerResponseKind = "confirm" | "polarity_inverted" | "edit" | "not_relevant" | "skip";

export interface TrainingAnswerRequestBody {
  question_id: string;
  response: TrainingAnswerResponseKind;
  polarity_confirmed?: boolean | null;
  edits?: Record<string, unknown> | null;
  taught_by?: string;
  source_artifact?: string;
  session_id?: string;
}

export interface TrainingRuleSummary {
  id: string;
  extractor_id: string;
  version: number;
  platform: string;
  rulepack: string;
  status: string;
  taught_by: string;
  taught_at: string | null;
  ratified_by: string | null;
  ratified_at: string | null;
  source_artifact: string;
  confirmed_examples: number;
  polarity_confirmed: boolean | null;
}

export interface TrainingAnswerResponse {
  question_id: string;
  response: string;
  accepted: boolean;
  rule?: {
    status: string;
    reason?: string;
    rules?: TrainingRuleSummary[];
  };
}

export function useSubmitTrainingAnswer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TrainingAnswerRequestBody) =>
      apiClient.post<TrainingAnswerResponse>("/training/answer", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TRAINING_KEY });
    },
  });
}

export function useTrainingRules(status?: string) {
  return useQuery({
    queryKey: [...TRAINING_KEY, "rules", status],
    queryFn: () => {
      const qs = status ? `?status=${encodeURIComponent(status)}` : "";
      return apiClient.get<{ items: TrainingRuleSummary[] }>(`/training/rules${qs}`);
    },
  });
}

export function useRatifyRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: string) =>
      apiClient.post<TrainingRuleSummary>(`/training/rules/${encodeURIComponent(ruleId)}/ratify`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...TRAINING_KEY, "rules"] }),
  });
}

export function useRejectRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: string) =>
      apiClient.post<TrainingRuleSummary>(`/training/rules/${encodeURIComponent(ruleId)}/reject`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...TRAINING_KEY, "rules"] }),
  });
}

export interface TrainingMetricsResponse {
  platforms: unknown[];
  trend: string;
  polarity_safety_signal: unknown;
}

export function useTrainingMetrics() {
  return useQuery({
    queryKey: [...TRAINING_KEY, "metrics"],
    queryFn: () => apiClient.get<TrainingMetricsResponse>("/training/metrics"),
  });
}
