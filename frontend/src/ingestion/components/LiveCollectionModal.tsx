import React, { useState } from "react";
import { X, ShieldAlert, DownloadCloud, Lock, Server } from "lucide-react";

interface LiveCollectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStartCollection: (data: {
    targets: Array<{ host: string; credential_ref: string }>;
    artifacts: string[];
    mode: "read_only";
  }) => void;
}

const STORED_CREDENTIALS = [
  { id: "cred-vault-core-01", label: "Core Infrastructure SSH Key (Read-Only Service Account)" },
  { id: "cred-vault-edge-02", label: "Perimeter Firewalls API Token (Monitor Profile)" },
  { id: "cred-vault-access-03", label: "Branch Access SNMPv3 / SSH Read-Only" },
];

export const LiveCollectionModal: React.FC<LiveCollectionModalProps> = ({
  isOpen,
  onClose,
  onStartCollection,
}) => {
  const [hostsText, setHostsText] = useState("10.250.0.1\n10.250.0.2\n10.40.1.1\n10.40.1.2");
  const [selectedCred, setSelectedCred] = useState(STORED_CREDENTIALS[0].id);
  const [includeShowTech, setIncludeShowTech] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const hostList = hostsText
      .split(/\r?\n/)
      .map((h) => h.trim())
      .filter(Boolean);

    const targets = hostList.map((host) => ({
      host,
      credential_ref: selectedCred,
    }));

    const artifacts = ["running-config", "show-version", "show-inventory"];
    if (includeShowTech) artifacts.push("show-tech-support");

    onStartCollection({
      targets,
      artifacts,
      mode: "read_only", // Hardcoded per Guarantee G4 / TECH-STACK.md §4
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-xl rounded-xl border border-border bg-card shadow-2xl p-6 space-y-5 my-8">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-2">
            <DownloadCloud size={20} className="text-primary" />
            <h2 className="text-lg font-bold">Live Network Device Collection</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <X size={18} />
          </button>
        </div>

        {/* Read-Only Guarantee Notice */}
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 text-xs text-emerald-900 dark:text-emerald-200 flex items-start gap-2.5">
          <Lock size={16} className="text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-bold block">Guarantee G4: Strictly Read-Only Transport</span>
            <p className="text-[11px] text-emerald-800 dark:text-emerald-300 leading-relaxed">
              No configuration changes or mutating commands can be executed. Collection drivers only invoke immutable diagnostic commands (show running-config, show version, show inventory).
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div className="space-y-1.5">
            <label htmlFor="target-hosts" className="font-semibold text-foreground flex items-center gap-1">
              <Server size={13} className="text-muted-foreground" />
              <span>Target Device IP Addresses / Hostnames (One per line)</span>
            </label>
            <textarea
              id="target-hosts"
              rows={4}
              required
              value={hostsText}
              onChange={(e) => setHostsText(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-input bg-background font-mono text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="cred-select" className="font-semibold text-foreground flex items-center gap-1">
              <ShieldAlert size={13} className="text-muted-foreground" />
              <span>Vault Credential Profile</span>
            </label>
            <select
              id="cred-select"
              value={selectedCred}
              onChange={(e) => setSelectedCred(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {STORED_CREDENTIALS.map((cred) => (
                <option key={cred.id} value={cred.id}>
                  {cred.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2 pt-2 border-t">
            <input
              id="show-tech"
              type="checkbox"
              checked={includeShowTech}
              onChange={(e) => setIncludeShowTech(e.target.checked)}
              className="rounded border-border cursor-pointer"
            />
            <label htmlFor="show-tech" className="font-medium text-foreground cursor-pointer">
              Collect Show-Tech Diagnostic Bundle (Verbose mode)
            </label>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-md border border-border text-xs font-medium hover:bg-secondary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 transition-opacity"
            >
              <DownloadCloud size={14} />
              <span>Dispatch Read-Only Collector</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
