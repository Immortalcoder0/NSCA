import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, AlertTriangle } from "lucide-react";
import { AuditChainVerifier } from "../components/AuditChainVerifier";
import { useAuditLog } from "../../shared/api/hooks";

export const AuditLogViewerPage: React.FC = () => {
  const logQuery = useAuditLog();
  const logs = logQuery.data?.items ?? [];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/admin" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Administration</span>
        </Link>
        <span>/</span>
        <span className="font-semibold text-foreground">Hash-Chain Audit Log Viewer</span>
      </div>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Tamper-Evident Hash-Chain Audit Ledger
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Cryptographically linked event ledger verifying immutability and non-repudiation across all audit actions.
        </p>
      </div>

      {/* Hash Continuity Verifier — real GET /admin/audit-log/verify */}
      <AuditChainVerifier />

      <div className="p-3 rounded-lg border border-sky-300 dark:border-sky-800 bg-sky-50/60 dark:bg-sky-950/30 text-[11px] text-sky-900 dark:text-sky-300">
        <code>GET /admin/audit-log</code> (the list below) is still an M0 stub — it always returns the same single
        example entry, unlike the verify action above, which walks the real audit_log_entry table.
      </div>

      {/* Audit Log Table */}
      <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3 text-xs">
        {logQuery.isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground p-4 justify-center">
            <Loader2 size={14} className="animate-spin" />
            <span>Loading audit log…</span>
          </div>
        )}
        {logQuery.isError && (
          <div className="p-3 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-red-800 dark:text-red-300 flex items-center gap-2">
            <AlertTriangle size={14} className="shrink-0" />
            <span>Failed to load the audit log.</span>
          </div>
        )}
        <div className="rounded-lg border overflow-hidden bg-background">
          <table className="w-full text-left">
            <thead className="bg-muted/60 text-muted-foreground font-semibold border-b">
              <tr>
                <th className="p-3">Seq #</th>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Action</th>
                <th className="p-3">Actor</th>
                <th className="p-3">Target</th>
                <th className="p-3">Block SHA256 Digest</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-muted/30">
                  <td className="p-3 font-mono font-bold text-foreground">#{log.id}</td>
                  <td className="p-3 font-mono text-muted-foreground text-[11px]">{log.at}</td>
                  <td className="p-3 font-mono font-semibold text-primary">{log.action}</td>
                  <td className="p-3 font-medium text-foreground">{log.actor}</td>
                  <td className="p-3 text-foreground font-mono text-[11px]">{log.target}</td>
                  <td className="p-3 font-mono text-muted-foreground text-[10px]">{log.hash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
