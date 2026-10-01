/**
 * NSCA UI Domain Types
 * UI-only state representations, enums, and utility structures
 * complementing generated OpenAPI schema types.
 */

export type UserRole =
  | "assessor"
  | "lead_assessor"
  | "network_administrator"
  | "platform_administrator"
  | "read_only";

export const ROLE_LABELS: Record<UserRole, string> = {
  assessor: "Assessor",
  lead_assessor: "Lead Assessor",
  network_administrator: "Network Administrator",
  platform_administrator: "Platform Administrator",
  read_only: "Read-only",
};

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  token?: string;
}

export type FindingStatus =
  | "open"
  | "disputed"
  | "remediation_planned"
  | "risk_accepted"
  | "verified_resolved";

export type CampaignStatus = "Draft" | "Issued" | "Active" | "Closed";

export interface PaginationParams {
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}
