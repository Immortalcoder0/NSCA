import React, { useState } from "react";
import { X, Key, Lock } from "lucide-react";

interface CredentialCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { alias: string; target_type: "ssh_key" | "snmpv3" | "api_token"; username: string }) => void;
}

export const CredentialCreateModal: React.FC<CredentialCreateModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
}) => {
  const [alias, setAlias] = useState("");
  const [targetType, setTargetType] = useState<"ssh_key" | "snmpv3" | "api_token">("ssh_key");
  const [username, setUsername] = useState("");
  const [secretMaterial, setSecretMaterial] = useState("");

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      alias,
      target_type: targetType,
      username,
    });
    // Wipe local state immediately
    setSecretMaterial("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-md rounded-xl border border-border bg-card shadow-2xl p-6 space-y-5 my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-2 text-foreground">
            <Key size={18} className="text-primary" />
            <h2 className="text-base font-bold">Register Collection Credential Profile</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <X size={18} />
          </button>
        </div>

        {/* Zero-Read Security Notice */}
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 text-xs text-emerald-900 dark:text-emerald-200 flex items-start gap-2">
          <Lock size={15} className="text-emerald-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold block">Write-Only Credential Vault (NFR-SEC-003)</span>
            <p className="text-[11px] text-emerald-800 dark:text-emerald-300 leading-relaxed mt-0.5">
              Secret keys and passwords are encrypted immediately upon submission. No API endpoint or UI view will ever display stored secret material.
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div className="space-y-1.5">
            <label htmlFor="cred-alias" className="font-semibold text-foreground">
              Profile Alias / Identifier *
            </label>
            <input
              id="cred-alias"
              type="text"
              required
              placeholder="e.g. Core-IOSXE-ReadOnly-Vault"
              value={alias}
              onChange={(e) => setAlias(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="target-type" className="font-semibold text-foreground">
              Authentication Protocol Tier *
            </label>
            <select
              id="target-type"
              value={targetType}
              onChange={(e) => setTargetType(e.target.value as any)}
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="ssh_key">SSH Private Key (Read-Only Diagnostics)</option>
              <option value="snmpv3">SNMPv3 AuthPriv Profile</option>
              <option value="api_token">HTTPS RESTCONF / XML API Token</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="service-user" className="font-semibold text-foreground">
              Service Account Username *
            </label>
            <input
              id="service-user"
              type="text"
              required
              placeholder="nsca-readonly-svc"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="secret-input" className="font-semibold text-foreground">
              Secret Passphrase / Private Key Material *
            </label>
            <textarea
              id="secret-input"
              rows={3}
              required
              placeholder="Paste encrypted PEM key or diagnostic service password..."
              value={secretMaterial}
              onChange={(e) => setSecretMaterial(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-input bg-background font-mono text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

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
              className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 transition-opacity"
            >
              <Lock size={13} />
              <span>Store Write-Only Credential</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
