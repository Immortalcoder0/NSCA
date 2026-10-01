import type { VerdictType, SeverityType, TrustTierType } from "../shared/theme/tokens";

export type FindingLifecycleState =
  | "Open"
  | "Confirmed"
  | "Disputed"
  | "Remediation_Planned"
  | "Risk_Accepted"
  | "Verified_Resolved";

export type FindingGroupBy = "control" | "device" | "attack_path" | "systemic";

export interface FindingFrameworkMapping {
  framework: string;
  id: string;
  version?: string;
  revision?: string;
  release?: string;
  category?: string;
}

export interface FindingEvidenceSnippet {
  artifact: string;
  lines: [number, number];
  highlight: number[];
  excerpt: string;
  facts?: string[];
  masked_excerpt?: string;
}

export interface FindingModel {
  id: string;
  campaign_id: string;
  device_id: string;
  hostname: string;
  device_platform: string;
  control_id: string;
  rule_id: string;
  title: string;
  description: string;
  verdict: VerdictType;
  severity: {
    base: SeverityType;
    effective: SeverityType;
    reason?: string;
  };
  state: FindingLifecycleState;
  rulepack_trust_tier: TrustTierType;
  frameworks: FindingFrameworkMapping[];
  evidence: FindingEvidenceSnippet[];
  attack_paths: string[];
  systemic_id?: string;
  assigned_to?: string;
  created_at: string;
}

export type DisputeVerificationOutcome = "REFUTED" | "CONFIRMED" | "UNVERIFIABLE";

export interface DisputeCounterexample {
  packet: {
    src: string;
    dst: string;
    dport: number;
    protocol: string;
  };
  path: Array<{
    node: string;
    note?: string;
    action?: string;
  }>;
}

export interface DisputeModel {
  dispute_id: string;
  finding_id: string;
  raised_by: string;
  created_at: string;
  type: "compensating_control" | "false_positive" | "scope_challenge";
  claim: string;
  verification: {
    result: DisputeVerificationOutcome;
    counterexample?: DisputeCounterexample;
    assumptions?: string[];
    confidence: "high" | "medium" | "low";
    reason?: string;
    recommendation?: string;
  };
  adjudication?: {
    decision: "uphold" | "reject" | "accept_as_risk";
    adjudicated_by: string;
    rationale: string;
    timestamp: string;
  };
}

export interface RiskAcceptanceSubmission {
  finding_id: string;
  expires_at: string; // Required date (YYYY-MM-DD)
  justification: string;
  compensating_control?: string;
}
