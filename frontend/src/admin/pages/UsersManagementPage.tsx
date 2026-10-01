import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Check, Loader2, AlertTriangle, UserPlus } from "lucide-react";
import { useAdminUsers, useAdminRoles, useCreateAdminUser } from "../../shared/api/hooks";
import { ApiError } from "../../shared/api/client";

export const UsersManagementPage: React.FC = () => {
  const usersQuery = useAdminUsers();
  const rolesQuery = useAdminRoles();
  const createUser = useCreateAdminUser();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");

  const is403 = usersQuery.error instanceof ApiError && usersQuery.error.status === 403;

  const roles = rolesQuery.data?.items ?? [];

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !role) return;
    createUser.mutate({ name, email, role });
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/admin" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Administration</span>
        </Link>
        <span>/</span>
        <span className="font-semibold text-foreground">Users & Role Assignments</span>
      </div>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">User Accounts & RBAC Profiles</h1>
        <p className="text-xs text-muted-foreground mt-1">
          Configure authorization roles across five functional tiers (FR-ADM-002).
        </p>
      </div>

      <div className="p-3 rounded-lg border border-sky-300 dark:border-sky-800 bg-sky-50/60 dark:bg-sky-950/30 text-[11px] text-sky-900 dark:text-sky-300">
        <code>GET/POST /admin/users</code> are still M0 stubs on the live server — the list always shows the one
        hardcoded dev user, and there is no endpoint to change an existing user's role (only
        <code> GET /admin/roles</code> is real, derived from the platform's actual <code>Role</code> enum). The
        role column below is read-only for that reason rather than pretending an edit persists.
      </div>

      {/* Users Table */}
      <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3 text-xs">
        {usersQuery.isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground p-4 justify-center">
            <Loader2 size={14} className="animate-spin" />
            <span>Loading users…</span>
          </div>
        )}

        {is403 && (
          <div className="p-3 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300 flex items-center gap-2">
            <AlertTriangle size={14} className="shrink-0" />
            <span>Platform Administrator role required to list users. Switch your dev role and reload.</span>
          </div>
        )}

        {usersQuery.data && (
          <div className="rounded-lg border overflow-hidden bg-background">
            <table className="w-full text-left">
              <thead className="bg-muted/60 text-muted-foreground font-semibold border-b">
                <tr>
                  <th className="p-3">Name</th>
                  <th className="p-3">Email Address</th>
                  <th className="p-3">Assigned Role Profile</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {usersQuery.data.items.map((u) => (
                  <tr key={u.id} className="hover:bg-muted/30">
                    <td className="p-3 font-mono font-bold text-foreground">{u.name}</td>
                    <td className="p-3 text-muted-foreground font-mono">{u.email}</td>
                    <td className="p-3">
                      <span className="px-2.5 py-1 rounded-md border border-input bg-muted font-mono text-xs font-semibold">
                        {u.role}
                      </span>
                    </td>
                    <td className="p-3">
                      <span className="inline-flex items-center gap-1 font-semibold text-emerald-600">
                        <Check size={13} />
                        Active
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create user (real POST /admin/users — echoes the submitted body, does not persist across requests) */}
      <form onSubmit={handleCreate} className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3 text-xs">
        <span className="font-bold text-sm text-foreground flex items-center gap-2">
          <UserPlus size={16} className="text-primary" />
          <span>Register a new user (POST /admin/users)</span>
        </span>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <input
            placeholder="Full name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="px-2.5 py-1.5 rounded-md border border-input bg-background text-xs"
          />
          <input
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="px-2.5 py-1.5 rounded-md border border-input bg-background text-xs"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="px-2.5 py-1.5 rounded-md border border-input bg-background font-mono text-xs"
          >
            <option value="">Select role…</option>
            {roles.map((r) => (
              <option key={r.key} value={r.name}>
                {r.name}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          disabled={!name || !email || !role || createUser.isPending}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {createUser.isPending && <Loader2 size={14} className="animate-spin" />}
          <span>Create</span>
        </button>
        {createUser.isSuccess && (
          <p className="text-emerald-600 dark:text-emerald-400">
            Server accepted the request (id: {String(createUser.data.id)}) — note this M0 stub does not persist
            across requests, so it won't appear in the list above on reload.
          </p>
        )}
      </form>
    </div>
  );
};
