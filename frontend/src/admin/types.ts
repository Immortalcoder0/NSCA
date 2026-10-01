import type { UserRole } from "../shared/types/domain";

export interface UserAccountModel {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  created_at: string;
  active: boolean;
}

export interface CredentialProfileModel {
  id: string;
  alias: string;
  // The real `GET/POST /admin/credentials` only ever returns
  // `{id, label, type}` — widened to `string` (rather than the create
  // modal's narrower "ssh_key"|"snmpv3"|"api_token" union) so a real value
  // like "ssh_keypair" displays honestly instead of being coerced.
  target_type: string;
  username?: string;
  created_by?: string;
  created_at?: string;
  last_used?: string;
  // Intentionally NO password, private_key, or secret fields exist here (NFR-SEC-003)
}

export interface SystemFreshnessModel {
  engine_version: string;
  platform_health: "HEALTHY" | "DEGRADED" | "CRITICAL";
  vulnerability_db_date: string;
  vulnerability_db_staleness_text: string; // e.g. "43 days old" per 11-audit-integrity.md §13.3
  rulepack_freshness_status: "UP_TO_DATE" | "UPDATES_AVAILABLE";
  active_campaigns_count: number;
}

export interface AuditChainEntry {
  sequence: number;
  timestamp: string;
  action: string;
  actor: string;
  details: string;
  previous_hash: string;
  entry_hash: string;
}

export interface AuditChainVerificationResult {
  entries_checked: number;
  chain_intact: boolean;
  first_break_sequence: number | null;
  verified_at: string;
}
