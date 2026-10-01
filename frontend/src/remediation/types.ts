export type RemediationImpact = "safe" | "service_affecting" | "lockout_risk";

export interface PlaybookStepModel {
  step_number: number;
  title: string;
  device_hostname: string;
  device_platform: string;
  impact: RemediationImpact;
  impact_warning?: string;
  commands: string[];
  rollback_commands: string[];
  depends_on_steps?: number[];
  precedes_steps?: number[];
  findings_resolved: string[];
}

export interface NewlyFailingControl {
  control_id: string;
  rule_id: string;
  title: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  cause_description: string;
}

export interface RemediationDryRunModel {
  playbook_id: string;
  target_campaign_id: string;
  metrics: {
    before_compliance: number;
    after_compliance: number;
    delta: number;
    before_coverage: number;
    after_coverage: number;
    resolved_findings_count: number;
  };
  newly_failing_controls: NewlyFailingControl[];
  steps: PlaybookStepModel[];
}
