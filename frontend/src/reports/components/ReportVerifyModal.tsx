import React from "react";
import { X, CheckCircle2, AlertTriangle, ShieldAlert, Cpu, RefreshCw, HelpCircle } from "lucide-react";
import { useVerifyReport } from "../../shared/api/hooks";

interface ReportVerifyModalProps {
  isOpen: boolean;
  reportId?: string;
  onClose: () => void;
}

/** Real three(+one)-outcome rendering for `POST /reports/{id}/verify`
 * (services/report_service.py:verify_report). The real endpoint returns
 * `{ result: "MATCH"|"MISMATCH"|"UNVERIFIABLE", original_hash,
 * recomputed_hash, knowledge_base_identical }` — `knowledge_base_identical`
 * is hardcoded `True` in the current backend implementation whenever a
 * result is computable (report_service.py never actually diffs knowledge
 * base pins yet), so a real MISMATCH today will always render as the
 * defect case below, not the "differing knowledge base" case. That is a
 * real backend limitation, flagged rather than hidden: this component
 * trusts whatever `knowledge_base_identical` the server reports instead of
 * re-deriving it, so it will render correctly the moment the backend
 * starts computing it for real. `UNVERIFIABLE` (missing campaign/device
 * rows) is a fourth, real outcome the original 3-outcome design didn't
 * anticipate — rendered as its own state rather than forced into MISMATCH. */
export const ReportVerifyModal: React.FC<ReportVerifyModalProps> = ({ isOpen, reportId, onClose }) => {
  const verify = useVerifyReport();

  if (!isOpen) return null;

  const handleVerify = () => {
    if (!reportId) return;
    verify.mutate(reportId);
  };

  const result = verify.data;
  const isDefect = result?.result === "MISMATCH" && result.knowledge_base_identical === true;
  const isDiffKb = result?.result === "MISMATCH" && result.knowledge_base_identical === false;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-lg rounded-xl border border-border bg-card shadow-2xl p-6 space-y-5 my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-2 text-foreground">
            <Cpu size={20} className="text-primary" />
            <h2 className="text-base font-bold">Cryptographic Report Verification</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <X size={18} />
          </button>
        </div>

        <p className="text-[11px] text-muted-foreground font-mono">
          Report: <span className="font-bold text-foreground">{reportId || "(none)"}</span>
        </p>

        {verify.isPending ? (
          <div className="p-8 text-center space-y-2">
            <RefreshCw size={24} className="animate-spin text-primary mx-auto" />
            <p className="text-xs text-muted-foreground">Re-executing the report render and comparing hashes…</p>
          </div>
        ) : verify.isError ? (
          <div className="p-4 rounded-xl border border-red-300 bg-red-50/80 dark:bg-red-950/40 dark:border-red-800 text-xs text-red-800 dark:text-red-300">
            {verify.error instanceof Error ? verify.error.message : "Verification request failed."}
          </div>
        ) : !result ? (
          <div className="p-6 text-center text-xs text-muted-foreground">
            Not yet verified this session. Click "Verify Now" to re-execute and compare hashes against the live
            server.
          </div>
        ) : (
          <div className="space-y-4 text-xs">
            {/* Outcome 1: MATCH */}
            {result.result === "MATCH" && (
              <div className="p-4 rounded-xl border border-emerald-300 bg-emerald-50/80 dark:bg-emerald-950/40 dark:border-emerald-800 space-y-2 text-emerald-950 dark:text-emerald-200">
                <div className="flex items-center gap-2 font-bold text-sm text-emerald-900 dark:text-emerald-100">
                  <CheckCircle2 size={18} className="text-emerald-600" />
                  <span>VERIFICATION SUCCESSFUL (MATCH)</span>
                </div>
                <p className="text-[11px] text-emerald-800 dark:text-emerald-300">
                  Re-executed calculation produced a byte-identical SHA256 digest matching the sealed document hash.
                </p>
                <div className="font-mono text-[10px] bg-background/80 p-2.5 rounded border border-emerald-200 dark:border-emerald-900 text-foreground break-all">
                  SHA256: {result.original_hash} (MATCHED)
                </div>
              </div>
            )}

            {/* Outcome 2: MISMATCH, differing knowledge base */}
            {isDiffKb && (
              <div className="p-4 rounded-xl border border-amber-300 bg-amber-50/80 dark:bg-amber-950/40 dark:border-amber-800 space-y-2 text-amber-950 dark:text-amber-200">
                <div className="flex items-center gap-2 font-bold text-sm text-amber-900 dark:text-amber-100">
                  <AlertTriangle size={18} className="text-amber-600" />
                  <span>CONTENT DRIFT: DIFFERING KNOWLEDGE BASE</span>
                </div>
                <p className="text-[11px] text-amber-800 dark:text-amber-300">
                  Calculation differed because the active engine/knowledge base pin differs from what was sealed
                  into this report.
                </p>
              </div>
            )}

            {/* Outcome 3: MISMATCH, identical knowledge base (DEFECT) */}
            {isDefect && (
              <div className="p-4 rounded-xl border-2 border-red-500 bg-red-100/90 dark:bg-red-950/80 dark:border-red-600 space-y-3 text-red-950 dark:text-red-100 shadow-lg animate-pulse">
                <div className="flex items-center gap-2 font-black text-sm text-red-900 dark:text-red-100">
                  <ShieldAlert size={20} className="text-red-600" />
                  <span>CRITICAL AUDIT INTEGRITY DEFECT DETECTED</span>
                </div>
                <p className="text-xs font-medium text-red-900 dark:text-red-200 leading-relaxed">
                  Calculation produced a differing hash <strong>despite identical engine and rulepack versions</strong>. This indicates non-deterministic AST evaluation or a code defect in the engine.
                </p>
                <div className="font-mono text-[10px] bg-background p-2.5 rounded border border-red-400 text-red-800 dark:text-red-300 break-all">
                  Expected: {result.original_hash} | Recomputed: {result.recomputed_hash} (DEFECT)
                </div>
              </div>
            )}

            {/* Outcome 4: UNVERIFIABLE — real, not in the original 3-outcome design */}
            {result.result === "UNVERIFIABLE" && (
              <div className="p-4 rounded-xl border border-slate-300 bg-slate-50/80 dark:bg-slate-900/40 dark:border-slate-700 space-y-2 text-slate-900 dark:text-slate-200">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <HelpCircle size={18} className="text-slate-600" />
                  <span>UNVERIFIABLE</span>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  The campaign or device this report was generated from could no longer be found — the server
                  cannot re-gather the same data to recompute a hash.
                </p>
              </div>
            )}
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t">
          <button
            onClick={handleVerify}
            disabled={!reportId || verify.isPending}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
          >
            <RefreshCw size={12} className={verify.isPending ? "animate-spin" : ""} />
            <span>{result ? "Re-verify Now" : "Verify Now"}</span>
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-md bg-secondary border border-border text-xs font-semibold hover:bg-secondary/80 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
