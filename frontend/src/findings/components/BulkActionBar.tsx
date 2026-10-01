import React from "react";
import { CheckCircle2, UserPlus, ShieldAlert, Download, X } from "lucide-react";

interface BulkActionBarProps {
  selectedCount: number;
  onClearSelection: () => void;
  onBulkConfirm?: () => void;
  onBulkAssign?: (assignee: string) => void;
  onBulkAcceptRisk?: () => void;
  onBulkExport?: () => void;
}

export const BulkActionBar: React.FC<BulkActionBarProps> = ({
  selectedCount,
  onClearSelection,
  onBulkConfirm,
  onBulkAssign,
  onBulkAcceptRisk,
  onBulkExport,
}) => {
  if (selectedCount === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 max-w-2xl w-full px-4 animate-in fade-in slide-in-from-bottom-4 duration-200">
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl border border-primary/40 bg-card/95 text-card-foreground shadow-2xl backdrop-blur text-xs">
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-0.5 rounded-full bg-primary text-primary-foreground font-mono font-black text-xs">
            {selectedCount}
          </span>
          <span className="font-bold text-foreground">
            {selectedCount === 1 ? "finding selected" : "findings selected"}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {onBulkConfirm && (
            <button
              onClick={onBulkConfirm}
              className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white font-semibold transition-colors"
            >
              <CheckCircle2 size={13} />
              <span>Confirm</span>
            </button>
          )}

          {onBulkAssign && (
            <button
              onClick={() => onBulkAssign("p.sharma")}
              className="flex items-center gap-1 px-3 py-1.5 rounded-md border border-border bg-secondary hover:bg-secondary/80 font-semibold transition-colors"
            >
              <UserPlus size={13} />
              <span>Assign</span>
            </button>
          )}

          {onBulkAcceptRisk && (
            <button
              onClick={onBulkAcceptRisk}
              className="flex items-center gap-1 px-3 py-1.5 rounded-md border border-border bg-secondary hover:bg-secondary/80 font-semibold transition-colors"
            >
              <ShieldAlert size={13} />
              <span>Accept Risk</span>
            </button>
          )}

          {onBulkExport && (
            <button
              onClick={onBulkExport}
              className="flex items-center gap-1 px-3 py-1.5 rounded-md border border-border bg-secondary hover:bg-secondary/80 font-semibold transition-colors"
            >
              <Download size={13} />
              <span>Export</span>
            </button>
          )}

          <button
            onClick={onClearSelection}
            title="Deselect all"
            aria-label="Clear selection"
            className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground hover:text-foreground"
          >
            <X size={15} />
          </button>
        </div>
      </div>
    </div>
  );
};
