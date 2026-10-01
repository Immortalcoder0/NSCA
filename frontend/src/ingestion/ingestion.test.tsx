import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ArtifactOutcomeCard } from "./components/ArtifactOutcomeCard";
import { CollectionCompleteness } from "./components/CollectionCompleteness";
import { LiveCollectionModal } from "./components/LiveCollectionModal";
import { AccessibleFileDropzone } from "./components/AccessibleFileDropzone";
import type { IngestionArtifactItem, CollectionCompletenessData } from "./types";

describe("Ingestion Subsystem", () => {
  it("renders all 4 outcome states distinctly in ArtifactOutcomeCard", () => {
    const parsedItem: IngestionArtifactItem = {
      id: "1",
      device: "CORE-SW-01",
      platform: "Cisco IOS-XE",
      status: "parsed",
      correlated_artifacts: [{ name: "running.cfg", type: "config", sha256: "abc" }],
    };

    const { rerender } = render(
      <MemoryRouter>
        <ArtifactOutcomeCard item={parsedItem} />
      </MemoryRouter>
    );
    expect(screen.getByRole("status")).toHaveTextContent("Parsed");
    expect(screen.getByText("CORE-SW-01")).toBeInTheDocument();

    const caveatItem: IngestionArtifactItem = {
      ...parsedItem,
      status: "parsed_with_caveat",
      unassessable_controls_count: 34,
      export_mode: "terse",
    };
    rerender(
      <MemoryRouter>
        <ArtifactOutcomeCard item={caveatItem} />
      </MemoryRouter>
    );
    expect(screen.getByRole("status")).toHaveTextContent("Parsed with Caveat");
    expect(screen.getByText(/34 controls unassessable/i)).toBeInTheDocument();

    const notTaughtItem: IngestionArtifactItem = {
      ...parsedItem,
      status: "platform_not_taught",
      platform: "MikroTik RouterOS",
      training_questions_count: 9,
    };
    rerender(
      <MemoryRouter>
        <ArtifactOutcomeCard item={notTaughtItem} />
      </MemoryRouter>
    );
    expect(screen.getByRole("status")).toHaveTextContent("NOT TAUGHT");
    expect(screen.getByText(/Teach Grammar/i)).toBeInTheDocument();
    // Deep-links into Track 3's training queue at the exact documented
    // route (docs/15-api-specification.md §3's training.url shape:
    // /api/v1/training/queue/{platform}), with the platform pre-selected --
    // not a generic /training landing page.
    expect(screen.getByText(/Teach Grammar/i).closest("a")).toHaveAttribute(
      "href",
      "/training/queue/MikroTik%20RouterOS"
    );

    const unidentifiedItem: IngestionArtifactItem = {
      ...parsedItem,
      status: "unidentified",
      grammar_coverage: 0.43,
    };
    rerender(
      <MemoryRouter>
        <ArtifactOutcomeCard item={unidentifiedItem} />
      </MemoryRouter>
    );
    expect(screen.getByRole("status")).toHaveTextContent("Unidentified");
    expect(screen.getByText(/Assisted grammar authoring/i)).toBeInTheDocument();
  });

  it("renders CollectionCompleteness and expands missing devices list", () => {
    const completenessData: CollectionCompletenessData = {
      total_in_scope: 412,
      collected: 389,
      missing: 23,
      percentage: 94.4,
      missing_devices: [
        { name: "MGMT-SW-04", ip: "10.250.0.14", role: "Management Switch", owner: "r.kulkarni" },
      ],
    };

    render(<CollectionCompleteness data={completenessData} />);

    expect(screen.getByText(/389 of 412/i)).toBeInTheDocument();
    expect(screen.getByText(/23 missing/i)).toBeInTheDocument();

    const viewButton = screen.getByText("View Missing Devices");
    fireEvent.click(viewButton);

    expect(screen.getByText("MGMT-SW-04")).toBeInTheDocument();
    expect(screen.getByText("r.kulkarni")).toBeInTheDocument();
  });

  it("dispatches live collection with mode 'read_only' (G4 guarantee)", () => {
    const handleStart = vi.fn();
    render(
      <LiveCollectionModal
        isOpen={true}
        onClose={() => {}}
        onStartCollection={handleStart}
      />
    );

    expect(screen.getByText(/Guarantee G4: Strictly Read-Only Transport/i)).toBeInTheDocument();

    const submitBtn = screen.getByText("Dispatch Read-Only Collector");
    fireEvent.click(submitBtn);

    expect(handleStart).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: "read_only",
      })
    );
  });

  it("upload dropzone is reachable and activatable by keyboard alone (NFR-USE-008)", () => {
    render(
      <MemoryRouter>
        <AccessibleFileDropzone />
      </MemoryRouter>
    );

    const dropzone = screen.getByRole("button", { name: /drop configuration files/i });
    // Focusable via Tab (tabIndex=0), unlike shared/FileDropzone's plain div.
    expect(dropzone).toHaveAttribute("tabindex", "0");

    const fileInput = screen.getByLabelText(/upload configuration files/i) as HTMLInputElement;
    const clickSpy = vi.spyOn(fileInput, "click");

    dropzone.focus();
    expect(dropzone).toHaveFocus();

    fireEvent.keyDown(dropzone, { key: "Enter" });
    expect(clickSpy).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(dropzone, { key: " " });
    expect(clickSpy).toHaveBeenCalledTimes(2);
  });
});
