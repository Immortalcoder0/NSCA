export type ReportFormatType = "pdf" | "docx" | "json" | "csv" | "oscal";

export type ReportVerificationOutcome =
  | "MATCH"
  | "MISMATCH_DIFF_KB"
  | "MISMATCH_SAME_KB"; // Defect state

export interface ReportItemModel {
  id: string;
  campaign_id: string;
  title: string;
  generated_at: string;
  lead_assessor: string;
  sha256_hash: string;
  device_count: number;
  compliance_score: number;
  coverage_score: number;
}

export interface ReportUnassessedControl {
  control_id: string;
  title: string;
  reason: string;
}

export interface ReportDocumentModel {
  id: string;
  campaign_id: string;
  title: string;
  organization: string;
  lead_assessor: string;
  date: string;
  sha256_hash: string;
  knowledge_pin: {
    engine_version: string;
    rulepack_signature: string;
    control_pack_signature: string;
  };
  executive_summary: {
    narrative: string;
    compliance_score: number;
    coverage_score: number;
    meaningful_ratio: number;
  };
  findings: Array<{
    id: string;
    control_id: string;
    title: string;
    verdict: string;
    severity: string;
    hostname: string;
    evidence_excerpt: string;
    start_line: number;
    highlight_lines: number[];
  }>;
  emergent_findings: Array<{
    id: string;
    title: string;
    affected_devices_count: number;
    description: string;
  }>;
  remediation_playbook: Array<{
    step: number;
    action: string;
    device: string;
    impact: string;
  }>;
  unassessed: {
    determined_percentage: number;
    undetermined_percentage: number;
    items: ReportUnassessedControl[];
  };
  assessor_notes: string;
  appendix: string;
}

export interface ReportVerificationResult {
  outcome: ReportVerificationOutcome;
  stored_hash: string;
  recomputed_hash: string;
  knowledge_base_match: boolean;
  timestamp: string;
  details: string;
}
