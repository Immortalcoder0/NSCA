import type { TrustTierType } from "../shared/theme/tokens";

export interface RulepackCoverageMetrics {
  // The real `GET /knowledge/rulepacks/{id}/coverage` endpoint
  // (nsca_platform/api/knowledge.py) reports control coverage
  // (controls_covered/controls_total/coverage_rate), not the corpus-line /
  // fact-count / test-fixture metrics this UI model originally mocked —
  // those richer per-extractor metrics aren't computed by this backend
  // milestone. Both shapes are optional here so RulepackCoverageReport can
  // render whichever real fields are actually available instead of
  // fabricating the rest.
  line_coverage?: number; // e.g. 0.984
  facts_producible_count?: number; // e.g. 142
  test_fixtures_count?: number; // e.g. 450
  unparsed_constructs_count?: number;
  controls_covered?: number;
  controls_total?: number;
  coverage_rate?: number;
  trust_tier?: string;
}

export interface RulepackModel {
  id: string;
  name: string;
  platform: string;
  version: string;
  trust_tier: TrustTierType;
  author: string;
  signature_valid: boolean;
  metrics: RulepackCoverageMetrics;
  last_updated: string;
}

export interface ManualOnlyControlItem {
  control_id: string;
  // The real `GET /knowledge/frameworks/{id}/coverage` endpoint's
  // `manual_only_items` only carries `{id, reason}` — framework_id/title/
  // recommended_manual_procedure aren't computed by this backend milestone,
  // so they're optional here rather than fabricated.
  framework_id?: string;
  title?: string;
  reason: string;
  recommended_manual_procedure?: string;
}

export interface AutomationCoverageManifestData {
  framework_name: string;
  version: string;
  total_controls: number;
  automated_count: number;
  manual_only_count: number;
  data_unavailable_count: number;
  not_implemented_count: number;
  manual_only_items: ManualOnlyControlItem[];
}

export interface FrameworkUpdateDiff {
  framework: string;
  current_version: string;
  available_version: string;
  // The real `POST /knowledge/frameworks/{id}/preview` response has no
  // release-date field — optional so it isn't fabricated.
  release_date?: string;
  added_controls_count: number;
  modified_controls_count: number;
  withdrawn_controls_count: number;
  estate_impact: {
    new_findings_predicted: number;
    severity_tightened_count: number;
    findings_auto_resolvable: number;
    net_compliance_delta: number;
    affected_devices?: number;
  };
}
