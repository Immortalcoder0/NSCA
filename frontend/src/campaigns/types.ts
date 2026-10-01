export type CampaignLifecycleState =
  | "Draft"
  | "Collecting"
  | "Assessing"
  | "Review"
  | "Issued"
  | "Closed";

export interface CampaignFramework {
  framework: string;
  benchmark?: string;
  catalog?: string;
  revision?: string;
  version?: string;
  release?: string;
}

export interface CampaignModel {
  id: string;
  name: string;
  status: CampaignLifecycleState;
  scope: {
    type: string;
    expression: string;
  };
  frameworks: CampaignFramework[];
  owner: string;
  window: {
    start: string;
    end: string;
  };
  knowledge_pin?: {
    engine_version: string;
    rulepacks: Array<{ id: string; version: string }>;
    control_packs: Array<{ id: string; version: string }>;
  };
  device_count?: number;
  compliance_score?: number;
  coverage_score?: number;
}

export interface DeltaDecompositionItem {
  cause: "verified_remediation" | "framework_version_change" | "scope_change" | "configuration_regression";
  delta: number;
  findings?: number;
  detail?: string;
}

export interface CampaignComparisonData {
  from: string;
  to: string;
  compliance: {
    from: number;
    to: number;
  };
  decomposition: DeltaDecompositionItem[];
}
