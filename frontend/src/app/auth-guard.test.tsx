import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthProvider, RequireRole } from "./auth-guard";

describe("AuthGuard and RequireRole", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders protected content when user has the allowed role", () => {
    localStorage.setItem("nsca_dev_role", "lead_assessor");

    render(
      <AuthProvider>
        <RequireRole roles={["lead_assessor"]}>
          <div data-testid="protected-content">Secret Admin Area</div>
        </RequireRole>
      </AuthProvider>
    );

    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  it("blocks access and shows warning when user does not have allowed role", () => {
    localStorage.setItem("nsca_dev_role", "read_only");

    render(
      <AuthProvider>
        <RequireRole roles={["lead_assessor"]}>
          <div data-testid="protected-content">Secret Admin Area</div>
        </RequireRole>
      </AuthProvider>
    );

    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Access Restricted (RBAC)");
  });

  it("renders custom fallback if provided on restricted access", () => {
    localStorage.setItem("nsca_dev_role", "read_only");

    render(
      <AuthProvider>
        <RequireRole
          roles={["lead_assessor"]}
          fallback={<div data-testid="custom-fallback">Custom Fallback Notice</div>}
        >
          <div>Secret Area</div>
        </RequireRole>
      </AuthProvider>
    );

    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
  });
});
