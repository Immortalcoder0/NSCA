import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProgressPanel } from "./ProgressPanel";

describe("ProgressPanel Component", () => {
  it("renders progress percentage and item counts", () => {
    render(
      <ProgressPanel
        title="Processing Artifacts"
        processedCount={327}
        totalCount={389}
        currentStepLabel="Ingesting configuration"
      />
    );

    expect(screen.getByText("Processing Artifacts")).toBeInTheDocument();
    expect(screen.getByText("327 / 389 (84%)")).toBeInTheDocument();
    expect(screen.getByText(/Current stage: Ingesting configuration/i)).toBeInTheDocument();
  });

  it("renders step list items", () => {
    render(
      <ProgressPanel
        title="Assessment Pipeline"
        steps={[
          { id: "1", label: "Fingerprint Platform", status: "completed", detail: "Cisco IOS-XE 16.12" },
          { id: "2", label: "Parse AST", status: "running" },
          { id: "3", label: "Evaluate Rules", status: "pending" },
        ]}
      />
    );

    expect(screen.getByText("Fingerprint Platform")).toBeInTheDocument();
    expect(screen.getByText("Parse AST")).toBeInTheDocument();
    expect(screen.getByText("Evaluate Rules")).toBeInTheDocument();
  });
});
