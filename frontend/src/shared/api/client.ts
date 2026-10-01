import type { UserRole } from "../types/domain";

export interface ApiClientConfig {
  baseUrl?: string;
  getRole?: () => UserRole;
  getToken?: () => string | null;
}

export class ApiError extends Error {
  public status: number;
  public statusText: string;
  public details?: unknown;

  constructor(status: number, statusText: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
    this.details = details;
  }
}

class ApiClient {
  private baseUrl: string;
  private getRoleFn: () => UserRole;
  private getTokenFn: () => string | null;

  constructor(config: ApiClientConfig = {}) {
    this.baseUrl = config.baseUrl || "/api/v1";
    this.getRoleFn =
      config.getRole ||
      (() => {
        try {
          const savedRole = localStorage.getItem("nsca_dev_role");
          if (savedRole) return savedRole as UserRole;
        } catch {
          // fallback in SSR/test environments
        }
        return "lead_assessor";
      });
    this.getTokenFn =
      config.getToken ||
      (() => {
        try {
          return localStorage.getItem("nsca_auth_token");
        } catch {
          return null;
        }
      });
  }

  private getHeaders(customHeaders: HeadersInit = {}): Headers {
    const headers = new Headers(customHeaders);
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const token = this.getTokenFn();
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const devRole = this.getRoleFn();
    if (devRole && !headers.has("X-Dev-Role")) {
      headers.set("X-Dev-Role", devRole);
    }

    return headers;
  }

  public async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = endpoint.startsWith("http")
      ? endpoint
      : `${this.baseUrl}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

    const headers = this.getHeaders(options.headers);

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorDetails: unknown = null;
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;

      try {
        errorDetails = await response.json();
        if (
          errorDetails &&
          typeof errorDetails === "object" &&
          "detail" in errorDetails &&
          typeof (errorDetails as { detail: unknown }).detail === "string"
        ) {
          errorMessage = (errorDetails as { detail: string }).detail;
        }
      } catch {
        // Failed to parse JSON error body
      }

      throw new ApiError(
        response.status,
        response.statusText,
        errorMessage,
        errorDetails
      );
    }

    if (response.status === 204) {
      return null as unknown as T;
    }

    return response.json() as Promise<T>;
  }

  public get<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "GET" });
  }

  public post<T>(endpoint: string, body?: unknown, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public patch<T>(endpoint: string, body?: unknown, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public put<T>(endpoint: string, body?: unknown, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  public delete<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "DELETE" });
  }

  /** Additive: multipart form-data POST (file uploads — e.g. rulepack /
   * framework bundle import). Must NOT set a `Content-Type` header itself
   * so the browser can append the multipart boundary. */
  public async postForm<T>(endpoint: string, form: FormData): Promise<T> {
    const url = endpoint.startsWith("http")
      ? endpoint
      : `${this.baseUrl}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
    const headers = this.getHeaders();
    headers.delete("Content-Type");
    const response = await fetch(url, { method: "POST", headers, body: form });
    if (!response.ok) {
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;
      let errorDetails: unknown = null;
      try {
        errorDetails = await response.json();
        if (errorDetails && typeof errorDetails === "object" && "detail" in errorDetails) {
          const detail = (errorDetails as { detail: unknown }).detail;
          if (typeof detail === "string") errorMessage = detail;
        }
      } catch {
        // ignore
      }
      throw new ApiError(response.status, response.statusText, errorMessage, errorDetails);
    }
    return response.json() as Promise<T>;
  }

  /** Additive: for binary/non-JSON responses (e.g. report downloads —
   * `GET /reports/{id}/download?format=pdf|docx|json|csv|oscal`) where
   * `request<T>`'s unconditional `response.json()` would throw. Applies
   * the same auth/role headers as every other method. */
  public async getBlob(endpoint: string, options?: RequestInit): Promise<Blob> {
    const url = endpoint.startsWith("http")
      ? endpoint
      : `${this.baseUrl}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
    const headers = this.getHeaders(options?.headers);
    const response = await fetch(url, { ...options, method: "GET", headers });
    if (!response.ok) {
      throw new ApiError(response.status, response.statusText, `HTTP Error ${response.status}: ${response.statusText}`);
    }
    return response.blob();
  }
}

export const apiClient = new ApiClient();
