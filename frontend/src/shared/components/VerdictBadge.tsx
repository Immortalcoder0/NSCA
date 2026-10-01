import React from "react";
import {
  CheckCircle2,
  AlertTriangle,
  CircleDot,
  XCircle,
  MinusCircle,
} from "lucide-react";
import { VERDICT_TOKENS, type VerdictType } from "../theme/tokens";
import { cn } from "../lib/utils";

export interface VerdictBadgeProps {
  verdict: VerdictType | string;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  monochromePrint?: boolean;
  className?: string;
}

export const VerdictBadge: React.FC<VerdictBadgeProps> = ({
  verdict,
  size = "md",
  showLabel = true,
  monochromePrint = false,
  className,
}) => {
  // Normalize verdict key
  const normalizedKey = (
    verdict.toUpperCase().replace(/[\s-]/g, "_")
  ) as VerdictType;
  const token = VERDICT_TOKENS[normalizedKey] || VERDICT_TOKENS.UNKNOWN;

  const sizeClasses = {
    sm: "text-[11px] px-2.5 py-0.5 gap-1.5",
    md: "text-xs px-3 py-1 gap-1.5 font-semibold",
    lg: "text-sm px-3.5 py-1.5 gap-2 font-bold",
  };

  const iconSizes = {
    sm: 12,
    md: 13,
    lg: 15,
  };

  const renderIcon = () => {
    const s = iconSizes[size];
    switch (token.glyph) {
      case "check-filled":
        return <CheckCircle2 size={s} className="shrink-0 stroke-[2.5]" aria-hidden="true" />;
      case "check-warning":
        return (
          <div className="relative inline-flex items-center justify-center shrink-0">
            <CheckCircle2 size={s} className="stroke-[2.2]" aria-hidden="true" />
            <AlertTriangle
              size={Math.max(8, s - 4)}
              className="absolute -top-1 -right-1 text-amber-600 bg-amber-100 rounded-full dark:text-amber-300 dark:bg-amber-900"
              aria-hidden="true"
            />
          </div>
        );
      case "check-hollow":
        return <CircleDot size={s} className="shrink-0 stroke-[1.8]" aria-hidden="true" />;
      case "cross-solid":
        return <XCircle size={s} className="shrink-0 stroke-[2.5]" aria-hidden="true" />;
      case "question":
        return (
          <span
            className="inline-flex items-center justify-center font-black rounded-full text-[10px] leading-none shrink-0 bg-slate-700 text-white dark:bg-slate-300 dark:text-slate-950 px-1 py-0.5 min-w-[14px]"
            aria-hidden="true"
          >
            ?
          </span>
        );
      case "dash":
      default:
        return <MinusCircle size={s} className="shrink-0 stroke-[1.8]" aria-hidden="true" />;
    }
  };

  if (monochromePrint) {
    return (
      <span
        role="status"
        aria-label={`Verdict: ${token.label}`}
        className={cn(
          "inline-flex items-center border border-black font-mono text-black bg-white rounded-full print:border-black",
          sizeClasses[size],
          token.monochrome.borderStyle === "dashed" && "border-dashed",
          token.monochrome.borderStyle === "dotted" && "border-dotted",
          token.monochrome.borderStyle === "double" && "border-double border-2",
          className
        )}
      >
        <span className="font-bold">{token.monochrome.glyphSymbol}</span>
        {showLabel && <span>{token.shortLabel}</span>}
      </span>
    );
  }

  return (
    <span
      role="status"
      aria-label={`Verdict: ${token.label}`}
      className={cn(
        "inline-flex items-center rounded-full border shadow-sm transition-all select-none",
        sizeClasses[size],
        token.color.bg,
        token.color.darkBg,
        className
      )}
    >
      {renderIcon()}
      {showLabel && <span>{token.label}</span>}
    </span>
  );
};
