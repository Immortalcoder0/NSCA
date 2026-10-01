import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./auth-guard";
import { Shell } from "./shell";

// Shell now renders the "Fill With Demo Data" button (useSeedDemoData,
// a TanStack Query mutation) in its header, so every render needs a real
// QueryClientProvider ancestor — same pattern as campaigns.test.tsx.
function renderShell() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/campaigns"]}>
        <AuthProvider>
          <Shell />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("App Shell Component", () => {
  it("renders NSCA brand header and all 7 section nav items", () => {
    renderShell();

    expect(screen.getByText("NSCA")).toBeInTheDocument();
    expect(screen.getAllByText("Campaigns")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Estate")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Findings")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Training Studio")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Knowledge")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Reports")[0]).toBeInTheDocument();
    expect(screen.getAllByText("Administration")[0]).toBeInTheDocument();
  });

  it("renders dev role switcher in the header", () => {
    renderShell();

    const roleSelect = screen.getByLabelText("Dev RBAC Role Switcher");
    expect(roleSelect).toBeInTheDocument();
  });

  it("renders the Fill With Demo Data button", () => {
    renderShell();

    expect(screen.getByText("Fill With Demo Data")).toBeInTheDocument();
  });
});
