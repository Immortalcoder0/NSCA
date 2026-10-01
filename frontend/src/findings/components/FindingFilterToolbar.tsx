import React from "react";
import { Search, Layers, Filter } from "lucide-react";
import type { FindingGroupBy } from "../types";

interface FindingFilterToolbarProps {
  groupBy: FindingGroupBy;
  onGroupByChange: (mode: FindingGroupBy) => void;
  severityFilter: string;
  onSeverityFilterChange: (sev: string) => void;
  verdictFilter: string;
  onVerdictFilterChange: (v: string) => void;
  searchTerm: string;
  onSearchTermChange: (term: string) => void;
}

export const FindingFilterToolbar: React.FC<FindingFilterToolbarProps> = ({
  groupBy,
  onGroupByChange,
  severityFilter,
  onSeverityFilterChange,
  verdictFilter,
  onVerdictFilterChange,
  searchTerm,
  onSearchTermChange,
}) => {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 rounded-xl border border-border bg-card text-xs shadow-sm">
      {/* Group-by Switcher */}
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground font-semibold flex items-center gap-1">
          <Layers size={14} className="text-primary" />
          <span>Group by:</span>
        </span>
        <div className="flex items-center gap-1 bg-secondary/80 p-1 rounded-lg border">
          {(
            [
              { id: "control", label: "Control (Default)" },
              { id: "device", label: "Device" },
              { id: "attack_path", label: "Attack Path" },
              { id: "systemic", label: "Systemic" },
            ] as Array<{ id: FindingGroupBy; label: string }>
          ).map((item) => (
            <button
              key={item.id}
              onClick={() => onGroupByChange(item.id)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                groupBy === item.id
                  ? "bg-background text-foreground font-bold shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filter Dropdowns & Search */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5">
          <Filter size={13} className="text-muted-foreground" />
          <select
            aria-label="Filter by Severity"
            value={severityFilter}
            onChange={(e) => onSeverityFilterChange(e.target.value)}
            className="px-2.5 py-1.5 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring cursor-pointer"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          <select
            aria-label="Filter by Verdict"
            value={verdictFilter}
            onChange={(e) => onVerdictFilterChange(e.target.value)}
            className="px-2.5 py-1.5 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring cursor-pointer"
          >
            <option value="all">All Verdicts</option>
            <option value="fail">FAIL Only</option>
            <option value="unknown">UNKNOWN (⊥) Only</option>
            <option value="pass_partial">Partial Only</option>
          </select>
        </div>

        <div className="relative w-full sm:w-60">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search findings, controls, hosts..."
            value={searchTerm}
            onChange={(e) => onSearchTermChange(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>
    </div>
  );
};
