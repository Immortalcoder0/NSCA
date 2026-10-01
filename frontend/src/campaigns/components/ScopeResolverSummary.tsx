import React from "react";
import { Server, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "../../shared/lib/utils";

interface ScopeResolverSummaryProps {
  expression: string;
  resolvedCount?: number;
  totalInventoryCount?: number;
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}

export const ScopeResolverSummary: React.FC<ScopeResolverSummaryProps> = ({
  expression,
  resolvedCount = 412,
  totalInventoryCount = 500,
  isLoading = false,
  error = null,
  className,
}) => {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-4 space-y-3",
        error && "border-red-300 dark:border-red-900 bg-red-50/40 dark:bg-red-950/20",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
          <Server size={15} className="text-primary" />
          <span>Scope Resolution Preview</span>
        </div>
        {isLoading ? (
          <span className="text-xs text-muted-foreground animate-pulse">Resolving assets...</span>
        ) : error ? (
          <span className="text-xs text-red-600 dark:text-red-400 font-medium flex items-center gap-1">
            <AlertCircle size={13} />
            Syntax error in filter expression
          </span>
        ) : (
          <span className="text-xs text-emerald-700 dark:text-emerald-300 font-medium flex items-center gap-1">
            <CheckCircle2 size={13} />
            Target set verified
          </span>
        )}
      </div>

      <div className="bg-muted/70 p-2 rounded text-xs font-mono break-all text-muted-foreground border border-border/50">
        {expression || "exposure == 'all'"}
      </div>

      {!error && (
        <div className="flex items-center justify-between text-xs pt-1 border-t border-border/50">
          <span className="text-muted-foreground">Resolved Devices:</span>
          <span className="font-bold text-foreground">
            {resolvedCount} of {totalInventoryCount} assets in scope (
            {Math.round((resolvedCount / totalInventoryCount) * 100)}%)
          </span>
        </div>
      )}
    </div>
  );
};
