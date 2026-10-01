import type { ReactElement } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { KnowledgeFreshnessBox } from "./components/KnowledgeFreshnessBox";
import { CredentialCreateModal } from "./components/CredentialCreateModal";
import { AuditChainVerifier } from "./components/AuditChainVerifier";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { CredentialVaultPage } from "./pages/CredentialVaultPage";
import type { SystemFreshnessModel, CredentialProfileModel } from "./types";

function withProviders(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Administration & Audit Subsystem", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders KnowledgeFreshnessBox with staleness statement", () => {
    const mockFreshness: SystemFreshnessModel = {
      engine_version: "NSCA Engine 0.1.0",
      platform_health: "HEALTHY",
      vulnerability_db_date: "2026-07-16",
      vulnerability_db_staleness_text: "43 days old",
      rulepack_freshness_status: "UP_TO_DATE",
      active_campaigns_count: 3,
    };

    render(<KnowledgeFreshnessBox freshness={mockFreshness} />);

    expect(screen.getByText("43 days old")).toBeInTheDocument();
    expect(screen.getByText("NSCA Engine 0.1.0")).toBeInTheDocument();
  });

  it("stores write-only credentials in CredentialCreateModal without secret exposure", () => {
    const handleSubmit = vi.fn();
    render(
      <CredentialCreateModal
        isOpen={true}
        onClose={() => {}}
        onSubmit={handleSubmit}
      />
    );

    expect(screen.getByText(/Write-Only Credential Vault/i)).toBeInTheDocument();
    expect(screen.getByText("Store Write-Only Credential")).toBeInTheDocument();
  });

  it("renders the real GET /admin/audit-log/verify result once triggered (100% intact)", async () => {
    // This used to render a canned "1420 records / 100% INTACT" result on
    // mount, before any verification ran — a mock artifact, not a real
    // initial state. The real component shows nothing until the user
    // clicks "Verify Hash Continuity", which calls the real endpoint
    // (audit/log.py:verify_chain, Platform Administrator only).
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ entries_checked: 1420, chain_intact: true, first_break: null }),
    });
    global.fetch = fetchSpy as unknown as typeof fetch;

    withProviders(<AuditChainVerifier />);
    expect(screen.getByText(/Not yet verified this session/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText("Verify Hash Continuity"));

    expect(await screen.findByText("100% INTACT")).toBeInTheDocument();
    expect(screen.getByText(/1420 sequential records/i)).toBeInTheDocument();
    expect(String(fetchSpy.mock.calls[0][0])).toContain("/admin/audit-log/verify");
  });

  it("renders a broken-chain result distinctly, real endpoint shape (entries_checked/chain_intact/first_break)", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ entries_checked: 83, chain_intact: false, first_break: "audit-log-entry-42" }),
    });
    global.fetch = fetchSpy as unknown as typeof fetch;

    withProviders(<AuditChainVerifier />);
    fireEvent.click(screen.getByText("Verify Hash Continuity"));

    expect(await screen.findByText(/BROKEN AT audit-log-entry-42/i)).toBeInTheDocument();
  });

  it("never renders credential material even from a deliberately tampered credentials payload (NFR-SEC-003 / FR-ADM-006)", () => {
    // Simulate a compromised or misbehaving API response that violates the
    // CredentialProfileModel contract by echoing back secret-shaped fields.
    // The UI must have NO code path that renders these, regardless of what
    // the backend sends — this is a client-side assertion, not just trust
    // in the API contract.
    const tamperedCredentials = [
      {
        id: "cred-tampered-01",
        alias: "Tampered-Profile",
        target_type: "ssh_key",
        username: "svc-tampered",
        created_by: "attacker-simulated",
        created_at: "2026-08-01",
        last_used: "Never",
        // The following fields do NOT exist on CredentialProfileModel and
        // must never be rendered, even though a tampered/buggy API might
        // include them in a response payload.
        password: "LEAKED_PLAINTEXT_PASSWORD_9182",
        private_key: "-----BEGIN RSA PRIVATE KEY----- LEAKED_KEY_MATERIAL",
        secret: "LEAKED_SECRET_TOKEN_ABCDEF",
        encrypted_material: "LEAKED_CIPHERTEXT_BLOB_ZZZ999",
      },
    ] as unknown as CredentialProfileModel[];

    // The `initialCredentials` seam bypasses the real fetch, but the page
    // still calls `useAdminCredentials()` unconditionally (its result is
    // just ignored when the prop is set) — mock fetch so that background
    // query doesn't hit the network in the test environment.
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [] }) }) as unknown as typeof fetch;

    withProviders(<CredentialVaultPage initialCredentials={tamperedCredentials} />);

    // Sanity: the safe, non-secret fields render normally.
    expect(screen.getByText("Tampered-Profile")).toBeInTheDocument();
    expect(screen.getByText("svc-tampered")).toBeInTheDocument();

    // None of the secret-shaped values may ever appear in the rendered DOM.
    expect(screen.queryByText(/LEAKED_PLAINTEXT_PASSWORD_9182/)).not.toBeInTheDocument();
    expect(screen.queryByText(/LEAKED_KEY_MATERIAL/)).not.toBeInTheDocument();
    expect(screen.queryByText(/LEAKED_SECRET_TOKEN_ABCDEF/)).not.toBeInTheDocument();
    expect(screen.queryByText(/LEAKED_CIPHERTEXT_BLOB_ZZZ999/)).not.toBeInTheDocument();

    // The secret column must always render the fixed write-only placeholder,
    // never a value sourced from the record itself.
    expect(screen.getByText("ENCRYPTED (WRITE-ONLY)")).toBeInTheDocument();

    // Also verify the full document body text, as a structural guard against
    // any future change that might dump the raw object (e.g. via JSON.stringify
    // in a debug view) rather than an explicit field-by-field render.
    expect(document.body.textContent).not.toMatch(/LEAKED_/);
  });

  it("never leaks in-progress secret material typed into CredentialCreateModal, even after submission", () => {
    const handleSubmit = vi.fn();
    render(
      <CredentialCreateModal isOpen={true} onClose={() => {}} onSubmit={handleSubmit} />
    );

    fireEvent.change(screen.getByLabelText(/Profile Alias/i), {
      target: { value: "New-Profile" },
    });
    fireEvent.change(screen.getByLabelText(/Service Account Username/i), {
      target: { value: "svc-new" },
    });
    fireEvent.change(screen.getByLabelText(/Secret Passphrase/i), {
      target: { value: "TYPED_SECRET_SHOULD_NEVER_RENDER_555" },
    });

    fireEvent.click(screen.getByText("Store Write-Only Credential"));

    // onSubmit must only ever be called with the non-secret fields.
    expect(handleSubmit).toHaveBeenCalledWith({
      alias: "New-Profile",
      target_type: "ssh_key",
      username: "svc-new",
    });
    const submittedPayload = handleSubmit.mock.calls[0][0];
    expect(submittedPayload).not.toHaveProperty("secretMaterial");
    expect(submittedPayload).not.toHaveProperty("secret");
    expect(submittedPayload).not.toHaveProperty("password");
  });

  it("renders AdminDashboardPage and CredentialVaultPage cleanly against real (mocked) API responses", async () => {
    global.fetch = vi.fn(async (url: string) => {
      const u = String(url);
      if (u.includes("/admin/status")) {
        return { ok: true, status: 200, json: async () => ({ status: "ok", db: "ok", job_queue: { pending: 0, running: 0 }, inference_container: "not_configured", version: "0.1.0" }) };
      }
      if (u.includes("/knowledge/freshness")) {
        return { ok: true, status: 200, json: async () => ({ rulepacks: [{ id: "cisco_iosxe", version: "7.2.1", imported_at: "2026-06-01T00:00:00Z" }], vulnerability_index: { snapshot_date: "2026-08-01", age_days: 27 } }) };
      }
      if (u.includes("/campaigns")) {
        return { ok: true, status: 200, json: async () => ({ items: [], next_cursor: null }) };
      }
      if (u.includes("/admin/credentials")) {
        return { ok: true, status: 200, json: async () => ({ items: [{ id: "cred-audit-ios", label: "IOS audit account", type: "ssh_keypair" }] }) };
      }
      return { ok: false, status: 404, statusText: "Not Found", json: async () => ({ detail: "not found" }) };
    }) as unknown as typeof fetch;

    const { unmount } = withProviders(<AdminDashboardPage />);
    expect(screen.getByText("Platform Administration & System Health")).toBeInTheDocument();
    // Real staleness text derived from `vulnerability_index.age_days`
    // (11-audit-integrity.md §13.3's "N days old" phrasing).
    expect(await screen.findByText("27 days old")).toBeInTheDocument();
    unmount();

    withProviders(<CredentialVaultPage />);
    expect(screen.getByText("Write-Only Diagnostic Credential Profiles")).toBeInTheDocument();
    expect(await screen.findByText("IOS audit account")).toBeInTheDocument();
  });
});
