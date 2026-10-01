import React, { createContext, useContext, useState } from "react";
import type { UserRole, AuthUser } from "../shared/types/domain";
import { ROLE_LABELS } from "../shared/types/domain";

interface AuthContextType {
  user: AuthUser;
  role: UserRole;
  setRole: (role: UserRole) => void;
  hasRole: (allowedRoles: UserRole[]) => boolean;
}

const DEFAULT_DEV_ROLE: UserRole = "lead_assessor";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [role, setRoleState] = useState<UserRole>(() => {
    try {
      const stored = localStorage.getItem("nsca_dev_role");
      if (
        stored === "assessor" ||
        stored === "lead_assessor" ||
        stored === "network_administrator" ||
        stored === "platform_administrator" ||
        stored === "read_only"
      ) {
        return stored;
      }
    } catch {
      // ignore
    }
    return DEFAULT_DEV_ROLE;
  });

  const setRole = (newRole: UserRole) => {
    setRoleState(newRole);
    try {
      localStorage.setItem("nsca_dev_role", newRole);
    } catch {
      // ignore
    }
  };

  const user: AuthUser = {
    id: "dev-user-0001",
    name: "Dev Lead Assessor",
    email: "p.sharma@example.gov.in",
    role,
  };

  const hasRole = (allowedRoles: UserRole[]): boolean => {
    return allowedRoles.includes(role);
  };

  return (
    <AuthContext.Provider value={{ user, role, setRole, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export interface RequireRoleProps {
  roles: UserRole[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const RequireRole: React.FC<RequireRoleProps> = ({
  roles,
  children,
  fallback = null,
}) => {
  const { hasRole, role } = useAuth();

  if (!hasRole(roles)) {
    if (fallback) return <>{fallback}</>;
    return (
      <div
        role="alert"
        className="rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-950/40 dark:border-amber-800 p-4 text-amber-900 dark:text-amber-200"
      >
        <div className="font-semibold text-sm">Access Restricted (RBAC)</div>
        <p className="text-xs mt-1 text-amber-800 dark:text-amber-300">
          This action or section requires one of the following roles:{" "}
          <span className="font-mono font-medium">
            {roles.map((r) => ROLE_LABELS[r]).join(", ")}
          </span>
          . Current role: <span className="font-mono font-bold">{ROLE_LABELS[role]}</span>.
        </p>
      </div>
    );
  }

  return <>{children}</>;
};
