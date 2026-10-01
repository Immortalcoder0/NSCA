/**
 * NSCA Shared Design Tokens & Visual Vocabulary
 * Single source of truth for Verdict, Severity, and Trust Tier treatments.
 * Strictly implements 12-ux-specification.md §10 & frontend-00-shared-foundations.md §2.3.
 *
 * Guarantees:
 * - U3: UNKNOWN is a distinct visual state (question mark, purple badge), never styled like PASS.
 * - U7: Severity is never color alone; every level pairs with a distinct shape/glyph.
 * - Monochrome safe: All states remain distinguishable in black-and-white printouts.
 */

export type VerdictType =
  | "PASS"
  | "PASS_PARTIAL"
  | "PASS_VACUOUS"
  | "FAIL"
  | "UNKNOWN"
  | "NOT_APPLICABLE";

export type SeverityType =
  | "CRITICAL"
  | "HIGH"
  | "MEDIUM"
  | "LOW"
  | "INFORMATIONAL";

export type TrustTierType =
  | "CERTIFIED"
  | "COMMUNITY"
  | "SYNTHESIZED"
  | "UNVERIFIED";

export interface VerdictToken {
  id: VerdictType;
  label: string;
  shortLabel: string;
  description: string;
  glyph: "check-filled" | "check-warning" | "check-hollow" | "cross-solid" | "question" | "dash";
  iconName: string;
  color: {
    bg: string;
    text: string;
    border: string;
    hex: string;
    darkBg: string;
    darkText: string;
  };
  monochrome: {
    glyphSymbol: string;
    borderStyle: "solid" | "dashed" | "dotted" | "double";
    fillPattern: "solid" | "striped" | "hollow" | "shaded" | "none";
  };
}

export interface SeverityToken {
  id: SeverityType;
  label: string;
  weight: number;
  glyph: "octagon" | "diamond" | "triangle" | "circle" | "square";
  glyphSymbol: string;
  iconName: string;
  color: {
    bg: string;
    text: string;
    border: string;
    hex: string;
    darkBg: string;
    darkText: string;
  };
  monochrome: {
    borderThickness: number; // in px
    fillPattern: "solid" | "crosshatch" | "striped" | "dotted" | "outline";
  };
}

export interface TrustTierToken {
  id: TrustTierType;
  label: string;
  description: string;
  badgeText: string;
  isCertified: boolean;
  glyph: "shield-check" | "users" | "sparkles" | "alert-circle";
  color: {
    bg: string;
    text: string;
    border: string;
    hex: string;
  };
}

export const VERDICT_TOKENS: Record<VerdictType, VerdictToken> = {
  PASS: {
    id: "PASS",
    label: "Pass",
    shortLabel: "PASS",
    description: "All conditions satisfied with concrete affirmative evidence.",
    glyph: "check-filled",
    iconName: "CheckCircle2",
    color: {
      bg: "bg-emerald-50 text-emerald-700 border-emerald-200",
      text: "text-emerald-700",
      border: "border-emerald-200",
      hex: "#10b981",
      darkBg: "dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800",
      darkText: "dark:text-emerald-300",
    },
    monochrome: {
      glyphSymbol: "[✓]",
      borderStyle: "solid",
      fillPattern: "solid",
    },
  },
  PASS_PARTIAL: {
    id: "PASS_PARTIAL",
    label: "Pass (Partial)",
    shortLabel: "PARTIAL",
    description: "Rule satisfied with non-critical caveats or partial scope.",
    glyph: "check-warning",
    iconName: "AlertTriangle",
    color: {
      bg: "bg-amber-50 text-amber-800 border-amber-300",
      text: "text-amber-800",
      border: "border-amber-300",
      hex: "#d97706",
      darkBg: "dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800",
      darkText: "dark:text-amber-300",
    },
    monochrome: {
      glyphSymbol: "[✓!]",
      borderStyle: "dashed",
      fillPattern: "striped",
    },
  },
  PASS_VACUOUS: {
    id: "PASS_VACUOUS",
    label: "Pass (Vacuous)",
    shortLabel: "VACUOUS",
    description: "Universally quantified condition satisfied over empty target set.",
    glyph: "check-hollow",
    iconName: "CircleDot",
    color: {
      bg: "bg-sky-50 text-sky-700 border-sky-200",
      text: "text-sky-700",
      border: "border-sky-200",
      hex: "#0284c7",
      darkBg: "dark:bg-sky-950/50 dark:text-sky-300 dark:border-sky-800",
      darkText: "dark:text-sky-300",
    },
    monochrome: {
      glyphSymbol: "(✓)",
      borderStyle: "dotted",
      fillPattern: "hollow",
    },
  },
  FAIL: {
    id: "FAIL",
    label: "Fail",
    shortLabel: "FAIL",
    description: "One or more security conditions violated.",
    glyph: "cross-solid",
    iconName: "XCircle",
    color: {
      bg: "bg-red-50 text-red-700 border-red-200",
      text: "text-red-700",
      border: "border-red-200",
      hex: "#ef4444",
      darkBg: "dark:bg-red-950/50 dark:text-red-300 dark:border-red-800",
      darkText: "dark:text-red-300",
    },
    monochrome: {
      glyphSymbol: "[✗]",
      borderStyle: "solid",
      fillPattern: "solid",
    },
  },
  UNKNOWN: {
    id: "UNKNOWN",
    label: "Unknown (⊥)",
    shortLabel: "UNKNOWN",
    description: "Missing required evidence; uncertainty cannot be resolved to PASS or FAIL.",
    glyph: "question",
    iconName: "HelpCircle",
    color: {
      bg: "bg-slate-100 text-slate-800 border-slate-300",
      text: "text-slate-800",
      border: "border-slate-300",
      hex: "#475569",
      darkBg: "dark:bg-slate-800/80 dark:text-slate-200 dark:border-slate-700",
      darkText: "dark:text-slate-200",
    },
    monochrome: {
      glyphSymbol: "{?}",
      borderStyle: "double",
      fillPattern: "shaded",
    },
  },
  NOT_APPLICABLE: {
    id: "NOT_APPLICABLE",
    label: "Not Applicable",
    shortLabel: "N/A",
    description: "Rule does not apply to this device platform or feature scope.",
    glyph: "dash",
    iconName: "MinusCircle",
    color: {
      bg: "bg-slate-100 text-slate-600 border-slate-200",
      text: "text-slate-600",
      border: "border-slate-200",
      hex: "#64748b",
      darkBg: "dark:bg-slate-900/60 dark:text-slate-400 dark:border-slate-800",
      darkText: "dark:text-slate-400",
    },
    monochrome: {
      glyphSymbol: "[-]",
      borderStyle: "dotted",
      fillPattern: "none",
    },
  },
};

export const SEVERITY_TOKENS: Record<SeverityType, SeverityToken> = {
  CRITICAL: {
    id: "CRITICAL",
    label: "Critical",
    weight: 5,
    glyph: "octagon",
    glyphSymbol: "⯃", // Octagonal badge marker
    iconName: "OctagonAlert",
    color: {
      bg: "bg-red-100 text-red-900 border-red-400 font-semibold",
      text: "text-red-900 dark:text-red-200",
      border: "border-red-400 dark:border-red-700",
      hex: "#991b1b",
      darkBg: "dark:bg-red-950 dark:text-red-200 dark:border-red-800",
      darkText: "dark:text-red-200",
    },
    monochrome: {
      borderThickness: 3,
      fillPattern: "solid",
    },
  },
  HIGH: {
    id: "HIGH",
    label: "High",
    weight: 4,
    glyph: "diamond",
    glyphSymbol: "◆",
    iconName: "DiamondAlert",
    color: {
      bg: "bg-orange-100 text-orange-900 border-orange-300",
      text: "text-orange-900 dark:text-orange-200",
      border: "border-orange-300 dark:border-orange-700",
      hex: "#ea580c",
      darkBg: "dark:bg-orange-950/60 dark:text-orange-200 dark:border-orange-800",
      darkText: "dark:text-orange-200",
    },
    monochrome: {
      borderThickness: 2,
      fillPattern: "crosshatch",
    },
  },
  MEDIUM: {
    id: "MEDIUM",
    label: "Medium",
    weight: 3,
    glyph: "triangle",
    glyphSymbol: "▲",
    iconName: "TriangleAlert",
    color: {
      bg: "bg-amber-100 text-amber-900 border-amber-300",
      text: "text-amber-900 dark:text-amber-200",
      border: "border-amber-300 dark:border-amber-700",
      hex: "#d97706",
      darkBg: "dark:bg-amber-950/60 dark:text-amber-200 dark:border-amber-800",
      darkText: "dark:text-amber-200",
    },
    monochrome: {
      borderThickness: 2,
      fillPattern: "striped",
    },
  },
  LOW: {
    id: "LOW",
    label: "Low",
    weight: 2,
    glyph: "circle",
    glyphSymbol: "●",
    iconName: "CircleAlert",
    color: {
      bg: "bg-blue-50 text-blue-800 border-blue-200",
      text: "text-blue-800 dark:text-blue-300",
      border: "border-blue-200 dark:border-blue-800",
      hex: "#2563eb",
      darkBg: "dark:bg-blue-950/50 dark:text-blue-300 dark:border-blue-800",
      darkText: "dark:text-blue-300",
    },
    monochrome: {
      borderThickness: 1,
      fillPattern: "dotted",
    },
  },
  INFORMATIONAL: {
    id: "INFORMATIONAL",
    label: "Info",
    weight: 1,
    glyph: "square",
    glyphSymbol: "■",
    iconName: "Info",
    color: {
      bg: "bg-slate-100 text-slate-700 border-slate-300",
      text: "text-slate-700 dark:text-slate-300",
      border: "border-slate-300 dark:border-slate-700",
      hex: "#64748b",
      darkBg: "dark:bg-slate-900/60 dark:text-slate-300 dark:border-slate-800",
      darkText: "dark:text-slate-300",
    },
    monochrome: {
      borderThickness: 1,
      fillPattern: "outline",
    },
  },
};

export const TRUST_TIER_TOKENS: Record<TrustTierType, TrustTierToken> = {
  CERTIFIED: {
    id: "CERTIFIED",
    label: "Certified Rulepack",
    description: "Official vendor/regulator baseline pack with verified cryptographic signatures.",
    badgeText: "CERTIFIED",
    isCertified: true,
    glyph: "shield-check",
    color: {
      bg: "bg-emerald-50 text-emerald-800 border-emerald-300",
      text: "text-emerald-800 dark:text-emerald-300",
      border: "border-emerald-300 dark:border-emerald-700",
      hex: "#059669",
    },
  },
  COMMUNITY: {
    id: "COMMUNITY",
    label: "Community Rulepack",
    description: "Shared community rulepack; peer-reviewed without official certification.",
    badgeText: "COMMUNITY",
    isCertified: false,
    glyph: "users",
    color: {
      bg: "bg-blue-50 text-blue-800 border-blue-300",
      text: "text-blue-800 dark:text-blue-300",
      border: "border-blue-300 dark:border-blue-700",
      hex: "#2563eb",
    },
  },
  SYNTHESIZED: {
    id: "SYNTHESIZED",
    label: "Synthesized (AI Learner)",
    description: "Machine-learned rulepack awaiting full lead assessor ratification.",
    badgeText: "SYNTHESIZED",
    isCertified: false,
    glyph: "sparkles",
    color: {
      bg: "bg-slate-100 text-slate-800 border-slate-300 border-dashed",
      text: "text-slate-800 dark:text-slate-300",
      border: "border-slate-300 dark:border-slate-700",
      hex: "#475569",
    },
  },
  UNVERIFIED: {
    id: "UNVERIFIED",
    label: "Unverified / Custom",
    description: "Imported custom rulepack without validation seal.",
    badgeText: "UNVERIFIED",
    isCertified: false,
    glyph: "alert-circle",
    color: {
      bg: "bg-amber-50 text-amber-800 border-amber-300 border-dashed",
      text: "text-amber-800 dark:text-amber-300",
      border: "border-amber-300 dark:border-amber-700",
      hex: "#d97706",
    },
  },
};
