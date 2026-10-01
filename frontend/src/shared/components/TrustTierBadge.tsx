import React from "react";
import { ShieldCheck, Users, Sparkles, AlertCircle } from "lucide-react";
import { TRUST_TIER_TOKENS, type TrustTierType } from "../theme/tokens";
import { cn } from "../lib/utils";

export interface TrustTierBadgeProps {
  tier: TrustTierType | string;
  size?: "sm" | "md";
  showIcon?: boolean;
  className?: string;
}

export const TrustTierBadge: React.FC<TrustTierBadgeProps> = ({
  tier,
  size = "sm",
  showIcon = true,
  className,
}) => {
  const normalizedKey = (
    tier.toUpperCase().trim()
  ) as TrustTierType;
  const token = TRUST_TIER_TOKENS[normalizedKey] || TRUST_TIER_TOKENS.UNVERIFIED;

  const sizeClasses = {
    sm: "text-[10px] tracking-wider px-2 py-0.5 font-bold uppercase",
    md: "text-xs px-2.5 py-1 font-semibold uppercase",
  };

  const iconSizes = {
    sm: 11,
    md: 13,
  };

  const renderIcon = () => {
    if (!showIcon) return null;
    const s = iconSizes[size];
    switch (token.glyph) {
      case "shield-check":
        return <ShieldCheck size={s} className="shrink-0" aria-hidden="true" />;
      case "users":
        return <Users size={s} className="shrink-0" aria-hidden="true" />;
      case "sparkles":
        return <Sparkles size={s} className="shrink-0" aria-hidden="true" />;
      case "alert-circle":
      default:
        return <AlertCircle size={s} className="shrink-0" aria-hidden="true" />;
    }
  };

  return (
    <span
      role="status"
      title={token.description}
      aria-label={`Rulepack Trust Tier: ${token.label}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border shadow-sm select-none transition-all",
        sizeClasses[size],
        token.color.bg,
        token.color.border,
        token.color.text,
        className
      )}
    >
      {renderIcon()}
      <span>{token.badgeText}</span>
    </span>
  );
};
