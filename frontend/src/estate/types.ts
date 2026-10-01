import type { TrustTierType } from "../shared/theme/tokens";

// "unknown" is real, not a placeholder: exposure is a graph-derived,
// per-campaign computation (`nsca_platform/db/models/device.py`'s own
// docstring — "Derived from graph, per campaign", M3+ risk/graph work) that
// does not exist in this build. The real `group_by=device` endpoint
// (`finding_lifecycle.device_grid`) reports it honestly as "unknown" rather
// than fabricating a plausible-looking zone.
export type DeviceExposure = "internet_facing" | "internal" | "isolated" | "unknown";

export interface EstateDeviceItem {
  id: string;
  hostname: string;
  platform: string;
  os_version: string;
  serial?: string;
  role: "core" | "distribution" | "access" | "perimeter" | "management" | "unknown";
  exposure: DeviceExposure;
  compliance_score: number; // e.g. 0.78
  coverage_score: number; // e.g. 0.92 (First-class column)
  meaningful_ratio?: number;
  security_score?: number;
  critical_findings_count: number;
  high_findings_count: number;
  status_annotations: Array<"terse" | "local_rulepack" | "missing" | "external">;
  rulepack_id: string;
  rulepack_trust_tier: TrustTierType;
}

export interface FixFirstItem {
  rank: number;
  action: string;
  commandCount: number;
  impact: "safe" | "svc_affecting" | "lockout_risk";
  findingId: string;
}

export interface UnauditedCapabilityItem {
  path: string;
  port: number;
  properties: string[];
  controls_contaminated: number;
  description: string;
}

export interface DeviceDetailModel {
  id: string;
  hostname: string;
  hardware_model: string;
  platform: string;
  os_version: string;
  serial: string;
  role: string;
  exposure: DeviceExposure;
  rulepack_id: string;
  rulepack_version: string;
  rulepack_trust_tier: TrustTierType;
  scores: {
    compliance: number;
    coverage: number;
    meaningful_ratio: number;
    security: number;
  };
  counts: {
    findings: number;
    passing: number;
    unknown: number;
    not_applicable: number;
  };
  fix_first: FixFirstItem[];
  unaudited_capabilities: UnauditedCapabilityItem[];
}
