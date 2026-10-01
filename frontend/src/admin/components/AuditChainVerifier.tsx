import React from "react";
import { CheckCircle2, XCircle, ShieldCheck, RefreshCw, AlertTriangle } from "lucide-react";
import { useVerifyAuditLog } from "../../shared/api/hooks";
import { ApiError } from "../../shared/api/client";
import { cn } from "../../shared/lib/utils";

interface AuditChainVerifierProps {
  onVerify?: () => void;
  className?: string;
}

/** Real hash-chain verification — `GET /admin/audit-log/verify`
 * (audit/log.py:verify_chain, Platform Administrator only). Renders the
 * actual `entries_checked` / `chain_intact` / `first_break` response;
 * there is no result until the user actually triggers a verification —
 * this used to render a canned "1420 sequential records / 100% INTACT"
 * result on mount, which was a mock artifact, not a real initial state. */
export const AuditChainVerifier: React.FC<AuditChainVerifierProps> = ({ onVerify, className }) => {
  const verify = useVerifyAuditLog();

  const handleVerify = () => {
    verify.mutate(undefined, { onSuccess: () => onVerify?.() });
  };

  const is403 = verify.error instanceof ApiError && verify.error.status === 403;
  const result = verify.data;

  return (
    <div
      className={cn(
        "p-5 rounded-xl border border-border bg-card shadow-sm space-y-4 select-none text-xs",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <ShieldCheck size={18} className="text-primary" />
            <h3 className="font-bold text-sm text-foreground">
              Tamper-Evident Hash-Chain Ledger Verification
            </h3>
          </div>
          <p className="text-muted-foreground text-[11px]">
            Verifies forward SHA256 integrity across all logged audit events.
          </p>
        </div>

        <button
          onClick={handleVerify}
          disabled={verify.isPending}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-secondary border border-border text-foreground font-semibold hover:bg-secondary/80 transition-colors self-start sm:self-center disabled:opacity-60"
        >
          <RefreshCw size={13} className={cn(verify.isPending && "animate-spin text-primary")} />
          <span>{verify.isPending ? "Verifying Chain…" : "Verify Hash Continuity"}</span>
        </button>
      </div>

      {is403 && (
        <div className="p-3 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300 flex items-center gap-2">
          <AlertTriangle size={14} className="shrink-0" />
          <span>Platform Administrator role required. Switch your dev role and try again.</span>
        </div>
      )}
      {verify.isError && !is403 && (
        <div className="p-3 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-red-800 dark:text-red-300 flex items-center gap-2">
          <AlertTriangle size={14} className="shrink-0" />
          <span>{verify.error instanceof Error ? verify.error.message : "Verification failed."}</span>
        </div>
      )}

      {!result && !verify.isError && !verify.isPending && (
        <p className="text-muted-foreground">Not yet verified this session.</p>
      )}

      {result && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div
            className={cn(
              "p-3 rounded-lg space-y-0.5 border",
              result.chain_intact
                ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-800"
                : "bg-red-50 dark:bg-red-950/40 border-red-300 dark:border-red-800"
            )}
          >
            <span
              className={cn(
                "text-[10px] uppercase font-semibold block",
                result.chain_intact ? "text-emerald-800 dark:text-emerald-300" : "text-red-800 dark:text-red-300"
              )}
            >
              Chain Continuity Status
            </span>
            <span
              className={cn(
                "font-bold text-base flex items-center gap-1",
                result.chain_intact ? "text-emerald-900 dark:text-emerald-100" : "text-red-900 dark:text-red-100"
              )}
            >
              {result.chain_intact ? <CheckCircle2 size={15} /> : <XCircle size={15} />}
              <span>{result.chain_intact ? "100% INTACT" : `BROKEN AT ${result.first_break}`}</span>
            </span>
          </div>

          <div className="p-3 rounded-lg bg-secondary/50 space-y-0.5">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
              Entries Verified
            </span>
            <span className="font-mono font-bold text-base text-foreground block">
              {result.entries_checked} sequential records
            </span>
          </div>

          <div className="p-3 rounded-lg bg-secondary/50 space-y-0.5">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
              Last Verifier Check
            </span>
            <span className="font-mono text-foreground block">{new Date().toLocaleTimeString()}</span>
          </div>
        </div>
      )}
    </div>
  );
};
