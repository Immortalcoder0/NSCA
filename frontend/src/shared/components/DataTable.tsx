import { useState, useMemo, useRef } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  type ColumnDef,
  type SortingState,
  type RowSelectionState,
  flexRender,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  Search,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "../lib/utils";

export interface DataTableProps<TData> {
  data: TData[];
  columns: ColumnDef<TData, any>[];
  enableVirtualization?: boolean;
  virtualRowHeight?: number;
  searchPlaceholder?: string;
  enableRowSelection?: boolean;
  onSelectionChange?: (selectedRows: TData[]) => void;
  pageSize?: number;
  className?: string;
}

export function DataTable<TData>({
  data,
  columns,
  enableVirtualization = false,
  virtualRowHeight = 44,
  searchPlaceholder = "Search records...",
  enableRowSelection = false,
  onSelectionChange,
  pageSize = 20,
  className,
}: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const tableColumns = useMemo(() => {
    if (!enableRowSelection) return columns;

    const selectionColumn: ColumnDef<TData, any> = {
      id: "select",
      header: ({ table }) => (
        <input
          type="checkbox"
          aria-label="Select all rows"
          className="rounded border-border cursor-pointer accent-primary"
          checked={table.getIsAllPageRowsSelected()}
          onChange={table.getToggleAllPageRowsSelectedHandler()}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          aria-label={`Select row ${row.id}`}
          className="rounded border-border cursor-pointer accent-primary"
          checked={row.getIsSelected()}
          disabled={!row.getCanSelect()}
          onChange={row.getToggleSelectedHandler()}
        />
      ),
      size: 40,
    };

    return [selectionColumn, ...columns];
  }, [columns, enableRowSelection]);

  const table = useReactTable({
    data,
    columns: tableColumns,
    state: {
      sorting,
      globalFilter,
      rowSelection,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onRowSelectionChange: (updater) => {
      setRowSelection((old) => {
        const next = typeof updater === "function" ? updater(old) : updater;
        if (onSelectionChange) {
          const selectedItems = Object.keys(next)
            .filter((key) => next[Number(key) || key])
            .map((index) => data[Number(index)])
            .filter(Boolean);
          onSelectionChange(selectedItems);
        }
        return next;
      });
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: enableVirtualization ? undefined : getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize,
      },
    },
  });

  const { rows } = table.getRowModel();

  // Virtualizer setup if enabled
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => virtualRowHeight,
    overscan: 10,
    enabled: enableVirtualization,
  });

  return (
    <div className={cn("space-y-3.5", className)}>
      {/* Top Search Filter */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={globalFilter ?? ""}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder={searchPlaceholder}
            className="w-full pl-9 pr-4 py-2 text-xs rounded-full border border-border/80 bg-card shadow-subtle focus:outline-none focus:ring-2 focus:ring-primary/30 transition-all"
          />
        </div>

        {enableRowSelection && Object.keys(rowSelection).length > 0 && (
          <div className="text-xs text-muted-foreground font-medium px-3 py-1 bg-primary/10 text-primary rounded-full">
            <span className="font-bold">
              {Object.keys(rowSelection).length}
            </span>{" "}
            selected
          </div>
        )}
      </div>

      {/* Table Container with Material Card Elevation */}
      <div
        ref={tableContainerRef}
        className={cn(
          "rounded-2xl border border-border/70 bg-card shadow-card overflow-hidden transition-all",
          enableVirtualization ? "max-h-[500px]" : ""
        )}
      >
        <table className="w-full text-xs text-left border-collapse">
          <thead className="sticky top-0 bg-secondary/70 backdrop-blur-md z-10 border-b border-border/70 font-semibold text-muted-foreground">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}
                    className="p-3.5 select-none font-semibold text-foreground tracking-tight"
                  >
                    {header.isPlaceholder ? null : (
                      <div
                        className={cn(
                          "flex items-center gap-1.5",
                          header.column.getCanSort() ? "cursor-pointer hover:text-primary transition-colors" : ""
                        )}
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getCanSort() && (
                          <span className="text-muted-foreground">
                            {header.column.getIsSorted() === "asc" ? (
                              <ChevronUp size={14} className="text-primary" />
                            ) : header.column.getIsSorted() === "desc" ? (
                              <ChevronDown size={14} className="text-primary" />
                            ) : (
                              <ChevronsUpDown size={12} className="opacity-40" />
                            )}
                          </span>
                        )}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>

          <tbody className="divide-y divide-border/60">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={tableColumns.length} className="h-28 text-center text-muted-foreground italic">
                  No matching records found.
                </td>
              </tr>
            ) : enableVirtualization ? (
              <>
                <tr style={{ height: `${rowVirtualizer.getVirtualItems()[0]?.start ?? 0}px` }} />
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const row = rows[virtualRow.index];
                  return (
                    <tr
                      key={row.id}
                      className={cn(
                        "hover:bg-secondary/40 transition-colors",
                        row.getIsSelected() && "bg-primary/5"
                      )}
                      style={{ height: `${virtualRow.size}px` }}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="p-3.5 align-middle">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  );
                })}
                <tr
                  style={{
                    height: `${
                      rowVirtualizer.getTotalSize() -
                      (rowVirtualizer.getVirtualItems()[
                        rowVirtualizer.getVirtualItems().length - 1
                      ]?.end ?? 0)
                    }px`,
                  }}
                />
              </>
            ) : (
              rows.map((row) => (
                <tr
                  key={row.id}
                  className={cn(
                    "hover:bg-secondary/40 transition-colors",
                    row.getIsSelected() && "bg-primary/5"
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="p-3.5 align-middle">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls (when not virtualized) */}
      {!enableVirtualization && rows.length > 0 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground px-2 pt-1">
          <div>
            Showing{" "}
            <span className="font-semibold text-foreground">
              {table.getState().pagination.pageIndex * pageSize + 1}
            </span>{" "}
            to{" "}
            <span className="font-semibold text-foreground">
              {Math.min(
                (table.getState().pagination.pageIndex + 1) * pageSize,
                table.getFilteredRowModel().rows.length
              )}
            </span>{" "}
            of{" "}
            <span className="font-semibold text-foreground">
              {table.getFilteredRowModel().rows.length}
            </span>{" "}
            entries
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              aria-label="Previous Page"
              className="p-1.5 rounded-full border border-border/80 bg-card hover:bg-secondary disabled:opacity-40 transition-colors shadow-subtle"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="font-medium text-foreground">
              Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
            </span>
            <button
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              aria-label="Next Page"
              className="p-1.5 rounded-full border border-border/80 bg-card hover:bg-secondary disabled:opacity-40 transition-colors shadow-subtle"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
