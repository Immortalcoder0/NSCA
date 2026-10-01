import React, { useState } from "react";
import { CheckCircle2, AlertCircle, ChevronDown, ChevronUp, User, Server } from "lucide-react";
import type { CollectionCompletenessData } from "../types";
import { cn } from "../../shared/lib/utils";

interface CollectionCompletenessProps {
  data: CollectionCompletenessData;
  className?: string;
}

export const CollectionCompleteness: React.FC<CollectionCompletenessProps> = ({
  data,
  className,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-5 space-y-4 shadow-sm",
        data.missing > 0
          ? "border-amber-300 dark:border-amber-900/60"
          : "border-emerald-300 dark:border-emerald-900/60",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            {data.missing === 0 ? (
              <CheckCircle2 size={18} className="text-emerald-500" />
            ) : (
              <AlertCircle size={18} className="text-amber-500" />
            )}
            <h3 className="text-sm font-bold text-foreground">Collection Completeness</h3>
          </div>
          <p className="text-xs text-muted-foreground">
            Audit guarantee: <strong className="text-foreground">{data.collected} of {data.total_in_scope}</strong> devices in scope ({data.percentage.toFixed(1)}%) ·{" "}
            <span className={data.missing > 0 ? "text-amber-600 dark:text-amber-400 font-bold" : "text-emerald-600"}>
              {data.missing} missing
            </span>
          </p>
        </div>

        {data.missing > 0 && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md border border-border text-xs font-semibold hover:bg-secondary transition-colors"
          >
            <span>{isExpanded ? "Hide Missing Devices" : "View Missing Devices"}</span>
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>

      {/* Progress Bar */}
      <div className="w-full h-2.5 bg-secondary rounded-full overflow-hidden">
        <div
          style={{ width: `${data.percentage}%` }}
          className={cn(
            "h-full rounded-full transition-all duration-300",
            data.percentage >= 100 ? "bg-emerald-500" : "bg-amber-500"
          )}
        />
      </div>

      {/* Expanded Missing Devices Table */}
      {isExpanded && data.missing_devices.length > 0 && (
        <div className="pt-3 border-t border-border space-y-2">
          <div className="text-xs font-semibold text-muted-foreground flex items-center justify-between">
            <span>Missing In-Scope Target Devices ({data.missing_devices.length})</span>
            <span className="text-[11px] italic">Per FR-ING-016: Custody attribution</span>
          </div>

          <div className="rounded-lg border border-border overflow-hidden bg-background">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/70 text-muted-foreground font-semibold border-b">
                <tr>
                  <th className="p-2.5">Device Hostname</th>
                  <th className="p-2.5">Target IP</th>
                  <th className="p-2.5">Role</th>
                  <th className="p-2.5">Responsible Engineer</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.missing_devices.map((d, idx) => (
                  <tr key={idx} className="hover:bg-muted/40 transition-colors">
                    <td className="p-2.5 font-mono font-bold text-foreground flex items-center gap-1.5">
                      <Server size={13} className="text-muted-foreground" />
                      {d.name}
                    </td>
                    <td className="p-2.5 font-mono text-muted-foreground">{d.ip || "—"}</td>
                    <td className="p-2.5 capitalize">{d.role || "—"}</td>
                    <td className="p-2.5 flex items-center gap-1 text-foreground">
                      <User size={13} className="text-muted-foreground" />
                      <span>{d.owner || "Unassigned"}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
