import React, { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { FindingCard } from "./FindingCard";
import type { FindingModel } from "../types";

export interface VirtualizedFindingListProps {
  findings: FindingModel[];
  selectedIds: string[];
  onSelect: (id: string, selected: boolean) => void;
  onAcceptRisk: (id: string) => void;
  /** Groups at or below this size render as a plain list — a scroll box
   * around three cards is friction, not performance. */
  virtualizeThreshold?: number;
  /** Height of the scroll viewport once virtualization kicks in. */
  viewportHeight?: number;
}

/**
 * Virtualised finding list for the workbench (frontend-02 §2.1 / U8 / A7 —
 * "an assessor works with hundreds of findings at once"). Uses
 * `@tanstack/react-virtual` directly — the same primitive `shared/DataTable`
 * is built on — rather than routing through `<DataTable>` itself, because
 * DataTable's row model is a flat table of cells: it cannot host a group
 * header, an inline `<SystemicFindingBanner>`, and a `<FindingCard>` whose
 * evidence expands to variable height in one row. Card height varies
 * (collapsed vs. evidence-expanded), so this measures real element height
 * via `measureElement` rather than assuming a fixed row size.
 */
export const VirtualizedFindingList: React.FC<VirtualizedFindingListProps> = ({
  findings,
  selectedIds,
  onSelect,
  onAcceptRisk,
  virtualizeThreshold = 10,
  viewportHeight = 640,
}) => {
  const parentRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtualizer({
    count: findings.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 96,
    overscan: 6,
  });

  if (findings.length <= virtualizeThreshold) {
    return (
      <div className="grid grid-cols-1 gap-3">
        {findings.map((finding) => (
          <FindingCard
            key={finding.id}
            finding={finding}
            selectable
            selected={selectedIds.includes(finding.id)}
            onSelect={onSelect}
            onAcceptRisk={onAcceptRisk}
          />
        ))}
      </div>
    );
  }

  const virtualItems = rowVirtualizer.getVirtualItems();

  return (
    <div
      ref={parentRef}
      style={{ height: viewportHeight, overflowY: "auto" }}
      className="rounded-xl border border-border/40 bg-secondary/10 p-1"
    >
      <div style={{ height: rowVirtualizer.getTotalSize(), position: "relative", width: "100%" }}>
        {virtualItems.map((virtualRow) => {
          const finding = findings[virtualRow.index];
          return (
            <div
              key={finding.id}
              ref={rowVirtualizer.measureElement}
              data-index={virtualRow.index}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start}px)`,
                padding: "6px 4px",
              }}
            >
              <FindingCard
                finding={finding}
                selectable
                selected={selectedIds.includes(finding.id)}
                onSelect={onSelect}
                onAcceptRisk={onAcceptRisk}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};
