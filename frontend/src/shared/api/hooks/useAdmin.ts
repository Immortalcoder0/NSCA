import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../client";

// See useCampaigns.ts's note on unstructured JSON dicts. Honesty note
// specific to this file (flagged in the M6 integration report): most of
// `nsca_platform/api/admin.py` is still an M0 stub — `GET /admin/users`,
// `GET/POST /admin/credentials`, `GET /admin/audit-log` (the list, not the
// verify action), and `GET /admin/status` all return hardcoded literal
// responses regardless of real DB state (`POST` variants echo back what
// was submitted but don't persist it — a second `GET` still shows the
// original single hardcoded item). The two genuinely real, DB-backed
// routes are `GET /admin/roles` (derived from the real `Role` enum) and
// `GET /admin/audit-log/verify` (real hash-chain walk via
// `audit.log.verify_chain`) — the one this track's plan calls out by name
// as worth exercising live. Every hook below still calls the real HTTP
// route; this comment is about what the *backend* currently computes.

export const ADMIN_KEY = ["admin"] as const;

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: string;
}

export function useAdminUsers() {
  return useQuery({
    queryKey: [...ADMIN_KEY, "users"],
    queryFn: () => apiClient.get<{ items: AdminUser[] }>("/admin/users"),
  });
}

export function useCreateAdminUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; email: string; role: string }) =>
      apiClient.post<AdminUser & { status: string }>("/admin/users", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...ADMIN_KEY, "users"] }),
  });
}

export interface AdminRole {
  key: string;
  name: string;
}

export function useAdminRoles() {
  return useQuery({
    queryKey: [...ADMIN_KEY, "roles"],
    queryFn: () => apiClient.get<{ items: AdminRole[] }>("/admin/roles"),
  });
}

export interface AdminCredential {
  id: string;
  label: string;
  type: string;
}

export function useAdminCredentials() {
  return useQuery({
    queryKey: [...ADMIN_KEY, "credentials"],
    queryFn: () => apiClient.get<{ items: AdminCredential[] }>("/admin/credentials"),
  });
}

export function useCreateAdminCredential() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { label: string; type: string; username?: string }) =>
      apiClient.post<AdminCredential>("/admin/credentials", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...ADMIN_KEY, "credentials"] }),
  });
}

export interface AuditLogEntry {
  id: number;
  actor: string;
  action: string;
  target: string;
  at: string;
  hash: string;
}

export function useAuditLog() {
  return useQuery({
    queryKey: [...ADMIN_KEY, "audit-log"],
    queryFn: () => apiClient.get<{ items: AuditLogEntry[]; next_cursor: string | null }>("/admin/audit-log"),
  });
}

export interface AuditLogVerifyResult {
  entries_checked: number;
  chain_intact: boolean;
  first_break: string | null;
}

/** Real hash-chain verification — `GET /admin/audit-log/verify`
 * (audit/log.py:verify_chain), walking every real `audit_log_entry` row's
 * `previous_entry_hash -> entry_hash` pointers. Modelled as a `useMutation`
 * even though the HTTP verb is GET, because this is a user-triggered
 * on-demand action (a "Verify Now" button), not data to load on mount. */
export function useVerifyAuditLog() {
  return useMutation({
    mutationFn: () => apiClient.get<AuditLogVerifyResult>("/admin/audit-log/verify"),
  });
}

export interface AdminStatus {
  status: string;
  db: string;
  job_queue: { pending: number; running: number };
  inference_container: string;
  version: string;
}

export function useAdminStatus() {
  return useQuery({
    queryKey: [...ADMIN_KEY, "status"],
    queryFn: () => apiClient.get<AdminStatus>("/admin/status"),
  });
}
