import React, { useState } from "react";
import { X, ShieldAlert, Calendar, AlertCircle } from "lucide-react";
import { RequireRole } from "../../app/auth-guard";
import type { RiskAcceptanceSubmission } from "../types";

interface RiskAcceptanceModalProps {
  isOpen: boolean;
  findingId: string;
  onClose: () => void;
  onSubmit: (data: RiskAcceptanceSubmission) => void;
}

// Backend contract (nsca_platform/api/findings.py RiskAcceptanceRequest):
// expires_at is a required date (FR-FND-008) and must be strictly in the
// future (`no_backdated_expiry` model_validator) — "no indefinite
// acceptance" is read as "no acceptance that's already meaningless."
// justification has Field(min_length=20). Mirrored here so the 422 is
// never the first time a Lead Assessor learns about either rule.
const MIN_JUSTIFICATION_LENGTH = 20;

function tomorrowIsoDate(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

export const RiskAcceptanceModal: React.FC<RiskAcceptanceModalProps> = ({
  isOpen,
  findingId,
  onClose,
  onSubmit,
}) => {
  const minExpiryDate = tomorrowIsoDate();
  const [expiresAt, setExpiresAt] = useState("");
  const [justification, setJustification] = useState("");
  const [compensatingControl, setCompensatingControl] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!expiresAt) {
      setValidationError("Expiration date is mandatory. Findings cannot be accepted indefinitely.");
      return;
    }
    if (expiresAt <= new Date().toISOString().slice(0, 10)) {
      setValidationError("Expiration date must be in the future — a backdated or same-day expiry is as meaningless as no expiry at all.");
      return;
    }
    if (justification.trim().length < MIN_JUSTIFICATION_LENGTH) {
      setValidationError(`Justification rationale must be at least ${MIN_JUSTIFICATION_LENGTH} characters.`);
      return;
    }

    setValidationError(null);
    onSubmit({
      finding_id: findingId,
      expires_at: expiresAt,
      justification: justification.trim(),
      compensating_control: compensatingControl.trim() || undefined,
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-lg rounded-xl border border-border bg-card shadow-2xl p-6 space-y-5 my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-2 text-foreground">
            <ShieldAlert size={20} className="text-amber-500" />
            <h2 className="text-base font-bold">Formal Risk Acceptance & Exemption</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <X size={18} />
          </button>
        </div>

        {/* Lead Assessor Role Check */}
        <RequireRole
          roles={["lead_assessor"]}
          fallback={
            <div className="p-4 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-xs text-amber-900 dark:text-amber-200">
              <span className="font-bold block">Access Restricted: Lead Assessor Required</span>
              <p className="mt-1">
                Only a designated Lead Assessor holds the authority to accept organizational risk and grant audit exemptions (FR-ADM-003). Switch dev role to `lead_assessor` in the top switcher.
              </p>
            </div>
          }
        >
          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            <div className="p-2.5 rounded bg-muted/60 text-muted-foreground border">
              Accepting finding <strong className="font-mono text-foreground font-bold">{findingId}</strong>. This state creates a time-bounded exception in the compliance ledger.
            </div>

            {validationError && (
              <div className="p-2.5 rounded bg-red-50 dark:bg-red-950/40 border border-red-300 dark:border-red-800 text-xs text-red-700 dark:text-red-300 flex items-center gap-2">
                <AlertCircle size={14} className="shrink-0" />
                <span>{validationError}</span>
              </div>
            )}

            {/* Mandatory Expiration Date */}
            <div className="space-y-1.5">
              <label htmlFor="expires-at" className="font-semibold text-foreground flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Calendar size={13} className="text-amber-500" />
                  <span>Mandatory Expiration Date (expires_at) *</span>
                </span>
                <span className="text-[10px] text-amber-600 font-mono font-bold">REQUIRED</span>
              </label>
              <input
                id="expires-at"
                type="date"
                required
                min={minExpiryDate}
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-input bg-background font-mono text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <p className="text-[11px] text-muted-foreground">
                Per NSCA policy, omitting `expires_at` is forbidden to prevent permanent finding obsolescence. Must be a future date — indefinite or backdated acceptance is rejected by the API (422).
              </p>
            </div>

            {/* Rationale & Justification */}
            <div className="space-y-1.5">
              <label htmlFor="justification" className="font-semibold text-foreground block">
                Business & Technical Justification *
              </label>
              <textarea
                id="justification"
                rows={3}
                required
                placeholder="Document operational necessity, business context, or pending migration schedule..."
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            {/* Compensating Control Reference */}
            <div className="space-y-1.5">
              <label htmlFor="compensating" className="font-semibold text-foreground block">
                Compensating Control Reference (Optional)
              </label>
              <input
                id="compensating"
                type="text"
                placeholder="e.g. Edge firewall rate-limiting, bastion isolation, or IPS profile"
                value={compensatingControl}
                onChange={(e) => setCompensatingControl(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-3 border-t">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs transition-colors shadow-sm"
              >
                <ShieldAlert size={14} />
                <span>Ratify Risk Acceptance</span>
              </button>
            </div>
          </form>
        </RequireRole>
      </div>
    </div>
  );
};
