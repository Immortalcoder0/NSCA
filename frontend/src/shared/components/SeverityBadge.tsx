import React from "react";
import {
  OctagonAlert,
  Diamond,
  TriangleAlert,
  CircleDot,
  Info,
} from "lucide-react";
import { SEVERITY_TOKENS, type SeverityType } from "../theme/tokens";
import { cn } from "../lib/utils";

export interface SeverityBadgeProps {
  severity: SeverityType | string;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  monochromePrint?: boolean;
  className?: string;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({
  severity,
  size = "md",
  showLabel = true,
  monochromePrint = false,
  className,
}) => {
  const normalizedKey = (
    severity.toUpperCase().trim()
  ) as SeverityType;
  const token = SEVERITY_TOKENS[normalizedKey] || SEVERITY_TOKENS.INFORMATIONAL;

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

  const renderGlyph = () => {
    const s = iconSizes[size];
    switch (token.glyph) {
      case "octagon":
        return <OctagonAlert size={s} className="shrink-0 stroke-[2.5]" aria-hidden="true" />;
      case "diamond":
        return <Diamond size={s} className="shrink-0 fill-current stroke-1" aria-hidden="true" />;
      case "triangle":
        return <TriangleAlert size={s} className="shrink-0 stroke-[2.2]" aria-hidden="true" />;
      case "circle":
        return <CircleDot size={s} className="shrink-0 stroke-[2]" aria-hidden="true" />;
      case "square":
      default:
        return <Info size={s} className="shrink-0 stroke-[1.8]" aria-hidden="true" />;
    }
  };

  if (monochromePrint) {
    return (
      <span
        role="status"
        aria-label={`Severity: ${token.label}`}
        className={cn(
          "inline-flex items-center border border-black font-mono text-black bg-white rounded-full px-2.5 py-0.5 text-xs gap-1",
          token.monochrome.borderThickness === 3 && "border-2 font-bold",
          token.monochrome.borderThickness === 2 && "border font-semibold",
          className
        )}
      >
        <span className="font-bold">{token.glyphSymbol}</span>
        {showLabel && <span>{token.label.toUpperCase()}</span>}
      </span>
    );
  }

  return (
    <span
      role="status"
      aria-label={`Severity: ${token.label}`}
      className={cn(
        "inline-flex items-center rounded-full border shadow-sm select-none transition-all duration-150",
        sizeClasses[size],
        token.color.bg,
        token.color.darkBg,
        className
      )}
    >
      {renderGlyph()}
      {showLabel && <span>{token.label}</span>}
    </span>
  );
};
