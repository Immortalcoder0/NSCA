import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DataTable } from "./DataTable";
import type { ColumnDef } from "@tanstack/react-table";

interface TestRow {
  id: string;
  name: string;
  count: number;
}

const columns: ColumnDef<TestRow>[] = [
  {
    accessorKey: "name",
    header: "Name",
  },
  {
    accessorKey: "count",
    header: "Count",
  },
];

const mockData: TestRow[] = [
  { id: "1", name: "Alpha", count: 10 },
  { id: "2", name: "Beta", count: 20 },
  { id: "3", name: "Gamma", count: 30 },
];

describe("DataTable Component", () => {
  it("renders table headers and rows", () => {
    render(<DataTable data={mockData} columns={columns} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Count")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("filters rows based on global search", () => {
    render(<DataTable data={mockData} columns={columns} />);
    const input = screen.getByPlaceholderText("Search records...");
    fireEvent.change(input, { target: { value: "Alpha" } });

    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.queryByText("Beta")).not.toBeInTheDocument();
  });

  it("supports row selection callbacks", () => {
    const handleSelection = vi.fn();
    render(
      <DataTable
        data={mockData}
        columns={columns}
        enableRowSelection={true}
        onSelectionChange={handleSelection}
      />
    );

    const selectAllCheckbox = screen.getByLabelText("Select all rows");
    fireEvent.click(selectAllCheckbox);

    expect(handleSelection).toHaveBeenCalled();
  });
});
