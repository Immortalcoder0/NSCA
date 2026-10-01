import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FileDropzone } from "./FileDropzone";

describe("FileDropzone Component", () => {
  it("renders upload invitation text", () => {
    render(<FileDropzone />);
    expect(
      screen.getByText(/Drop configuration files or archives here/i)
    ).toBeInTheDocument();
  });

  it("handles file selection via input", () => {
    const handleFiles = vi.fn();
    render(<FileDropzone onFilesSelected={handleFiles} />);

    const input = screen.getByLabelText("Upload configuration files");
    const file = new File(["test config"], "cisco.cfg", { type: "text/plain" });

    fireEvent.change(input, { target: { files: [file] } });

    expect(screen.getByText("cisco.cfg")).toBeInTheDocument();
    expect(handleFiles).toHaveBeenCalled();
  });
});
