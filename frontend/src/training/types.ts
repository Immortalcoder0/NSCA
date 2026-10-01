export type PlatformTrainingStatus = "not_taught" | "partial" | "unidentified";

export interface TrainingQueueItem {
  platform: string;
  display_name: string;
  status: PlatformTrainingStatus;
  // The real `GET /training/queue` endpoint (services/training.py
  // platforms_with_pending_questions) reports platform/gap/coverage/question
  // counts — it has no device inventory or time-estimate fields. Optional
  // here so the card can honestly omit what the live API doesn't provide
  // instead of fabricating a number (see PlatformQueueCard.tsx).
  device_count?: number;
  current_coverage: number;
  grammar_coverage?: number;
  question_count: number;
  estimated_minutes?: number;
}

export interface TrainingSnippet {
  artifact: string;
  start_line: number;
  highlight_lines: number[];
  content: string;
}

export interface TrainingPlainReading {
  raw_clause: string;
  statement: string;
  mapped_concept: string;
  normalized_property: string;
}

export interface TrainingPolarityCheck {
  requires_explicit_confirmation: boolean;
  prompt: string;
  proposed_polarity: "positive" | "negative";
  explanation: string;
}

export interface TrainingQuestionModel {
  id: string;
  platform: string;
  question_index: number;
  total_questions: number;
  snippet: TrainingSnippet;
  plain_reading: TrainingPlainReading;
  polarity: TrainingPolarityCheck;
  controls_unlocked: number;
  estimated_time_remaining: string;
}

export interface TrainingResultModel {
  platform: string;
  display_name: string;
  previous_coverage: number;
  new_coverage: number;
  confirmations_count: number;
  elapsed_time_formatted: string;
  rulepack_id: string;
  rulepack_version: string;
}

export interface ValidationGateItem {
  id: string;
  name: string;
  description: string;
  status: "passed" | "failed";
  details?: string;
}

export interface RatificationModel {
  rulepack_id: string;
  rulepack_version: string;
  platform: string;
  taught_by: string;
  gates: ValidationGateItem[];
}
