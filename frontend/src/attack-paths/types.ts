import type { SeverityType } from "../shared/theme/tokens";

export interface AttackPathNodeModel {
  id: string;
  hostname: string;
  ip: string;
  role: string;
  zone: string;
  is_entry?: boolean;
  is_target?: boolean;
}

export interface AttackPathLinkModel {
  id: string;
  source: string; // node id
  target: string; // node id
  contributing_finding_id: string;
  control_id: string;
  finding_title: string;
  severity: SeverityType;
  protocol?: string;
  port?: number;
}

export interface AttackPathModel {
  id: string;
  name: string;
  entry_point: string;
  target_asset: string;
  criticality: "CRITICAL" | "HIGH" | "MEDIUM";
  length: number;
  nodes: AttackPathNodeModel[];
  links: AttackPathLinkModel[];
  payoff: {
    critical_links_count: number;
    recommended_break_finding_id: string;
    recommended_break_device: string;
    unreachable_findings_count: number;
    cost_estimate: string;
  };
}
