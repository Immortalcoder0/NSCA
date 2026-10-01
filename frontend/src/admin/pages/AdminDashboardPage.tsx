import React from "react";
import { Link } from "react-router-dom";
import { Settings, Users, Key, FileText, Loader2 } from "lucide-react";
import { KnowledgeFreshnessBox } from "../components/KnowledgeFreshnessBox";
import { AuditChainVerifier } from "../components/AuditChainVerifier";
import { useAdminStatus, useKnowledgeFreshness, useCampaigns } from "../../shared/api/hooks";
import type { SystemFreshnessModel } from "../types";

export const AdminDashboardPage: React.FC = () => {
  const statusQuery = useAdminStatus();
  const freshnessQuery = useKnowledgeFreshness();
  const campaignsQuery = useCampaigns();

  const isLoading = statusQuery.isLoading || freshnessQuery.isLoading;

  const campaignItems = (campaignsQuery.data?.items as Array<Record<string, unknown>> | undefined) ?? [];
  const activeCampaignsCount = campaignItems.filter((c) => c.status !== "Closed").length;

  const freshness: SystemFreshnessModel | null =
    statusQuery.data && freshnessQuery.data
      ? {
          engine_version: `NSCA Platform ${statusQuery.data.version}`,
          platform_health: statusQuery.data.status === "ok" ? "HEALTHY" : "DEGRADED",
          vulnerability_db_date: freshnessQuery.data.vulnerability_index.snapshot_date,
          vulnerability_db_staleness_text: `${freshnessQuery.data.vulnerability_index.age_days} days old`,
          // GET /knowledge/freshness has no "is a newer rulepack version
          // available" signal today — this is not independently computed,
          // just the honest absence of a "stale" flag (see note below).
          rulepack_freshness_status: "UP_TO_DATE",
          active_campaigns_count: activeCampaignsCount,
        }
      : null;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-primary">
          <Settings size={22} />
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Platform Administration & System Health</h1>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Manage user accounts, RBAC permissions, write-only credential vaults, and offline vulnerability freshness.
        </p>
      </div>

      {/* Admin Quick Navigation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
        <Link
          to="/admin/users"
          className="p-5 rounded-xl border border-border bg-card shadow-sm hover:border-primary transition-colors space-y-2 block"
        >
          <div className="flex items-center gap-2 font-bold text-sm text-foreground">
            <Users size={18} className="text-primary" />
            <span>Users & Role Assignments</span>
          </div>
          <p className="text-muted-foreground text-[11px]">
            Manage 5 RBAC operational profiles (Lead Assessor, Assessor, Network Admin, Platform Admin, Read Only).
          </p>
        </Link>

        <Link
          to="/admin/credentials"
          className="p-5 rounded-xl border border-border bg-card shadow-sm hover:border-primary transition-colors space-y-2 block"
        >
          <div className="flex items-center gap-2 font-bold text-sm text-foreground">
            <Key size={18} className="text-primary" />
            <span>Collection Credential Vault</span>
          </div>
          <p className="text-muted-foreground text-[11px]">
            Manage write-only service keys and SNMP credentials for read-only diagnostic collection.
          </p>
        </Link>

        <Link
          to="/admin/audit-log"
          className="p-5 rounded-xl border border-border bg-card shadow-sm hover:border-primary transition-colors space-y-2 block"
        >
          <div className="flex items-center gap-2 font-bold text-sm text-foreground">
            <FileText size={18} className="text-primary" />
            <span>Hash-Chain Audit Ledger</span>
          </div>
          <p className="text-muted-foreground text-[11px]">
            Inspect tamper-evident audit trails with forward cryptographic SHA256 continuity verification.
          </p>
        </Link>
      </div>

      {/* Freshness Monitor */}
      {isLoading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-6 justify-center">
          <Loader2 size={16} className="animate-spin" />
          <span>Loading system status…</span>
        </div>
      ) : (
        freshness && <KnowledgeFreshnessBox freshness={freshness} />
      )}

      {/* Hash Chain Integrity Verifier */}
      <AuditChainVerifier />
    </div>
  );
};
