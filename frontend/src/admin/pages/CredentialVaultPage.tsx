import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Key, Plus, Lock, Loader2, AlertTriangle } from "lucide-react";
import { CredentialCreateModal } from "../components/CredentialCreateModal";
import type { CredentialProfileModel } from "../types";
import { useAdminCredentials, useCreateAdminCredential } from "../../shared/api/hooks";
import { ApiError } from "../../shared/api/client";

interface CredentialVaultPageProps {
  // Test-only seam: lets tests exercise the render path with a deliberately
  // tampered payload (e.g. one where a compromised/misbehaving API response
  // echoes back secret material) without touching production wiring, which
  // always fetches from the real `GET /admin/credentials` when this prop is
  // omitted.
  initialCredentials?: CredentialProfileModel[];
}

export const CredentialVaultPage: React.FC<CredentialVaultPageProps> = ({ initialCredentials }) => {
  const credentialsQuery = useAdminCredentials();
  const createCredential = useCreateAdminCredential();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  // Locally-appended entries from a successful create this session — the
  // real `POST /admin/credentials` is still an M0 stub that doesn't persist
  // across requests (a subsequent `GET` won't include it), so this is the
  // only way a just-created credential is visible without lying about
  // real DB persistence.
  const [locallyAdded, setLocallyAdded] = useState<CredentialProfileModel[]>([]);

  const is403 = credentialsQuery.error instanceof ApiError && credentialsQuery.error.status === 403;

  const serverCredentials: CredentialProfileModel[] =
    initialCredentials ??
    (credentialsQuery.data?.items.map((c) => ({
      id: c.id,
      alias: c.label,
      target_type: c.type,
    })) ?? []);

  const credentials = initialCredentials ? serverCredentials : [...locallyAdded, ...serverCredentials];

  const handleCreate = (data: { alias: string; target_type: "ssh_key" | "snmpv3" | "api_token"; username: string }) => {
    createCredential.mutate(
      { label: data.alias, type: data.target_type, username: data.username },
      {
        onSuccess: (res) => {
          setLocallyAdded((prev) => [
            { id: res.id, alias: res.label, target_type: res.type, created_at: "just now", last_used: "Never" },
            ...prev,
          ]);
        },
      }
    );
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link to="/admin" className="hover:text-foreground flex items-center gap-1">
            <ArrowLeft size={13} />
            <span>Administration</span>
          </Link>
          <span>/</span>
          <span className="font-semibold text-foreground">Collection Credential Vault</span>
        </div>

        <button
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 transition-opacity shadow-sm"
        >
          <Plus size={14} />
          <span>New Credential Profile</span>
        </button>
      </div>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Write-Only Diagnostic Credential Profiles
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          Zero-read security model: secrets are encrypted upon entry and never returned to the UI (NFR-SEC-003).
        </p>
      </div>

      {!initialCredentials && (
        <div className="p-3 rounded-lg border border-sky-300 dark:border-sky-800 bg-sky-50/60 dark:bg-sky-950/30 text-[11px] text-sky-900 dark:text-sky-300">
          <code>GET/POST /admin/credentials</code> are still M0 stubs on the live server — the list always shows
          the one hardcoded example credential, and a created profile only persists for this browser session (see
          the locally-tracked rows above the server row).
        </div>
      )}

      {/* Credentials Table */}
      <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3 text-xs">
        {credentialsQuery.isLoading && !initialCredentials && (
          <div className="flex items-center gap-2 text-muted-foreground p-4 justify-center">
            <Loader2 size={14} className="animate-spin" />
            <span>Loading credential profiles…</span>
          </div>
        )}
        {is403 && (
          <div className="p-3 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300 flex items-center gap-2">
            <AlertTriangle size={14} className="shrink-0" />
            <span>Network Administrator role required. Switch your dev role and reload.</span>
          </div>
        )}

        <div className="rounded-lg border overflow-hidden bg-background">
          <table className="w-full text-left">
            <thead className="bg-muted/60 text-muted-foreground font-semibold border-b">
              <tr>
                <th className="p-3">Profile Alias</th>
                <th className="p-3">Protocol Tier</th>
                <th className="p-3">Service Username</th>
                <th className="p-3">Stored Secrets</th>
                <th className="p-3">Last Diagnostic Pull</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {credentials.map((c) => (
                <tr key={c.id} className="hover:bg-muted/30">
                  <td className="p-3 font-mono font-bold text-foreground flex items-center gap-1.5">
                    <Key size={13} className="text-primary" />
                    {c.alias}
                  </td>
                  <td className="p-3 uppercase font-mono text-[11px] text-muted-foreground">
                    {c.target_type.replace(/_/g, " ")}
                  </td>
                  <td className="p-3 font-mono text-foreground">{c.username ?? "—"}</td>
                  <td className="p-3">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-muted text-muted-foreground font-mono text-[10px]">
                      <Lock size={10} />
                      ENCRYPTED (WRITE-ONLY)
                    </span>
                  </td>
                  <td className="p-3 text-muted-foreground font-mono">{c.last_used || "Never"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal */}
      <CredentialCreateModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreate}
      />
    </div>
  );
};
